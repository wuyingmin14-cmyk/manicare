# AI Nail Virtual Try-On System
# Main package initialization

__version__ = "1.0.0"
__author__ = "AI Nail Team"
__license__ = "MIT"

# Import main components
from pipeline import NailRecommendationPipeline
from modules.skin_analysis import SkinAnalyzer
from modules.hand_shape_analysis import HandShapeAnalyzer
from modules.nail_shape_transform import NailShapeTransformer
from modules.color_database import ColorDatabase
from modules.recommendation_engine import RecommendationEngine
from modules.data_loader import DataLoader

# Public API
__all__ = [
    'NailRecommendationPipeline',
    'SkinAnalyzer',
    'HandShapeAnalyzer',
    'NailShapeTransformer',
    'ColorDatabase',
    'RecommendationEngine',
    'DataLoader',
]

# Package metadata
__doc__ = """
AI Nail Virtual Try-On System
=============================

A complete AI-powered nail virtual try-on system featuring:
- Automatic skin tone detection and color recommendation
- Hand shape analysis and nail shape recommendation
- Nail shape geometric transformation
- Comprehensive color database and matching
- End-to-end recommendation pipeline

Quick Start
-----------
    from nail_virtual_try_on import NailRecommendationPipeline
    
    pipeline = NailRecommendationPipeline()
    recommendation = pipeline.recommend_nails(hand_image)
    print(recommendation['report'])

Documentation
--------------
See INTEGRATION_GUIDE.md for complete documentation and examples.
"""

print(f"✓ AI Nail Virtual Try-On v{__version__} loaded")
