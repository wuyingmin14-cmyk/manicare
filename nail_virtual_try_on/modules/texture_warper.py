"""
texture_warper.py
=================
NailArtRenderer — loads the style database (style_index.json) and renders
photorealistic nail art onto a user's hand using the colour-fill pipeline:

  1. Look up the style's per-finger dominant nail-art colour
  2. Fill the user's nail ellipse with that colour
  3. Specular gloss + edge shadow
  4. Alpha composite

(Module name kept for backward compatibility with app.py imports.)
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modules.nail_transfer import render_all_nails, RENDER_ORDER
from modules.hand_embedding import (
    compute_hand_embedding, recommend_styles,
)

_ROOT          = Path(__file__).parent.parent
_INDEX_DEFAULT = _ROOT / "data" / "style_index.json"

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]


# ── Safe image I/O (CJK path safe) ───────────────────────────────────────────

def _load_img(rel_or_abs: str, unchanged: bool = False) -> Optional[np.ndarray]:
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = _ROOT / p
    if not p.exists():
        return None
    data  = p.read_bytes()
    arr   = np.frombuffer(data, np.uint8)
    flags = cv2.IMREAD_UNCHANGED if unchanged else cv2.IMREAD_COLOR
    return cv2.imdecode(arr, flags)


# ── NailArtRenderer ───────────────────────────────────────────────────────────

class NailArtRenderer:
    """
    Photorealistic nail-art renderer backed by the style database.

    Usage
    -----
    renderer = NailArtRenderer()
    result   = renderer.render(hand_bgr, nail_masks, nail_info,
                               style_idx=3, opacity=0.95)
    thumbs   = renderer.get_thumbnails()      # [(rgb_ndarray, caption), ...]
    top5     = renderer.recommend(skin_type, hand_type, nail_info)
    """

    def __init__(self, index_path: Optional[str] = None):
        self.styles: List[Dict] = []
        self._thumb_cache:  List[Tuple[np.ndarray, str]]    = []
        self._embeddings:   List[np.ndarray]                = []

        p = Path(index_path) if index_path else _INDEX_DEFAULT
        if p.exists():
            with open(p, encoding="utf-8") as f:
                self.styles = json.load(f)
            print(f"[NailArtRenderer] {len(self.styles)} styles loaded")
            self._build_caches()
        else:
            print(f"[NailArtRenderer] No index at {p}. Run build_style_db.py first.")

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def num_styles(self) -> int:
        return len(self.styles)

    def get_thumbnails(self) -> List[Tuple[np.ndarray, str]]:
        return self._thumb_cache

    def recommend(
        self,
        skin_type: str,
        hand_type: str,
        nail_info: Dict,
        k: int = 5,
        exclude: Optional[set] = None,
    ) -> List[int]:
        """Return top-k style indices ordered by compatibility.

        *exclude* lets the feedback loop drop styles the user has already
        rejected ("不喜欢/太假/颜色不合适") from future recommendations.
        """
        if not self._embeddings:
            return list(range(min(k, len(self.styles))))
        hand_emb = compute_hand_embedding(skin_type, hand_type, nail_info)
        return recommend_styles(hand_emb, self._embeddings, k=k,
                                skin_type=skin_type, hand_type=hand_type,
                                exclude=exclude)

    def render(
        self,
        hand_bgr: np.ndarray,
        nail_masks: Dict[str, np.ndarray],
        nail_info: Dict[str, Dict],
        style_idx: int,
        opacity: float = 1.0,
        hand_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Apply style *style_idx* from the database to all detected nails.
        Returns a new BGR image.
        """
        if style_idx >= len(self.styles) or not self.styles:
            return hand_bgr

        style    = self.styles[style_idx]
        colors   = self._get_colors(style)
        finishes = style.get("finishes", {})

        if not any(c is not None for c in colors.values()):
            return hand_bgr

        return render_all_nails(
            hand_bgr, colors, nail_info,
            finishes=finishes,
            hand_mask=hand_mask,
            opacity=opacity,
        )

    # ── Cache building ──────────────────────────────────────────────────────

    def _build_caches(self, thumb_size: Tuple[int, int] = (200, 270)):
        """Pre-load thumbnails and embeddings for all styles."""
        self._thumb_cache = []
        self._embeddings  = []

        for s in self.styles:
            # Thumbnail
            img = _load_img(s.get("thumb_path", ""))
            if img is None:
                img = _load_img(s.get("raw_path", ""))
            if img is not None:
                h, w  = img.shape[:2]
                scale = min(thumb_size[0] / w, thumb_size[1] / h)
                thumb = cv2.resize(img, (max(1, int(w * scale)),
                                         max(1, int(h * scale))))
                rgb   = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
                self._thumb_cache.append((rgb, f"款式 {s['id']}"))

            # Embedding
            emb = s.get("embedding")
            if emb and len(emb) >= 13:
                self._embeddings.append(np.array(emb, dtype=np.float32))
            else:
                self._embeddings.append(np.zeros(13, dtype=np.float32))

    # ── Colour lookup ────────────────────────────────────────────────────────

    def _get_colors(self, style: Dict) -> Dict[str, Optional[Tuple[float, float, float]]]:
        """Return {finger: (B, G, R) or None} for one style, with fallback."""
        dom = style.get("dominant_colors", {})
        colors: Dict[str, Optional[Tuple[float, float, float]]] = {}

        # Pick a fallback colour from any finger that has one
        fallback = None
        for fname in FINGER_NAMES:
            c = dom.get(fname)
            if c and len(c) == 3:
                fallback = tuple(float(x) for x in c)
                break

        for fname in FINGER_NAMES:
            c = dom.get(fname)
            if c and len(c) == 3:
                colors[fname] = tuple(float(x) for x in c)
            else:
                colors[fname] = fallback

        return colors
