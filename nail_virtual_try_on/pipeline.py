# Complete Pipeline Module
# Integrates all modules for end-to-end nail recommendation

import cv2
import numpy as np
from typing import Dict, Optional, Tuple, List
import json
from pathlib import Path

from modules.skin_analysis import SkinAnalyzer
from modules.hand_shape_analysis import HandShapeAnalyzer
from modules.nail_shape_transform import NailShapeTransformer
from modules.color_database import ColorDatabase
from modules.recommendation_engine import RecommendationEngine

class NailRecommendationPipeline:
    """
    Complete pipeline for personalized nail recommendations
    """
    
    def __init__(self, 
                 color_db_path: Optional[str] = None,
                 cache_dir: str = './cache'):
        """
        Initialize pipeline with all modules
        
        Args:
            color_db_path: Path to color database JSON
            cache_dir: Cache directory
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize modules
        self.skin_analyzer = SkinAnalyzer()
        self.hand_analyzer = HandShapeAnalyzer()
        self.nail_transformer = NailShapeTransformer()
        
        # Initialize color database
        self.color_database = ColorDatabase(cache_dir=cache_dir)
        if color_db_path and Path(color_db_path).exists():
            self.color_database.load_database(color_db_path)
        
        # Initialize recommendation engine
        self.recommendation_engine = RecommendationEngine(self.color_database)
        
        print("鉁?NailRecommendationPipeline initialized")
    
    def recommend_nails(self,
                       hand_image: np.ndarray,
                       hand_mask: Optional[np.ndarray] = None,
                       landmarks: Optional[np.ndarray] = None,
                       nail_masks: Optional[Dict[str, np.ndarray]] = None) -> Dict:
        """
        Generate personalized nail recommendations
        
        Args:
            hand_image: Hand image (BGR)
            hand_mask: Binary mask of hand region (optional)
            landmarks: 21 hand landmarks from MediaPipe (optional)
            nail_masks: Dictionary of per-finger nail masks (optional)
        
        Returns:
            Comprehensive recommendation dictionary
        """
        recommendations = {
            'status': 'success',
            'components': {}
        }
        
        try:
            # 1. Skin tone analysis
            print("Step 1: Analyzing skin tone...")
            skin_analysis = self.skin_analyzer.analyze(hand_image, hand_mask)
            recommendations['components']['skin_analysis'] = {
                'skin_type': skin_analysis['tone_classification']['skin_type'],
                'avg_hsv': skin_analysis['color_stats']['avg_hsv'],
            }
            
            # 2. Hand shape analysis (if landmarks provided)
            if landmarks is not None:
                print("Step 2: Analyzing hand shape...")
                hand_analysis = self.hand_analyzer.analyze(landmarks)
                recommendations['components']['hand_analysis'] = {
                    'hand_type': hand_analysis['classification']['hand_type'],
                    'average_ratio': hand_analysis['classification']['average_ratio'],
                }
            else:
                print("鈿?No landmarks provided, using default hand type")
                # Use default hand type
                hand_analysis = {
                    'classification': {'hand_type': 'standard', 'average_ratio': 2.5},
                    'nail_shape_recommendations': {
                        'primary_recommendation': 'oval',
                        'secondary_options': ['almond', 'coffin'],
                        'reasoning': 'Default recommendation'
                    }
                }
            
            # 3. Nail shape transformation (if nail masks provided)
            if nail_masks is not None:
                print("Step 3: Generating nail shape previews...")
                nail_shape = hand_analysis['nail_shape_recommendations']['primary_recommendation']
                transformed_masks = self.nail_transformer.transform_nail_set(
                    nail_masks, 
                    nail_shape
                )
                recommendations['components']['nail_transform'] = {
                    'recommended_shape': nail_shape,
                    'transformed_masks': {k: v.shape for k, v in transformed_masks.items()}
                }
            
            # 4. Generate recommendations
            print("Step 4: Generating personalized recommendations...")
            final_recommendations = self.recommendation_engine.generate_recommendations(
                skin_analysis,
                hand_analysis
            )
            
            recommendations['recommendations'] = final_recommendations
            
            # 5. Color style recommendations (if database loaded)
            if self.color_database.db:
                print("Step 5: Finding compatible styles...")
                avg_hsv = skin_analysis['color_stats']['avg_hsv']
                
                high_contrast = self.color_database.find_compatible_styles(
                    avg_hsv,
                    search_type='high_contrast',
                    top_n=5
                )
                harmonious = self.color_database.find_compatible_styles(
                    avg_hsv,
                    search_type='harmonious',
                    top_n=5
                )
                
                recommendations['style_recommendations'] = {
                    'high_contrast': high_contrast,
                    'harmonious': harmonious,
                }
            
            # Generate report
            print("\n鉁?Recommendations generated successfully!")
            report = self.recommendation_engine.generate_report(final_recommendations)
            recommendations['report'] = report
            
            return recommendations
        
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'error_type': type(e).__name__
            }
    
    def batch_recommend(self, 
                       hand_images: List[Dict]) -> List[Dict]:
        """
        Generate recommendations for multiple hand images
        
        Args:
            hand_images: List of dictionaries with 'image', 'mask', 'landmarks', 'nail_masks'
        
        Returns:
            List of recommendations
        """
        results = []
        
        for i, hand_data in enumerate(hand_images):
            print(f"\n{'='*60}")
            print(f"Processing image {i+1}/{len(hand_images)}")
            print('='*60)
            
            result = self.recommend_nails(
                hand_image=hand_data.get('image'),
                hand_mask=hand_data.get('mask'),
                landmarks=hand_data.get('landmarks'),
                nail_masks=hand_data.get('nail_masks')
            )
            
            results.append(result)
        
        return results
    
    def build_color_database_from_styles(self, 
                                        style_images: List[Dict]) -> None:
        """
        Build color database from style images
        
        Args:
            style_images: List of style dictionaries with 'id', 'image', 'url'
        """
        print("Building color database from styles...")
        
        for style in style_images:
            try:
                # Save image temporarily
                import tempfile
                temp_file = Path(tempfile.gettempdir()) / f"style_{style['id']}.jpg"
                cv2.imwrite(str(temp_file), style['image'])
                
                # Add to database
                self.color_database.add_style(
                    style_id=style['id'],
                    image_path=str(temp_file),
                    style_url=style.get('url', '')
                )
                
            except Exception as e:
                print(f"鈿?Error processing style {style['id']}: {e}")
                continue
        
        # Save database
        self.color_database.save_database()
        print(f"鉁?Color database built with {len(self.color_database.db)} styles")
    
    def export_results(self, 
                      recommendations: Dict, 
                      output_dir: str = './output') -> None:
        """
        Export recommendations to JSON
        
        Args:
            recommendations: Recommendations dictionary
            output_dir: Output directory
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Remove non-serializable objects
        clean_data = self._serialize_recommendations(recommendations)
        
        output_path = output_dir / 'recommendations.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False)
        
        print(f"鉁?Results exported to {output_path}")
    
    def _serialize_recommendations(self, obj):
        """Convert recommendations to JSON-serializable format"""
        if isinstance(obj, dict):
            return {k: self._serialize_recommendations(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_recommendations(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        else:
            return obj


# Example usage
if __name__ == "__main__":
    # Initialize pipeline
    pipeline = NailRecommendationPipeline()
    
    # Create test image
    test_img = np.uint8(np.random.rand(500, 500, 3) * 255)
    
    # Generate recommendations
    result = pipeline.recommend_nails(test_img)
    print(json.dumps(result, indent=2, default=str))

