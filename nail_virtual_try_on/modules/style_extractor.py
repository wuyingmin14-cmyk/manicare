"""
style_extractor.py
==================
Extracts the per-nail ART COLOUR from style reference photos.

Design philosophy
-----------------
Earlier attempts extracted full-texture BGRA patches and warped them onto
the user's nail via homography. That approach was abandoned: the visible
nail art occupies an unpredictable sub-region of the MediaPipe-estimated
nail ellipse (it can extend far past the biological fingertip for long /
extension nails, or sit only on the lower half of the ellipse for short
nails), so warping the whole patch either smears skin/background into the
result or shrinks the art into a tiny off-centre spot.

Instead we extract just the DOMINANT COLOUR of the nail art and render it
as a solid, glossy fill on the user's nail (plus specular highlight and
edge shadow for a photoreal look — see nail_transfer.py). This sidesteps
all alignment problems and matches how the vast majority of manicure
styles actually look (solid / near-solid colour, sometimes with glitter
or fine pattern that the dominant colour represents well).

Telling nail art from skin
--------------------------
Generic colour-space thresholds (YCrCb skin ranges, brightness cut-offs)
proved unreliable because nail-art hues can overlap with skin tones in any
colour space. Instead we sample a SKIN-TONE REFERENCE directly from the
same finger's knuckle area (clearly skin, never covered by nail art) and
classify nearby pixels by their distance from *that* reference colour —
this adapts to each individual photo's actual skin tone.
"""

import cv2
import numpy as np
from typing import Dict, Optional, Tuple

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]

# Sampling ellipse scale relative to the MediaPipe nail estimate — large
# enough to catch extended/long nail art, small enough to mostly stay on
# the finger (avoiding background contamination).
_SAMPLE_SCALE_H = 1.8
_SAMPLE_SCALE_W = 1.3

# Minimum BGR distance from the skin reference for a pixel to count as
# "nail art" rather than skin.
_SKIN_DIST_THRESH = 38.0


# ── Skin-tone reference ───────────────────────────────────────────────────────

def _sample_skin_color(style_img: np.ndarray, info: Dict) -> Optional[np.ndarray]:
    """Median BGR sampled from the knuckle area beyond the DIP joint (always skin)."""
    tip = np.array(info["tip"], dtype=np.float32)
    dip = np.array(info["dip"], dtype=np.float32)
    vec = dip - tip
    dist = float(np.linalg.norm(vec))
    if dist < 2.0:
        return None
    unit = vec / dist
    sample_pt = dip + unit * (dist * 0.55)        # well past the joint, into the knuckle

    sx, sy = int(round(sample_pt[0])), int(round(sample_pt[1]))
    h, w = style_img.shape[:2]
    r = max(3, int(dist * 0.18))
    x1, x2 = max(0, sx - r), min(w, sx + r)
    y1, y2 = max(0, sy - r), min(h, sy + r)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None

    region = style_img[y1:y2, x1:x2].reshape(-1, 3).astype(np.float32)
    return np.median(region, axis=0)


# ── Colour-region analysis (feeds the recommendation embedding) ─────────────

def analyse_color_region(pixels_bgr: np.ndarray) -> Dict:
    """Build a descriptor dict (same shape as the old analyse_patch) from BGR samples."""
    if pixels_bgr is None or len(pixels_bgr) < 5:
        return {"dominant_hsv": (0, 0, 128), "contrast": 0.0,
                "saturation": 0.0, "pattern_score": 0.0, "glitter_score": 0.0}

    sample = pixels_bgr.reshape(-1, 1, 3).astype(np.uint8)
    hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    h_vals, s_vals, v_vals = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    contrast      = float(np.std(v_vals)) / 128.0
    saturation    = float(np.mean(s_vals)) / 255.0
    glitter_score = float((s_vals > 120).sum()) / max(len(s_vals), 1)

    return {
        "dominant_hsv":  (float(np.median(h_vals)),
                          float(np.mean(s_vals)),
                          float(np.mean(v_vals))),
        "contrast":      contrast,
        "saturation":    saturation,
        "pattern_score": min(1.0, contrast),
        "glitter_score": min(1.0, glitter_score),
    }


# ── Main extraction ───────────────────────────────────────────────────────────

def extract_dominant_color(
    style_img: np.ndarray,
    nail_info: Dict,
    finger: str,
) -> Tuple[Optional[Tuple[float, float, float]], Optional[Dict]]:
    """
    Sample the actual nail-art colour for *finger*.

    Returns (bgr_color, analysis_dict) or (None, None) on failure.
    bgr_color is a 3-tuple of floats in [0, 255], BGR order.
    """
    info = nail_info.get(finger)
    if info is None:
        return None, None

    cx, cy     = info["center"]
    ax_w, ax_h = info["axes"]
    angle      = info["angle"]
    tip        = np.array(info["tip"], dtype=np.float32)
    dip        = np.array(info["dip"], dtype=np.float32)
    vec        = dip - tip
    dist       = float(np.linalg.norm(vec))
    unit       = vec / dist if dist > 1e-3 else np.array([0.0, 1.0], dtype=np.float32)

    # Bias the sampling region toward the free edge, where art concentrates
    # for long / extension nails (MediaPipe's centre sits closer to cuticle).
    sample_centre = np.array([cx, cy], dtype=np.float32) - unit * (info["nail_h"] * 0.20)

    h, w = style_img.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(
        mask,
        (int(round(sample_centre[0])), int(round(sample_centre[1]))),
        (max(4, int(ax_w * _SAMPLE_SCALE_W)), max(6, int(ax_h * _SAMPLE_SCALE_H))),
        float(angle), 0, 360, 255, -1,
    )
    ys, xs = np.where(mask > 0)
    if len(ys) < 30:
        return None, None

    pixels = style_img[ys, xs].astype(np.float32)            # N×3 BGR

    skin_bgr = _sample_skin_color(style_img, info)
    if skin_bgr is not None:
        d = np.linalg.norm(pixels - skin_bgr[np.newaxis, :], axis=1)
        nail_pixels = pixels[d > _SKIN_DIST_THRESH]
        if len(nail_pixels) < max(20, len(pixels) * 0.05):
            nail_pixels = pixels                              # fallback: use everything
    else:
        nail_pixels = pixels

    color    = np.median(nail_pixels, axis=0)                # BGR
    analysis = analyse_color_region(nail_pixels.astype(np.uint8))
    return tuple(float(c) for c in color), analysis


def fallback_dominant_color(style_img: np.ndarray) -> Tuple[Tuple[float, float, float], Dict]:
    """When no hand is detected: sample the centre crop of the photo."""
    h, w = style_img.shape[:2]
    crop = style_img[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
    pixels = crop.reshape(-1, 3).astype(np.float32)
    color = np.median(pixels, axis=0)
    analysis = analyse_color_region(pixels.astype(np.uint8))
    return tuple(float(c) for c in color), analysis
