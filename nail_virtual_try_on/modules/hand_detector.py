# Hand Detector Module
# MediaPipe Tasks API (0.10+) hand landmark detection + nail region estimation

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# MediaPipe landmark indices
# ---------------------------------------------------------------------------
# Each tuple: (tip, dip, pip, mcp)
FINGER_DEFS = {
    "thumb":  {"tip": 4, "dip": 3, "pip": 2, "mcp": 1},
    "index":  {"tip": 8, "dip": 7, "pip": 6, "mcp": 5},
    "middle": {"tip": 12, "dip": 11, "pip": 10, "mcp": 9},
    "ring":   {"tip": 16, "dip": 15, "pip": 14, "mcp": 13},
    "pinky":  {"tip": 20, "dip": 19, "pip": 18, "mcp": 17},
}

# Default model path.
# MediaPipe's C++ backend cannot open paths with non-ASCII (e.g. Chinese) characters
# on Windows, so we first try a plain-ASCII fallback location.
_DEFAULT_MODEL_ASCII = Path("C:/tmp/mediapipe/hand_landmarker.task")
_DEFAULT_MODEL_LOCAL = Path(__file__).parent.parent / "data" / "hand_landmarker.task"

def _resolve_model_path() -> Optional[Path]:
    if _DEFAULT_MODEL_ASCII.exists():
        return _DEFAULT_MODEL_ASCII
    # Try to copy to the ASCII path on-the-fly
    if _DEFAULT_MODEL_LOCAL.exists():
        try:
            import shutil
            _DEFAULT_MODEL_ASCII.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(_DEFAULT_MODEL_LOCAL), str(_DEFAULT_MODEL_ASCII))
            return _DEFAULT_MODEL_ASCII
        except Exception:
            pass
    return None


class HandDetector:
    """
    Detects hand landmarks via MediaPipe Tasks API and estimates
    per-finger nail regions as oriented ellipses.

    Falls back to a skin-colour heuristic when MediaPipe is unavailable
    or the model file is missing.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.5,
    ):
        self._mp_available = False
        self._detector = None

        mp_path = Path(model_path) if model_path else _resolve_model_path()
        if mp_path is None:
            print("[HandDetector] No model file found. Using fallback detection.")
            return

        if not mp_path.exists():
            print(f"[HandDetector] Model not found at {mp_path}. Using fallback detection.")
            return


        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            base_options = mp_python.BaseOptions(model_asset_path=str(mp_path))
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_hands=max_num_hands,
                min_hand_detection_confidence=min_detection_confidence,
                min_hand_presence_confidence=min_detection_confidence,
                min_tracking_confidence=0.4,
            )
            self._detector = vision.HandLandmarker.create_from_options(options)
            self._mp_available = True
        except Exception as e:
            print(f"[HandDetector] MediaPipe init failed: {e}. Using fallback detection.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, image_bgr: np.ndarray) -> Dict:
        """
        Run detection on a BGR image.

        Returns
        -------
        {
          "detected": bool,
          "hands": [
            {
              "landmarks":  np.ndarray (21, 3)  # pixel coords (x, y, z_rel)
              "nail_masks": {"thumb": mask, ...}  # (H,W) uint8
              "hand_mask":  np.ndarray (H, W) uint8
              "nail_info":  {finger: geometry dict}
              "handedness": "Left" | "Right"
            }, ...
          ]
        }
        """
        if self._mp_available:
            return self._detect_mediapipe(image_bgr)
        return self._detect_fallback(image_bgr)

    def draw_debug(self, image_bgr: np.ndarray, result: Dict) -> np.ndarray:
        """Overlay landmarks and nail-mask outlines for inspection."""
        vis = image_bgr.copy()
        if not result["detected"]:
            return vis
        for hand in result["hands"]:
            for pt in hand["landmarks"][:, :2]:
                cv2.circle(vis, (int(pt[0]), int(pt[1])), 3, (0, 200, 255), -1)
            for mask in hand["nail_masks"].values():
                contours, _ = cv2.findContours(
                    mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                cv2.drawContours(vis, contours, -1, (0, 255, 128), 2)
        return vis

    # ------------------------------------------------------------------
    # MediaPipe Tasks path
    # ------------------------------------------------------------------

    def _detect_mediapipe(self, bgr: np.ndarray) -> Dict:
        import mediapipe as mp

        # MediaPipe Tasks needs an mp.Image (RGB format)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self._detector.detect(mp_image)

        if not result.hand_landmarks:
            return {"detected": False, "hands": []}

        h, w = bgr.shape[:2]
        hands_out = []

        for lms, handedness_list in zip(result.hand_landmarks, result.handedness):
            landmarks = np.array(
                [[lm.x * w, lm.y * h, lm.z * w] for lm in lms],
                dtype=np.float32,
            )
            nail_masks, nail_info = self._estimate_nail_masks(landmarks, (h, w))
            hand_mask = self._build_hand_mask(landmarks, (h, w))
            hand_label = handedness_list[0].display_name  # "Left" or "Right"

            hands_out.append(
                {
                    "landmarks": landmarks,
                    "nail_masks": nail_masks,
                    "nail_info": nail_info,
                    "hand_mask": hand_mask,
                    "handedness": hand_label,
                }
            )

        return {"detected": True, "hands": hands_out}

    # ------------------------------------------------------------------
    # Nail-mask geometry
    # ------------------------------------------------------------------

    def _estimate_nail_masks(
        self, landmarks: np.ndarray, img_size: Tuple[int, int]
    ) -> Tuple[Dict, Dict]:
        """
        Estimate an oriented-ellipse nail mask for each finger.

        Coordinate anatomy (TIP = landmark tip, DIP = first joint):

          FREE EDGE          CUTICLE
          |<--- nail_h --->|
          TIP ─────────────── DIP
           0%              ~50% of TIP-DIP distance

        Geometry:
          nail_h  = TIP-DIP * 0.54
          nail_w  = nail_h  * 0.90  (nails ~slightly narrower than long)
          center  = TIP + unit * nail_h * 0.40
                    (free edge extends ~10 % past TIP, cuticle at ~90 %)
          angle   = aligned with TIP→DIP finger axis
        """
        h, w = img_size
        nail_masks: Dict[str, np.ndarray] = {}
        nail_info:  Dict[str, Dict]       = {}

        for fname, fidx in FINGER_DEFS.items():
            tip = landmarks[fidx["tip"], :2]
            dip = landmarks[fidx["dip"], :2]
            pip = landmarks[fidx["pip"], :2]

            vec = dip - tip                          # from fingertip toward DIP joint
            dist = float(np.linalg.norm(vec))
            if dist < 2.0:
                continue
            unit = vec / dist
            perp = np.array([-unit[1], unit[0]], dtype=np.float32)

            # ── Perspective / view-angle estimate ─────────────────────
            # Foreshortening: how much of the TIP→DIP segment's true 3-D
            # length is "lost" to depth (z) rather than on-screen length.
            # A finger photographed side-on (thumb rolled toward camera is
            # the classic case) shows large |Δz| relative to its 3-D
            # length — its nail is seen edge-on and renders narrower /
            # more curved than a front-facing nail.
            seg3d   = landmarks[fidx["dip"], :3] - landmarks[fidx["tip"], :3]
            len3d   = float(np.linalg.norm(seg3d))
            foreshortening = float(np.clip(abs(float(seg3d[2])) / max(len3d, 1e-3), 0.0, 1.0))
            is_side_view   = (fname == "thumb" and foreshortening > 0.35) or foreshortening > 0.55

            # ── Nail dimensions ───────────────────────────────────────
            nail_h = dist * 0.54                     # nail plate height
            nail_w = nail_h * 0.90                   # nail plate width
            if is_side_view:
                # Side/tilted view: the visible nail plate compresses
                # toward the viewer — narrow the fill so it follows the
                # finger's true silhouette instead of overflowing onto skin.
                nail_w *= (1.0 - 0.30 * foreshortening)

            # Centre: 40 % of nail_h from tip toward DIP
            # → free edge ~10 % of nail_h past TIP (natural overhang)
            # → cuticle  ~90 % of nail_h toward DIP
            center = tip + unit * (nail_h * 0.40)

            # ── Orientation ───────────────────────────────────────────
            # angle aligns the ellipse long axis with the finger direction.
            # cv2.ellipse: axes=(semi-x, semi-y) before rotation (clockwise).
            # With angle=0: semi-y is vertical. We rotate so semi-y aligns with vec.
            angle_deg = float(np.degrees(np.arctan2(vec[1], vec[0])) - 90.0)

            # semi-axes: (perpendicular-to-finger, along-finger)
            ax_perp  = max(4, int(nail_w / 2))
            ax_along = max(6, int(nail_h / 2))

            # ── Fault tolerance: clamp width to the finger's own joint
            # width so a noisy landmark can't blow the nail mask out past
            # the finger silhouette (overflow onto skin / neighbours).
            finger_width_ref = float(np.linalg.norm(pip - dip)) * 1.20
            max_perp = max(4, int(finger_width_ref))
            if ax_perp > max_perp:
                ax_perp = max_perp

            axes = (ax_perp, ax_along)

            cx_f = float(np.clip(center[0], ax_perp,  w - ax_perp  - 1))
            cy_f = float(np.clip(center[1], ax_along, h - ax_along - 1))
            # If the in-bounds clamp dragged the centre far from the
            # detected tip, the landmark is likely noisy near the image
            # edge — re-anchor to the raw centre rather than compounding
            # the drift (better a slightly clipped nail than a misplaced one).
            if np.hypot(cx_f - center[0], cy_f - center[1]) > nail_h * 0.5:
                cx_f = float(np.clip(center[0], 0, w - 1))
                cy_f = float(np.clip(center[1], 0, h - 1))
            cx, cy = int(cx_f), int(cy_f)
            center_clamped = np.array([cx_f, cy_f], dtype=np.float32)

            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.ellipse(mask, (cx, cy), axes, angle_deg, 0, 360, 255, -1)

            # ── Keypoints: 4 corners + free-edge arc apex + cuticle line ──
            # Anchored on `unit`/`perp` (the ellipse's own major/minor axes),
            # so they sit exactly on the rendered ellipse boundary and stay
            # consistent under rotation — usable downstream for perspective
            # warping / surface fitting as the user's nail bends with the finger.
            ax_w_f, ax_h_f = float(axes[0]), float(axes[1])
            apex      = center_clamped - unit * ax_h_f      # free-edge arc apex (tip side)
            cuticle_c = center_clamped + unit * ax_h_f      # cuticle-line centre (DIP side)
            keypoints = {
                "apex":        apex.tolist(),
                "cuticle_mid": cuticle_c.tolist(),
                "corner_tip_l":     (apex      + perp * ax_w_f).tolist(),
                "corner_tip_r":     (apex      - perp * ax_w_f).tolist(),
                "corner_cuticle_l": (cuticle_c + perp * ax_w_f).tolist(),
                "corner_cuticle_r": (cuticle_c - perp * ax_w_f).tolist(),
            }

            # Dense anchor ring (≥20 pts, evenly spread across all four
            # edges: free edge / cuticle line / two side walls) — the
            # single shared basis for any downstream warping or deformation,
            # so renders never improvise a different contour per step.
            n_per_edge = 5
            edge_spans = (np.linspace(-1.0, 1.0, n_per_edge),)
            anchor_points = []
            for tt in edge_spans[0]:                                   # free edge (apex side)
                anchor_points.append((apex      + perp * (ax_w_f * tt)).tolist())
            for tt in edge_spans[0]:                                   # cuticle line
                anchor_points.append((cuticle_c + perp * (ax_w_f * tt)).tolist())
            for tt in edge_spans[0]:                                   # left side wall
                anchor_points.append((center_clamped - perp * ax_w_f + unit * (ax_h_f * tt)).tolist())
            for tt in edge_spans[0]:                                   # right side wall
                anchor_points.append((center_clamped + perp * ax_w_f + unit * (ax_h_f * tt)).tolist())
            keypoints["anchor_points"] = anchor_points

            nail_masks[fname] = mask
            nail_info[fname]  = {
                "center":         center_clamped,
                "axes":           axes,
                "angle":          angle_deg,
                "tip":            tip,
                "dip":            dip,
                "nail_h":         nail_h,
                "nail_w":         nail_w,
                "is_side_view":   is_side_view,
                "foreshortening": foreshortening,
                "keypoints":      keypoints,
            }

        return nail_masks, nail_info

    def _build_hand_mask(self, landmarks: np.ndarray, img_size: Tuple[int, int]) -> np.ndarray:
        h, w = img_size
        pts  = landmarks[:, :2].astype(np.int32)
        hull = cv2.convexHull(pts)
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [hull], 255)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        return cv2.dilate(mask, kernel)

    # ------------------------------------------------------------------
    # Fallback: YCrCb skin segmentation
    # ------------------------------------------------------------------

    def _detect_fallback(self, bgr: np.ndarray) -> Dict:
        """
        Very rough hand detection using YCrCb skin-colour segmentation.
        Used only when MediaPipe is unavailable.
        """
        h, w = bgr.shape[:2]
        ycrcb    = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN,  kernel, iterations=2)

        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return {"detected": False, "hands": []}

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 5000:
            return {"detected": False, "hands": []}

        x, y, bw, bh = cv2.boundingRect(largest)
        cx = x + bw // 2
        offsets = [-0.35, -0.17, 0.0, 0.17, 0.33]
        finger_names = ["thumb", "index", "middle", "ring", "pinky"]

        nail_masks: Dict[str, np.ndarray] = {}
        for fname, dx in zip(finger_names, offsets):
            fx = cx + int(bw * dx)
            fy = y + bh // 6
            m  = np.zeros((h, w), dtype=np.uint8)
            cv2.ellipse(m, (fx, fy), (max(6, bw // 16), max(10, bh // 10)), 0, 0, 360, 255, -1)
            nail_masks[fname] = m

        hand_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(hand_mask, [largest], -1, 255, -1)

        landmarks = np.zeros((21, 3), dtype=np.float32)

        return {
            "detected": True,
            "hands": [
                {
                    "landmarks": landmarks,
                    "nail_masks": nail_masks,
                    "nail_info": {},
                    "hand_mask": hand_mask,
                    "handedness": "Right",
                }
            ],
        }


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    detector = HandDetector()
    print("MediaPipe available:", detector._mp_available)
    dummy = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
    result = detector.detect(dummy)
    print("Detected:", result["detected"])
    if result["detected"]:
        print("Fingers:", list(result["hands"][0]["nail_masks"].keys()))
