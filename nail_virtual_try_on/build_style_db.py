"""
build_style_db.py
=================
One-time script: reads DATA.xlsx, downloads all 25 raw-style images,
runs MediaPipe hand detection, samples each finger's DOMINANT NAIL-ART
COLOUR, and saves a style_index.json.

All paths are stored RELATIVE to this script's directory so that the
index survives moving the project (avoids Chinese-character path issues).

Usage:
    python build_style_db.py
"""

import sys
from pathlib import Path

ROOT        = Path(__file__).parent          # always correct even with CJK in cwd
DATA_XLSX   = ROOT.parent / "DATA.xlsx"
STYLES_DIR  = ROOT / "data" / "styles"
INDEX_PATH  = ROOT / "data" / "style_index.json"

sys.path.insert(0, str(ROOT))

import json
import requests
import cv2
import numpy as np
import pandas as pd

from modules.style_extractor import (
    FINGER_NAMES, extract_dominant_color, fallback_dominant_color,
)
from modules.hand_embedding import compute_style_embedding


# ── I/O helpers that bypass cv2 CJK-path bugs ────────────────────────────────

def _save_img(path: Path, img: np.ndarray, ext: str = ".jpg") -> bool:
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    path.write_bytes(buf.tobytes())
    return True


def _load_img(path: Path) -> "np.ndarray | None":
    if not path.exists():
        return None
    data = path.read_bytes()
    arr  = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _load_img_unchanged(path: Path) -> "np.ndarray | None":
    """Load with alpha channel preserved (for PNG)."""
    if not path.exists():
        return None
    data = path.read_bytes()
    arr  = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)


def _download(url: str, timeout: int = 20) -> "bytes | None":
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"    WARN download failed ({url[:60]}...): {e}")
        return None


def _decode(data: bytes) -> "np.ndarray | None":
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


# ── Nail detection ────────────────────────────────────────────────────────────

def _detect_nails(img: np.ndarray) -> "dict | None":
    from modules.hand_detector import HandDetector
    det    = HandDetector()
    result = det.detect(img)
    if not result["detected"]:
        return None
    hand = result["hands"][0]
    return {"nail_info": hand["nail_info"]}


# ── Main build ────────────────────────────────────────────────────────────────

def build_style_db():
    STYLES_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading DATA.xlsx ...")
    xl     = pd.read_excel(str(DATA_XLSX), sheet_name=None, header=0)
    sheets = list(xl.values())
    df_styles = sheets[1]          # Sheet2: [id, raw_url, enh_url]
    print(f"Found {len(df_styles)} style entries.\n")

    style_index = []

    for _, row in df_styles.iterrows():
        sid     = int(row.iloc[0])
        raw_url = str(row.iloc[1]).strip()
        enh_url = str(row.iloc[2]).strip()

        # ── 1. Download / load raw style image (as raw bytes) ────────────
        raw_path = STYLES_DIR / f"style_{sid:03d}_raw.jpg"
        if raw_path.exists():
            img = _load_img(raw_path)
        else:
            print(f"[{sid:3d}] Downloading raw style...")
            data = _download(raw_url)
            if data is None:
                continue
            raw_path.write_bytes(data)
            img = _decode(data)

        if img is None:
            print(f"[{sid:3d}] Could not load image, skipping.")
            continue

        # ── 2. Download enhanced image ───────────────────────────────────
        enh_path = STYLES_DIR / f"style_{sid:03d}_enh.jpg"
        if not enh_path.exists():
            data_enh = _download(enh_url)
            if data_enh:
                enh_path.write_bytes(data_enh)

        # ── 3. Gallery thumbnail (shorter side → 320px) ──────────────────
        thumb_path = STYLES_DIR / f"style_{sid:03d}_thumb.jpg"
        if not thumb_path.exists():
            h, w  = img.shape[:2]
            scale = 320 / min(h, w)
            thumb = cv2.resize(img, (int(w * scale), int(h * scale)))
            _save_img(thumb_path, thumb)

        # ── 4. Detect nails & sample dominant nail-art colour per finger ──
        det = _detect_nails(img)
        dominant_colors = {}
        color_analyses  = {}
        has_detection   = False

        if det is not None:
            has_detection = True
            nail_info     = det["nail_info"]
            for fname in FINGER_NAMES:
                color, analysis = extract_dominant_color(img, nail_info, fname)
                if color is not None:
                    dominant_colors[fname] = [round(c, 1) for c in color]
                    color_analyses[fname]  = analysis
            print(f"[{sid:3d}] Detection OK  colours: {list(dominant_colors.keys())}")
        else:
            # Fallback: sample a centre-crop colour for every finger
            print(f"[{sid:3d}] No detection  — centre-crop fallback colour")
            color, analysis = fallback_dominant_color(img)
            for fname in FINGER_NAMES:
                dominant_colors[fname] = [round(c, 1) for c in color]
                color_analyses[fname]  = analysis

        # ── 5. Compute style embedding from a representative finger ───────
        ref_analysis = (
            color_analyses.get("index")
            or color_analyses.get("middle")
            or next(iter(color_analyses.values()), None)
        )
        if ref_analysis:
            embedding = compute_style_embedding(ref_analysis).tolist()
        else:
            embedding = [0.0] * 13

        style_index.append({
            "id":               sid,
            "raw_url":          raw_url,
            "enh_url":          enh_url,
            "raw_path":         raw_path.relative_to(ROOT).as_posix(),
            "enh_path":         enh_path.relative_to(ROOT).as_posix()
                                if enh_path.exists() else "",
            "thumb_path":       thumb_path.relative_to(ROOT).as_posix(),
            "dominant_colors":  dominant_colors,    # {finger: [B, G, R]}
            "finishes":         color_analyses,     # {finger: {dominant_hsv, contrast,
                                                     #  saturation, pattern_score, glitter_score}}
            "embedding":        embedding,
            "has_detection":    has_detection,
        })

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(style_index, f, indent=2, ensure_ascii=False)

    n_det = sum(1 for s in style_index if s["has_detection"])
    print(f"\nDone!  {len(style_index)} styles saved "
          f"({n_det} with MediaPipe detection) -> {INDEX_PATH.name}")
    return style_index


if __name__ == "__main__":
    build_style_db()
