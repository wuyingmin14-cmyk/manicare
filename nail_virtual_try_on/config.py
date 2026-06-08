# Configuration for AI Nail Virtual Try-On System

import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "cache"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Create directories if not exist
for dir_path in [DATA_DIR, CACHE_DIR, OUTPUT_DIR]:
    dir_path.mkdir(exist_ok=True)

# Color space conversions
COLOR_SPACES = {
    'HSV': 'HSV',
    'LAB': 'LAB',
    'RGB': 'RGB',
}

# Skin tone classification thresholds
SKIN_TONE_THRESHOLDS = {
    'hue_warm_min': 10,      # Warm tones (red-yellow range)
    'hue_warm_max': 40,
    'hue_cool_min': 270,     # Cool tones (blue-purple range)
    'hue_cool_max': 360,
    'brightness_dark': 50,   # V value threshold for dark skin
    'brightness_light': 180,  # V value threshold for light skin
}

# Hand shape classification parameters
HAND_SHAPE_PARAMS = {
    'short_wide_threshold': 2.0,   # ratio < 2.0: short and wide
    'long_thin_threshold': 3.0,    # ratio > 3.0: long and thin
}

# Nail shape types
NAIL_SHAPES = {
    'square': 'square',
    'round': 'round',
    'oval': 'oval',
    'almond': 'almond',
    'coffin': 'coffin',
}

# Nail shape recommendations based on hand type
NAIL_SHAPE_RECOMMENDATIONS = {
    'short_wide': ['oval', 'round'],           # Visual elongation
    'long_thin': ['square', 'round'],          # Balance
    'standard': ['oval', 'almond', 'coffin'],  # Universal
}

# Color recommendation rules
COLOR_RECOMMENDATION_RULES = {
    'warm_yellow': {
        'high_contrast': ['cool_pink', 'deep_blue', 'purple'],
        'harmonious': ['warm_red', 'coral', 'peach'],
    },
    'cool_white': {
        'high_contrast': ['wine_red', 'deep_purple', 'forest_green'],
        'harmonious': ['cool_pink', 'lavender', 'nude'],
    },
    'dark_skin': {
        'high_contrast': ['bright_red', 'gold', 'neon_colors'],
        'harmonious': ['bronze', 'warm_brown', 'deep_burgundy'],
    },
}

# Color database constants
COLOR_DB_VERSION = "1.0"
COLOR_DB_PATH = CACHE_DIR / "style_color_db.json"
HAND_DATASET_PATH = CACHE_DIR / "hand_dataset.json"
HAND_LANDMARKS_CACHE = CACHE_DIR / "hand_landmarks.json"

# Processing parameters
KMEANS_CLUSTERS = 5  # For dominant color extraction
HSV_BINS = (8, 8, 8)  # Histogram bins for HSV
MIN_HAND_AREA = 1000  # Minimum hand detection area

# Performance
CACHE_RESULTS = True
ENABLE_GPU = False  # Set to True if CUDA available

# Recommendation parameters
TOP_N_RECOMMENDATIONS = 5
SIMILARITY_THRESHOLD = 0.3

# config loaded
