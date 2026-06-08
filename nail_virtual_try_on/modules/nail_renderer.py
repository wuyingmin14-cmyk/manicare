# Nail Renderer Module
# Applies nail-color/pattern textures to detected nail regions

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Style catalogue
# ---------------------------------------------------------------------------

NAIL_STYLES: Dict[str, Dict] = {
    # --- Classics ---
    "wine_red":    {"name_cn": "酒红", "hex": "#722F37", "bgr": (55,  47, 114), "pattern": "solid",    "category": "经典"},
    "classic_red": {"name_cn": "经典红","hex": "#C41E3A", "bgr": (58,  30, 196), "pattern": "solid",    "category": "经典"},
    "nude_beige":  {"name_cn": "裸米色","hex": "#E5C2A7", "bgr": (167,194, 229), "pattern": "solid",    "category": "自然"},

    # --- Trendy ---
    "coral_pink":  {"name_cn": "珊瑚粉","hex": "#FF7F50", "bgr": (80, 127, 255), "pattern": "solid",    "category": "流行"},
    "mint_green":  {"name_cn": "薄荷绿","hex": "#98FB98", "bgr": (152,251, 152), "pattern": "solid",    "category": "清爽"},
    "ocean_blue":  {"name_cn": "海洋蓝","hex": "#006994", "bgr": (148,105,   0), "pattern": "shimmer",  "category": "流行"},

    # --- Elegant ---
    "deep_purple": {"name_cn": "深紫",  "hex": "#4B0A4B", "bgr": (75,  10,  75), "pattern": "shimmer",  "category": "优雅"},
    "rose_gold":   {"name_cn": "玫瑰金","hex": "#B76E79", "bgr": (121,110, 183), "pattern": "metallic", "category": "奢华"},
    "french_tip":  {"name_cn": "法式白","hex": "#F0E6D2", "bgr": (210,230, 240), "pattern": "french",   "category": "优雅"},

    # --- Bold ---
    "black_glitter":{"name_cn":"黑闪粉","hex": "#141414", "bgr": (20,  20,  20), "pattern": "glitter",  "category": "个性"},
}

# Skin-type → recommended style names
SKIN_RECOMMENDATIONS: Dict[str, List[str]] = {
    "warm_yellow": ["ocean_blue", "deep_purple", "wine_red", "mint_green", "classic_red"],
    "cool_white":  ["wine_red", "classic_red", "deep_purple", "rose_gold", "french_tip"],
    "dark_skin":   ["classic_red", "rose_gold", "nude_beige", "coral_pink", "black_glitter"],
    "neutral":     ["classic_red", "nude_beige", "coral_pink", "rose_gold", "french_tip"],
}


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class NailRenderer:
    """
    Renders nail styles (solid colour, shimmer, metallic, glitter, French-tip)
    onto detected nail-region masks with realistic edge blending.
    """

    def __init__(self):
        self.styles = NAIL_STYLES
        # Directional light source (upper-right, in image-space units).
        # Drives where the specular highlight lands so it reads as a real
        # light raking across a glossy convex surface, not a fixed blob.
        self.light_dir = np.array([0.3, -0.7], dtype=np.float32)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        image_bgr: np.ndarray,
        nail_masks: Dict[str, np.ndarray],
        style_name: str,
        opacity: float = 0.88,
    ) -> np.ndarray:
        """
        Apply *style_name* to every finger in *nail_masks* and return a new BGR image.

        Parameters
        ----------
        image_bgr : np.ndarray
            Original hand photo (BGR, uint8).
        nail_masks : dict
            Per-finger binary masks  {finger_name: (H,W) uint8}.
        style_name : str
            Key from NAIL_STYLES.
        opacity : float
            Blend strength (0 = invisible, 1 = fully opaque).
        """
        if style_name not in self.styles:
            raise ValueError(f"Unknown style '{style_name}'. Available: {list(self.styles)}")

        style = self.styles[style_name]
        result = image_bgr.copy()

        # Pre-blur the frame once — every nail "reflects" the same soft
        # environment instead of redoing an expensive blur per finger.
        env_layer = cv2.GaussianBlur(image_bgr, (25, 25), 15)

        for finger, mask in nail_masks.items():
            if mask is None or mask.max() == 0:
                continue
            result = self._apply_one_nail(result, mask, style, opacity, env_layer=env_layer)

        # Global detail pass — gentle edge-aware enhancement so the whole
        # composite reads as one photograph rather than a render pasted
        # onto a photo.
        result = cv2.detailEnhance(result, sigma_s=12, sigma_r=0.18)

        return result

    def get_recommended_styles(self, skin_type: str) -> List[str]:
        return SKIN_RECOMMENDATIONS.get(skin_type, SKIN_RECOMMENDATIONS["neutral"])

    def style_swatch(self, style_name: str, size: Tuple[int, int] = (100, 60)) -> np.ndarray:
        """Return a small BGR swatch image for a style (used in UI previews)."""
        w, h = size
        style = self.styles[style_name]
        swatch = np.full((h, w, 3), style["bgr"], dtype=np.uint8)
        swatch = self._apply_pattern(swatch, style["pattern"], style["bgr"])
        return swatch

    # ------------------------------------------------------------------
    # Core rendering helpers
    # ------------------------------------------------------------------

    def _apply_one_nail(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        style: Dict,
        opacity: float,
        env_layer: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        h, w = image.shape[:2]

        # ── 1. Alpha channel: hard core + soft edge ───────────────────
        # Erode to get the solid inner region, soft-blend only the edges
        k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        inner = cv2.erode(mask, k5, iterations=2)

        # Inner region gets full opacity; edge zone fades
        alpha_hard  = inner.astype(np.float32) / 255.0
        edge        = cv2.GaussianBlur(
            (mask.astype(np.float32) - inner.astype(np.float32)),
            (5, 5), 1.5
        ) / 255.0
        alpha = np.clip(alpha_hard * 0.95 + edge * 0.60, 0.0, 1.0) * opacity
        alpha3 = alpha[:, :, np.newaxis]

        # ── 2. Build nail colour layer ────────────────────────────────
        base_color = np.full((h, w, 3), style["bgr"], dtype=np.uint8)
        nail_layer = self._apply_pattern(base_color, style["pattern"], style["bgr"])

        # ── 2b. Skin-tone blending ─────────────────────────────────────
        # Sample the live skin in a thin ring just outside the nail and
        # fold a touch of it into the polish colour, so the result reads
        # as polish sitting on *this* finger rather than a flat sticker
        # that ignores the surrounding skin tone / ambient cast.
        k_ring  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        dilated = cv2.dilate(mask, k_ring, iterations=1)
        ring    = cv2.bitwise_and(dilated, cv2.bitwise_not(mask))
        if ring.max() > 0:
            avg_skin = cv2.mean(image, mask=ring)[:3]
            skin_layer = np.empty_like(nail_layer)
            skin_layer[:] = avg_skin
            nail_layer = cv2.addWeighted(nail_layer, 0.90, skin_layer, 0.10, 0)

        # ── 3. Specular highlight (light-direction aware) ─────────────
        nail_layer = self._add_highlight(nail_layer, mask)

        # ── 3b. Environment reflection ─────────────────────────────────
        # Glossy polish mirrors a soft, blurred version of its surroundings
        # rather than staying a flat, context-blind colour swatch.
        if env_layer is not None:
            nail_layer = cv2.addWeighted(nail_layer, 0.85, env_layer, 0.15, 0)

        # ── 3c. Nail-thickness rim ─────────────────────────────────────
        # Brighten a soft band along the mask outline so the polish reads
        # as a layer with real depth sitting atop the nail bed, instead of
        # paint fused perfectly flat to it. Blended (not hard-replaced) so
        # the rim fades smoothly rather than leaving a visible seam.
        edge_mask = cv2.Canny(mask, 50, 150)
        if edge_mask.max() > 0:
            edge_mask = cv2.dilate(edge_mask, np.ones((3, 3), np.uint8), iterations=1)
            edge_mask = cv2.GaussianBlur(edge_mask, (5, 5), 1.2)
            rim = (edge_mask.astype(np.float32) / 255.0)[:, :, np.newaxis] * 0.35
            nail_layer = np.clip(
                nail_layer.astype(np.float32) * (1.0 - rim) + 255.0 * rim, 0, 255
            ).astype(np.uint8)

        # ── 4. Alpha-blend onto original ──────────────────────────────
        result = (
            image.astype(np.float32) * (1.0 - alpha3)
            + nail_layer.astype(np.float32) * alpha3
        ).astype(np.uint8)

        return result

    # ------------------------------------------------------------------
    # Pattern generators  (all operate on a full-image layer, masked later)
    # ------------------------------------------------------------------

    def _apply_pattern(
        self, layer: np.ndarray, pattern: str, base_bgr: Tuple
    ) -> np.ndarray:
        if pattern == "shimmer":
            return self._shimmer(layer)
        if pattern == "metallic":
            return self._metallic(layer)
        if pattern == "glitter":
            return self._glitter(layer)
        if pattern == "french":
            return self._french(layer, base_bgr)
        return layer  # solid

    def _shimmer(self, layer: np.ndarray) -> np.ndarray:
        h, w = layer.shape[:2]
        noise = np.random.normal(0, 18, (h, w, 3)).astype(np.float32)
        return np.clip(layer.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    def _metallic(self, layer: np.ndarray) -> np.ndarray:
        h = layer.shape[0]
        # vertical gradient: darker at base, lighter in middle, darker at tip
        t = np.linspace(0, np.pi, h, dtype=np.float32)
        gradient = (0.75 + 0.40 * np.sin(t))[:, np.newaxis, np.newaxis]
        return np.clip(layer.astype(np.float32) * gradient, 0, 255).astype(np.uint8)

    def _glitter(self, layer: np.ndarray) -> np.ndarray:
        out = layer.copy()
        h, w = out.shape[:2]
        n_sparkles = max(300, h * w // 80)
        xs = np.random.randint(0, w, n_sparkles)
        ys = np.random.randint(0, h, n_sparkles)
        brightness = np.random.randint(160, 256, n_sparkles)
        for x, y, b in zip(xs, ys, brightness):
            out[y, x] = (b, b, b)
        return out

    def _french(self, layer: np.ndarray, base_bgr: Tuple) -> np.ndarray:
        h, w = layer.shape[:2]
        # Base = warm nude
        nude_bgr = (190, 210, 225)
        out = np.full_like(layer, nude_bgr)
        # White tip = top 28 % of the layer
        tip_rows = max(1, int(h * 0.28))
        out[:tip_rows, :] = (250, 255, 255)
        # Soft edge between nude and tip
        blend_rows = max(2, int(h * 0.06))
        for i in range(blend_rows):
            t = i / blend_rows
            out[tip_rows + i, :] = (
                int(250 * (1 - t) + nude_bgr[0] * t),
                int(255 * (1 - t) + nude_bgr[1] * t),
                int(255 * (1 - t) + nude_bgr[2] * t),
            )
        return out

    # ------------------------------------------------------------------
    # Highlight pass
    # ------------------------------------------------------------------

    def _add_highlight(self, layer: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Add a directional specular highlight where a real light source
        would catch a glossy, convex nail surface.

        The highlight centre is offset from the nail's centroid along
        ``self.light_dir`` (rather than pinned to a fixed upper-centre
        point) — that off-centre placement plus a soft Gaussian falloff
        is what reads as "wet gloss catching the light" instead of a
        painted-on white oval.
        """
        rows = np.where(mask > 0)[0]
        cols = np.where(mask > 0)[1]
        if len(rows) == 0:
            return layer

        top, bottom = rows.min(), rows.max()
        left, right = cols.min(), cols.max()
        nail_h = max(1, bottom - top)
        nail_w = max(1, right - left)

        cx = int(np.mean(cols) + self.light_dir[0] * nail_w * 0.28)
        cy = int(np.mean(rows) + self.light_dir[1] * nail_h * 0.28)

        axes_x = max(2, int(nail_w * 0.16))
        axes_y = max(2, int(nail_h * 0.10))

        # Outer soft glow + inner bright spot, each Gaussian-blurred so
        # the highlight fades smoothly rather than ending in a hard rim.
        for scale, alpha in [(2.0, 0.18), (1.0, 0.32)]:
            axes = (max(2, int(axes_x * scale)), max(2, int(axes_y * scale)))
            hl = layer.copy()
            cv2.ellipse(hl, (cx, cy), axes, 0, 0, 360, (255, 255, 255), -1)
            hl = cv2.GaussianBlur(hl, (0, 0), sigmaX=max(axes) * 0.35)
            layer = cv2.addWeighted(layer, 1 - alpha, hl, alpha, 0)

        return layer


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    renderer = NailRenderer()

    dummy_img = np.full((480, 640, 3), (200, 180, 160), dtype=np.uint8)
    dummy_mask = np.zeros((480, 640), dtype=np.uint8)
    cv2.ellipse(dummy_mask, (320, 120), (25, 40), 0, 0, 360, 255, -1)

    for style_name in list(NAIL_STYLES)[:3]:
        out = renderer.render(dummy_img, {"index": dummy_mask}, style_name)
        print(f"Rendered '{style_name}' → shape {out.shape}, dtype {out.dtype}")

    print("Recommended for warm_yellow:", renderer.get_recommended_styles("warm_yellow"))
