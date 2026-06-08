"""
nail_transfer.py
================
Renders nail art onto a user's hand photo as a photoreal coloured fill that
mimics an actual manicure rather than a flat sticker.

Pipeline per finger
-------------------
1. Build a soft elliptical alpha mask over the user's nail (wide feather)
2. Sample the local ambient skin tone (acts as both a lighting reference and
   a reflected-light source — glossy nails pick up their surroundings)
3. Adapt the style's dominant colour to that local lighting/reflection
4. Fill with the adapted colour and apply CURVATURE SHADING — a directional
   gradient that simulates the convex, cylindrical surface of a real nail
   (bright ridge along the centre-line, darker toward the side walls)
5. Apply a MATERIAL-AWARE finish — glossy specular streak, soft matte
   diffuse, or sparkly glitter speckle — chosen from the style's analysed
   saturation / contrast / glitter score
6. Add edge shadow for nail-plate thickness, then bleed a little of the
   underlying skin tone into the rim so the transition from polish to
   cuticle/skin looks soft and natural rather than a cut-out silhouette
7. Alpha-composite onto the hand photo

Thumb handling
--------------
A thumb photographed near side-on has a near-square nail silhouette; we
narrow the fill ellipse horizontally so the polish matches that
foreshortened, perspective-correct shape instead of looking like an
oversized circle glued on top.
"""

import cv2
import numpy as np
from typing import Dict, Optional, Tuple


# ── Light analysis ────────────────────────────────────────────────────────────

def estimate_light_direction(
    hand_bgr: np.ndarray,
    hand_mask: Optional[np.ndarray] = None,
) -> Tuple[float, float]:
    """
    Very simple light-direction estimator: find the brightest region in the
    hand area (the skin specular), return its normalised (dx, dy) offset
    from the image centre.  Values in [-1, 1].
    """
    gray = cv2.cvtColor(hand_bgr, cv2.COLOR_BGR2GRAY)
    if hand_mask is not None:
        gray = cv2.bitwise_and(gray, gray, mask=hand_mask)

    smooth = cv2.GaussianBlur(gray, (31, 31), 0)
    _, _, _, max_loc = cv2.minMaxLoc(smooth)

    h, w = hand_bgr.shape[:2]
    dx = (max_loc[0] - w / 2.0) / (w / 2.0)
    dy = (max_loc[1] - h / 2.0) / (h / 2.0)
    return float(dx), float(dy)


# ── Curvature shading ─────────────────────────────────────────────────────────

def _apply_curvature_shading(
    layer: np.ndarray,
    alpha: np.ndarray,
    cx: int, cy: int,
    ax_w: int, ax_h: int,
    angle_deg: float,
    light_dy: float,
) -> np.ndarray:
    """
    Multiply the nail layer by a directional-gradient "shade map" that
    simulates a convex, cylindrical nail surface: brightest along the
    centre ridge (where the surface normal faces the camera), darker
    toward the side walls, with a faint longitudinal tilt toward the light.
    This is what makes a colour fill read as a curved 3-D nail rather than
    a flat decal.
    """
    h, w = layer.shape[:2]
    bx = min(w, int(ax_w * 2.4) + 1)
    by = min(h, int(ax_h * 1.6) + 1)
    x1, x2 = max(0, cx - bx), min(w, cx + bx)
    y1, y2 = max(0, cy - by), min(h, cy + by)
    if x2 <= x1 or y2 <= y1:
        return layer

    ys, xs = np.mgrid[y1:y2, x1:x2].astype(np.float32)
    r = np.deg2rad(-angle_deg)            # inverse rotation: image → local frame
    ca, sa = np.cos(r), np.sin(r)
    dx = xs - cx
    dy = ys - cy
    lx = dx * ca - dy * sa
    ly = dx * sa + dy * ca

    t = np.clip(lx / max(float(ax_w), 1.0), -1.3, 1.3)   # across-nail position
    u = np.clip(ly / max(float(ax_h), 1.0), -1.3, 1.3)   # along-nail position

    # Cylindrical cross-section: bright centre ridge, shaded side walls
    shade = 0.80 + 0.20 * np.power(np.cos(np.clip(t, -1.0, 1.0) * (np.pi / 2.0)), 1.3)
    # Faint longitudinal tilt toward the light source
    shade = shade * (1.0 + 0.05 * (-light_dy) * (-u))
    shade = np.clip(shade, 0.60, 1.18)[:, :, np.newaxis]

    region_alpha = alpha[y1:y2, x1:x2][:, :, np.newaxis]
    out = layer.astype(np.float32)
    region = out[y1:y2, x1:x2]
    region = region * (1.0 - region_alpha) + (region * shade) * region_alpha
    out[y1:y2, x1:x2] = region
    return np.clip(out, 0, 255).astype(np.uint8)


# ── Gloss, matte highlight & glitter ─────────────────────────────────────────

def _add_gloss(
    layer: np.ndarray,
    alpha: np.ndarray,
    cx: int, cy: int,
    ax_w: int, ax_h: int,
    angle_deg: float,
    light_dx: float = -0.3,
    light_dy: float = -0.4,
    strength: float = 1.0,
) -> np.ndarray:
    """Overlay a physically-plausible specular gloss streak following the light."""
    if strength <= 0.01:
        return layer

    h, w = layer.shape[:2]
    r = np.deg2rad(angle_deg)
    ca, sa = np.cos(r), np.sin(r)

    hl_lx = light_dx * ax_w * 0.55
    hl_ly = light_dy * ax_h * 0.60
    hl_x  = int(np.clip(cx + hl_lx * ca - hl_ly * sa, ax_w, w - ax_w - 1))
    hl_y  = int(np.clip(cy + hl_lx * sa + hl_ly * ca, ax_h, h - ax_h - 1))

    if alpha[hl_y, hl_x] < 0.05:
        return layer

    hl_rx = max(3, ax_w // 5)
    hl_ry = max(4, ax_h // 6)

    out = layer.copy().astype(np.float32)

    # Outer soft glow — wide, faint halo around the highlight zone
    g1 = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(g1, (hl_x, hl_y), (hl_rx * 3, hl_ry * 3), angle_deg, 0, 360, 1.0, -1)
    g1 = cv2.GaussianBlur(g1, (0, 0), float(max(1, hl_rx * 1.5)))
    g1 *= 0.06 * alpha * strength

    # Inner bright streak — an elongated soft-edged BAND running along the
    # nail's curve ridge (long axis), the way light rakes across a convex
    # gel surface, rather than an isolated round "dot" highlight.
    g2 = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(g2, (hl_x, hl_y), (max(2, hl_rx // 3), int(hl_ry * 2.6)),
                angle_deg, 0, 360, 1.0, -1)
    g2 = cv2.GaussianBlur(g2, (0, 0), float(max(1.2, hl_rx * 0.9)))
    g2 *= 0.16 * alpha * strength

    total = np.clip(g1 + g2, 0.0, 1.0)[:, :, np.newaxis]
    white = np.full_like(out, 255.0)
    out   = out * (1.0 - total) + white * total
    return np.clip(out, 0, 255).astype(np.uint8)


def _add_sparkle(
    layer: np.ndarray,
    alpha: np.ndarray,
    cx: int, cy: int,
    ax_w: int, ax_h: int,
    intensity: float,
    seed: int = 0,
) -> np.ndarray:
    """Scatter tiny bright speckles across the nail to read as glitter polish."""
    h, w = layer.shape[:2]
    bx, by = int(ax_w * 1.05) + 1, int(ax_h * 1.05) + 1
    x1, x2 = max(0, cx - bx), min(w, cx + bx)
    y1, y2 = max(0, cy - by), min(h, cy + by)
    if x2 <= x1 or y2 <= y1:
        return layer

    n_specks = int(np.clip(35 * intensity * (ax_w * ax_h) / 900.0, 6, 140))
    rng = np.random.RandomState(seed * 97 + 13)

    speck = np.zeros((h, w), dtype=np.float32)
    xs = rng.randint(x1, x2, size=n_specks)
    ys = rng.randint(y1, y2, size=n_specks)
    for sx, sy in zip(xs, ys):
        if alpha[sy, sx] < 0.35:
            continue
        rad = int(rng.choice([1, 1, 2]))
        cv2.circle(speck, (int(sx), int(sy)), rad, 1.0, -1)

    speck = cv2.GaussianBlur(speck, (3, 3), 0.55)
    total = np.clip(speck, 0, 1) * alpha
    total3 = total[:, :, np.newaxis] * 0.85

    out   = layer.astype(np.float32)
    white = np.full_like(out, 255.0)
    out   = out * (1.0 - total3) + white * total3
    return np.clip(out, 0, 255).astype(np.uint8)


def _add_edge_shadow(
    layer: np.ndarray,
    alpha: np.ndarray,
    shadow_depth: float = 0.10,
) -> np.ndarray:
    """
    Add a thin, soft shadow band at the nail edges — simulating the faint
    thickness of a real polish layer rather than a heavy cut-out outline.
    The edge band itself is Gaussian-blurred so the shadow has no hard rim.
    """
    alpha_u8 = (alpha * 255).astype(np.uint8)
    k        = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    inner    = cv2.erode(alpha_u8, k, iterations=2).astype(np.float32) / 255.0
    edge     = np.clip(alpha - inner, 0, 1)
    edge     = cv2.GaussianBlur(edge, (5, 5), 1.2)
    edge3    = edge[:, :, np.newaxis]

    dark = (layer.astype(np.float32) * (1.0 - shadow_depth))
    out  = layer.astype(np.float32) * (1.0 - edge3) + dark * edge3
    return np.clip(out, 0, 255).astype(np.uint8)


# ── Blend modes (multiply + soft-light) ──────────────────────────────────────

def _blend_multiply_soft_light(base_bgr: np.ndarray, overlay_bgr: np.ndarray,
                               mix: float = 0.5) -> np.ndarray:
    """
    Approximate Photoshop's "multiply + soft light" stacked blend: lets the
    underlying skin/nail luminance and fine texture show through the colour
    layer (so the result reads as polish *soaked into* the nail, not a flat
    sticker placed on top of it). Returns a float32 BGR image in [0, 255].
    """
    b = base_bgr.astype(np.float32) / 255.0
    o = overlay_bgr.astype(np.float32) / 255.0
    multiply = b * o
    soft = np.where(
        o <= 0.5,
        2 * b * o + b * b * (1.0 - 2 * o),
        2 * b * (1.0 - o) + np.sqrt(np.clip(b, 0.0, 1.0)) * (2 * o - 1.0),
    )
    blended = mix * multiply + (1.0 - mix) * soft
    return np.clip(blended * 255.0, 0, 255)


# ── Finish classification ─────────────────────────────────────────────────────

def _finish_params(finish: Optional[Dict]) -> Dict:
    """
    Translate a style's analysed colour descriptor into render parameters:
    glossy (default — strong specular), matte (soft, low specular) or
    glitter (sparkle speckle overlay), based on its saturation/contrast/
    glitter-score profile.
    """
    if not finish:
        return {"gloss_strength": 1.0, "glitter": 0.0}

    glitter    = float(finish.get("glitter_score", 0.0))
    saturation = float(finish.get("saturation", 0.0))
    contrast   = float(finish.get("contrast", 0.0))

    is_matte = saturation < 0.28 and contrast < 0.32 and glitter < 0.15
    # Matte/frosted polish has almost no specular streak — only the faintest
    # ambient diffuse sheen — while glossy gel/lacquer carries a full streak.
    gloss_strength = 0.12 if is_matte else 1.0

    return {"gloss_strength": gloss_strength, "glitter": glitter}


# ── Local lighting / colour adaptation ───────────────────────────────────────

def _sample_local_ambient(hand_bgr: np.ndarray, mask_u8: np.ndarray) -> np.ndarray:
    """Mean BGR of the skin ring just outside the nail — the local light/reflection source."""
    k    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    ring = cv2.bitwise_and(cv2.dilate(mask_u8, k, iterations=2), cv2.bitwise_not(mask_u8))
    ys, xs = np.where(ring > 0)
    if len(ys) < 20:
        return np.array([170.0, 180.0, 200.0], dtype=np.float32)
    return hand_bgr[ys, xs].astype(np.float32).mean(axis=0)


def _adapt_color_to_lighting(
    color_bgr: Tuple[float, float, float],
    ambient_bgr: np.ndarray,
) -> np.ndarray:
    """
    Shift the style's base colour to the finger's local lighting: brighten
    or darken it to match the ambient luminance, and blend in a touch of
    the surrounding skin tone (a glossy surface always reflects a hint of
    its surroundings) so the polish never looks like a "dead", flat colour
    pasted on top of the photo.
    """
    base    = np.array(color_bgr, dtype=np.float32)
    amb_lum = float(np.mean(ambient_bgr))
    lum_scale = float(np.clip(amb_lum / 150.0, 0.78, 1.22))

    adapted = base * (0.86 + 0.14 * lum_scale)
    adapted = adapted * 0.90 + ambient_bgr * 0.10
    return np.clip(adapted, 0, 255)


# ── Core fill & composite ────────────────────────────────────────────────────

# The MediaPipe nail ellipse is a conservative estimate of the nail PLATE;
# painted nails visually cover a larger oval reaching to the free edge and
# the side walls. Enlarge the fill region so the colour covers the whole
# visible nail rather than leaving a smaller disc in the centre.
_FILL_SCALE_W = 1.20
_FILL_SCALE_H = 1.45

# A thumb photographed close to side-on shows a near-square nail silhouette
# (width ≈ height in screen space). Narrow the fill horizontally to match
# that foreshortened shape instead of an oversized circular blob.
_THUMB_SIDEVIEW_RATIO   = 0.78
_THUMB_SIDEVIEW_NARROW  = 0.74


def apply_nail_color(
    hand_bgr: np.ndarray,
    color_bgr: Tuple[float, float, float],
    dst_nail_info: Dict,
    finish: Optional[Dict] = None,
    opacity: float = 1.0,
    light_dx: float = -0.3,
    light_dy: float = -0.4,
    is_thumb: bool = False,
    seed: int = 0,
) -> np.ndarray:
    """
    Fill the user's nail (described by *dst_nail_info*) with a photoreal
    rendering of *color_bgr*: lighting-adapted colour, curvature shading,
    a material-appropriate finish, edge shadow and soft skin blending.

    Returns a new BGR image.
    """
    H_img, W_img = hand_bgr.shape[:2]
    center    = dst_nail_info["center"]
    src_axes  = dst_nail_info["axes"]
    angle_deg = float(dst_nail_info["angle"])

    fill_w = float(src_axes[0]) * _FILL_SCALE_W
    fill_h = float(src_axes[1]) * _FILL_SCALE_H

    # ── Side-view / tilted-angle correction ───────────────────────────────
    # Prefer the detector's 3-D depth-based estimate (it sees the true
    # finger angle, not just the on-screen silhouette) and fall back to
    # the on-screen aspect-ratio heuristic when that's unavailable —
    # important for the thumb, whose nail is most often photographed
    # side-on / at a steep angle.
    foreshortening = float(dst_nail_info.get("foreshortening", 0.0))
    side_view = bool(dst_nail_info.get("is_side_view", False))
    if not side_view and is_thumb:
        ratio = float(src_axes[0]) / max(float(src_axes[1]), 1.0)
        side_view = ratio > _THUMB_SIDEVIEW_RATIO
        foreshortening = max(foreshortening, 0.5)
    if side_view:
        narrow = _THUMB_SIDEVIEW_NARROW if is_thumb else (1.0 - 0.20 * foreshortening)
        fill_w *= narrow

    ax_w, ax_h = max(4, int(round(fill_w))), max(6, int(round(fill_h)))
    cx = int(np.clip(round(center[0]), ax_w, W_img - ax_w - 1))
    cy = int(np.clip(round(center[1]), ax_h, H_img - ax_h - 1))

    # ── Mask: geometric ellipse from the detector's landmark estimate ─────
    # (We tried snapping this to a colour-distance segmentation of the real
    # nail silhouette — on real photos with uneven lighting, shadows, skin
    # folds and existing polish it produced jagged blobs that bled onto
    # the skin, a strictly worse result than the smooth ellipse. Without a
    # trained nail-segmentation model, the geometric estimate plus soft
    # feathering is the more robust choice — the same lesson that drove
    # this module away from texture-warping in the first place.)
    mask_u8 = np.zeros((H_img, W_img), dtype=np.uint8)
    cv2.ellipse(mask_u8, (cx, cy), (ax_w, ax_h), angle_deg, 0, 360, 255, -1)

    # ── Soft alpha mask — tight ~1-2px feather (natural edge, no hard cut) ─
    k     = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    inner = cv2.erode(mask_u8, k, iterations=1)
    alpha = cv2.GaussianBlur(inner.astype(np.float32), (5, 5), 1.0) / 255.0
    alpha = np.clip(alpha * opacity, 0.0, 1.0)

    # ── Sample local ambient light / reflection source from skin ring ─────
    ambient = _sample_local_ambient(hand_bgr, mask_u8)
    adapted = _adapt_color_to_lighting(color_bgr, ambient)

    nail_layer = np.empty_like(hand_bgr)
    nail_layer[:] = adapted.astype(np.uint8)

    # ── Curvature shading: makes a flat fill read as a convex 3-D nail ────
    nail_layer = _apply_curvature_shading(nail_layer, alpha, cx, cy, ax_w, ax_h,
                                           angle_deg, light_dy)

    # ── Material-aware finish (glossy / matte / glitter) ──────────────────
    fp = _finish_params(finish)
    nail_layer = _add_gloss(nail_layer, alpha, cx, cy, ax_w, ax_h, angle_deg,
                            light_dx=light_dx, light_dy=light_dy,
                            strength=fp["gloss_strength"])
    if fp["glitter"] > 0.18:
        nail_layer = _add_sparkle(nail_layer, alpha, cx, cy, ax_w, ax_h,
                                  intensity=fp["glitter"], seed=seed)

    nail_layer = _add_edge_shadow(nail_layer, alpha, shadow_depth=0.16)

    # ── Soft rim blending: bleed a little skin tone into the very edge ────
    # (simulates polish translucency / the natural cuticle transition —
    # avoids the "cut-out sticker" look of a hard silhouette edge)
    inner2   = cv2.erode((alpha * 255).astype(np.uint8), k, iterations=2).astype(np.float32) / 255.0
    rim      = np.clip(alpha - inner2, 0.0, 1.0)
    rim3     = (rim * 0.30)[:, :, np.newaxis]
    nail_f   = nail_layer.astype(np.float32)
    nail_f   = nail_f * (1.0 - rim3) + hand_bgr.astype(np.float32) * rim3
    nail_layer = np.clip(nail_f, 0, 255).astype(np.uint8)

    # ── Blend mode: multiply + soft light (not flat opaque overlay) ───────
    # Lets the underlying nail/skin's own fine texture and luminance
    # variation show through the colour — reads as polish soaked into the
    # nail surface rather than a flat decal pasted on top of the photo.
    blended = _blend_multiply_soft_light(hand_bgr, nail_layer, mix=0.45)
    texture_mix = 0.32
    nail_textured = (
        nail_layer.astype(np.float32) * (1.0 - texture_mix)
        + blended * texture_mix
    )

    # ── Alpha composite ────────────────────────────────────────────────────
    alpha3 = alpha[:, :, np.newaxis]
    result = (
        hand_bgr.astype(np.float32) * (1.0 - alpha3)
        + nail_textured * alpha3
    ).astype(np.uint8)

    return result


# ── Multi-finger renderer ────────────────────────────────────────────────────

RENDER_ORDER = ["pinky", "ring", "middle", "index", "thumb"]


def render_all_nails(
    hand_bgr: np.ndarray,
    colors: Dict[str, Optional[Tuple[float, float, float]]],   # finger → BGR colour
    nail_info: Dict,
    finishes: Optional[Dict[str, Optional[Dict]]] = None,      # finger → finish descriptor
    hand_mask: Optional[np.ndarray] = None,
    opacity: float = 1.0,
) -> np.ndarray:
    """Apply the style's colour & finish to all detected nails (far fingers first)."""
    light_dx, light_dy = estimate_light_direction(hand_bgr, hand_mask)
    finishes = finishes or {}

    result = hand_bgr.copy()
    for i, fname in enumerate(RENDER_ORDER):
        color = colors.get(fname)
        info  = nail_info.get(fname)
        if color is None or info is None or info.get("axes", (0, 0))[0] == 0:
            continue
        result = apply_nail_color(
            result, color, info,
            finish=finishes.get(fname),
            opacity=opacity,
            light_dx=light_dx,
            light_dy=light_dy,
            is_thumb=(fname == "thumb"),
            seed=i,
        )

    return result
