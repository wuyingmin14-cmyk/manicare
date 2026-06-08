"""
hand_embedding.py
=================
Computes feature embeddings for hands and nail styles,
then finds Top-K compatible styles via cosine similarity.

Hand embedding (dim = 13):
  [0:4]   skin_type one-hot   (warm_yellow, cool_white, dark_skin, neutral)
  [4:7]   hand_type one-hot   (short_wide, long_thin, standard)
  [7:10]  nail geometry       (norm_width, norm_height, aspect_ratio)
  [10:13] skin dominant HSV   (H/180, S/255, V/255)

Style embedding (dim = 13):
  [0:3]   dominant HSV        (H/180, S/255, V/255)
  [3:6]   contrast, saturation, pattern_score
  [6:9]   glitter_score, brightness_var, hue_var
  [9:13]  colour-category features (warm/cool/dark/neutral affinity)
"""

import numpy as np
import cv2
from typing import Dict, List, Optional

SKIN_TYPES = ["warm_yellow", "cool_white", "dark_skin", "neutral"]
HAND_TYPES = ["short_wide", "long_thin", "standard"]

# Complementary-colour weights: skin_type → style hue affinity
# Hue in [0,1] (normalised from [0,180])
# warm_yellow: prefer cool blues/purples (H≈0.55–0.80)
# cool_white : prefer rich deep reds/purples (H≈0.0–0.10 or 0.75–1.0)
# dark_skin  : prefer bright warm/vivid (H≈0.0–0.10 or 0.15–0.30)
# neutral    : balanced preference
_HUE_AFFINITY_CENTRES = {
    "warm_yellow": 0.66,   # blue-purple
    "cool_white":  0.94,   # deep red / magenta  (wraps around from 0)
    "dark_skin":   0.05,   # vivid red
    "neutral":     0.50,   # neutral mid
}
_HUE_AFFINITY_WEIGHTS = {
    "warm_yellow": 0.6,
    "cool_white":  0.5,
    "dark_skin":   0.5,
    "neutral":     0.2,
}


# ── Hand embedding ────────────────────────────────────────────────────────────

def compute_hand_embedding(
    skin_type: str,
    hand_type: str,
    nail_info: Dict,
    skin_dominant_hsv: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Return a 13-dim float32 feature vector for the user's hand."""

    # One-hot skin (4)
    sv = np.zeros(4, dtype=np.float32)
    if skin_type in SKIN_TYPES:
        sv[SKIN_TYPES.index(skin_type)] = 1.0

    # One-hot hand type (3)
    hv = np.zeros(3, dtype=np.float32)
    if hand_type in HAND_TYPES:
        hv[HAND_TYPES.index(hand_type)] = 1.0

    # Nail geometry (3)
    widths, heights = [], []
    for info in nail_info.values():
        if info and "axes" in info:
            ax_w, ax_h = info["axes"]
            widths.append(ax_w)
            heights.append(ax_h)

    if widths:
        aw = float(np.mean(widths))
        ah = float(np.mean(heights))
        ar = aw / max(ah, 1.0)
    else:
        aw = ah = 0.4
        ar = 1.0
    gv = np.array([
        float(np.clip(aw / 50.0, 0, 1)),
        float(np.clip(ah / 70.0, 0, 1)),
        float(np.clip(ar / 2.0,  0, 1)),
    ], dtype=np.float32)

    # Skin colour (3)
    if skin_dominant_hsv is not None and len(skin_dominant_hsv) >= 3:
        cv_ = np.clip(
            np.array(skin_dominant_hsv[:3], dtype=np.float32)
            / np.array([180.0, 255.0, 255.0]),
            0, 1
        )
    else:
        cv_ = np.zeros(3, dtype=np.float32)

    return np.concatenate([sv, hv, gv, cv_])   # shape (13,)


# ── Style embedding ───────────────────────────────────────────────────────────

def compute_style_embedding(
    patch_analysis: Dict,
) -> np.ndarray:
    """
    Return a 13-dim float32 vector from a patch analysis dict
    (produced by style_extractor.analyse_patch).
    """
    dom_hsv = patch_analysis.get("dominant_hsv", (0, 0, 128))
    dom_h   = float(dom_hsv[0]) / 180.0
    dom_s   = float(dom_hsv[1]) / 255.0
    dom_v   = float(dom_hsv[2]) / 255.0

    contrast      = float(np.clip(patch_analysis.get("contrast",      0.0), 0, 2)) / 2.0
    saturation    = float(np.clip(patch_analysis.get("saturation",    0.0), 0, 1))
    pattern_score = float(np.clip(patch_analysis.get("pattern_score", 0.0), 0, 1))
    glitter_score = float(np.clip(patch_analysis.get("glitter_score", 0.0), 0, 1))

    # Extra hue/val variance (to distinguish gradient vs solid)
    hue_var  = float(np.clip(contrast * 0.5, 0, 1))
    bright_v = float(np.clip(dom_v,          0, 1))

    # Colour-affinity features (4): how well does this style fit each skin type?
    affinity = np.zeros(4, dtype=np.float32)
    for i, stype in enumerate(SKIN_TYPES):
        centre = _HUE_AFFINITY_CENTRES[stype]
        weight = _HUE_AFFINITY_WEIGHTS[stype]
        # Circular hue distance
        d = abs(dom_h - centre)
        d = min(d, 1.0 - d)          # wrap around
        affinity[i] = weight * float(np.exp(-8 * d * d))

    return np.concatenate([
        [dom_h, dom_s, dom_v],
        [contrast, saturation, pattern_score],
        [glitter_score, hue_var, bright_v],
        affinity,
    ]).astype(np.float32)   # shape (13,)


# ── Similarity + recommendation ───────────────────────────────────────────────

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ── Hand-type affinity ────────────────────────────────────────────────────────
#
# We have no labelled "this style suits hand-shape X" data, so we use a
# defensible visual heuristic based on the style's own colour/pattern profile
# (brightness, saturation, pattern strength — all already in its embedding):
#
#   short_wide (短圆手型): simple, light, low-contrast colours visually
#       lengthen short/wide fingers — busy patterns draw the eye and make
#       fingers look stubbier.
#   long_thin  (细长手型): already-elongated slender fingers can carry bold
#       colour, deep tones and patterns without looking cluttered — and
#       benefit from the added visual interest / balance.
#   standard   (标准手型): no strong correction needed — favour balanced,
#       moderate-saturation, moderate-pattern styles that suit most hands.

def _hand_type_affinity(style_embedding: np.ndarray, hand_type: str) -> float:
    if len(style_embedding) < 6:
        return 0.5
    dom_v      = float(style_embedding[2])    # brightness  [0,1]
    saturation = float(style_embedding[4])
    pattern    = float(style_embedding[5])

    if hand_type == "short_wide":
        score = 0.55 * dom_v + 0.45 * (1.0 - pattern)
    elif hand_type == "long_thin":
        score = 0.5 * saturation + 0.5 * pattern
    else:  # standard / unknown
        score = 1.0 - 0.6 * abs(dom_v - 0.55) - 0.4 * abs(pattern - 0.4)

    return float(np.clip(score, 0.0, 1.0))


def recommend_styles(
    hand_embedding: np.ndarray,
    style_embeddings: List[np.ndarray],
    k: int = 5,
    skin_type: str = "neutral",
    hand_type: str = "standard",
    exclude: Optional[set] = None,
) -> List[int]:
    """
    Return indices (into *style_embeddings*) of the top-k recommended styles.

    Scoring combines three signals so the result actually reflects the
    user's analysed profile rather than just visual nearest-neighbour:
      - cosine similarity between hand and style embeddings   (general fit)
      - skin-tone colour affinity                             (肤色适配)
      - hand-shape colour/pattern affinity                    (手型适配)

    A secondary validation pass then prefers candidates that clear a basic
    affinity bar on at least one of the two profile dimensions, falling
    back to the raw ranking only if too few candidates qualify (so we
    always return k results even for small databases).

    *exclude* — indices to drop before ranking (e.g. styles the user has
    already marked "不喜欢/太假/颜色不合适" via the feedback loop), so the
    next recommendation round doesn't keep resurfacing rejected looks.
    """
    if not style_embeddings:
        return list(range(min(k, len(style_embeddings))))

    exclude = exclude or set()
    skin_idx = SKIN_TYPES.index(skin_type) if skin_type in SKIN_TYPES else 3

    scored = []
    for i, se in enumerate(style_embeddings):
        if i in exclude:
            continue
        base_sim = _cosine_sim(hand_embedding, se[:13])
        skin_aff = float(se[9 + skin_idx]) if len(se) >= 13 else 0.0
        hand_aff = _hand_type_affinity(se, hand_type)

        score = 0.35 * base_sim + 0.35 * skin_aff + 0.30 * hand_aff
        scored.append((score, skin_aff, hand_aff, i))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Secondary validation: drop candidates whose profile fit is weak on
    # BOTH dimensions (i.e. neither the skin nor the hand-shape affinity
    # clears a basic bar) — these are the "doesn't match the analysis"
    # results the matching pass is meant to filter out.
    AFFINITY_BAR = 0.22
    validated = [s for s in scored if s[1] >= AFFINITY_BAR or s[2] >= AFFINITY_BAR]
    pool = validated if len(validated) >= k else scored

    return [i for _, _, _, i in pool[:k]]
