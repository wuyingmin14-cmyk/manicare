#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete End-to-End Example
Shows how to use the AI Nail Virtual Try-On system with mock data
"""

import numpy as np
import cv2
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.skin_analysis import SkinAnalyzer
from modules.hand_shape_analysis import HandShapeAnalyzer
from modules.nail_shape_transform import NailShapeTransformer
from modules.color_database import ColorDatabase
from modules.recommendation_engine import RecommendationEngine
from pipeline import NailRecommendationPipeline


def create_test_hand_image():
    """Create a test hand image with realistic skin tone"""
    # Create image with warm yellowish skin tone
    img = np.zeros((400, 300, 3), dtype=np.uint8)
    
    # Fill with skin-tone color (BGR format, roughly skin color)
    # Warm yellowish skin: B=100, G=150, R=180
    img[:, :] = [100, 150, 180]
    
    # Add some variation
    noise = np.random.randint(-20, 20, img.shape)
    img = cv2.add(img, noise.astype(np.uint8))
    
    return img


def create_test_hand_mask():
    """Create a test hand mask"""
    mask = np.zeros((400, 300), dtype=np.uint8)
    
    # Draw hand-like shape
    # Wrist area
    cv2.rectangle(mask, (100, 250), (200, 400), 255, -1)
    
    # Palm area
    cv2.ellipse(mask, (150, 150), (80, 100), 0, 0, 360, 255, -1)
    
    # Fingers
    for i, x in enumerate([80, 110, 150, 190, 220]):
        cv2.rectangle(mask, (x-15, 0), (x+15, 150), 255, -1)
    
    return mask


def create_test_landmarks():
    """Create mock 21 hand landmarks (MediaPipe format)"""
    # 21 landmarks: wrist, thumb, index, middle, ring, pinky
    landmarks = np.array([
        [150, 250],  # 0: wrist
        
        # Thumb
        [120, 200],  # 1
        [110, 150],  # 2
        [100, 100],  # 3
        [95, 50],    # 4: thumb tip
        
        # Index
        [110, 200],  # 5
        [105, 120],  # 6
        [100, 70],   # 7
        [95, 20],    # 8: index tip
        
        # Middle
        [150, 200],  # 9
        [150, 110],  # 10
        [150, 50],   # 11
        [150, 0],    # 12: middle tip
        
        # Ring
        [190, 200],  # 13
        [195, 120],  # 14
        [200, 70],   # 15
        [205, 20],   # 16: ring tip
        
        # Pinky
        [220, 210],  # 17
        [230, 140],  # 18
        [235, 80],   # 19
        [240, 30],   # 20: pinky tip
    ], dtype=np.float32)
    
    return landmarks


def example_1_skin_analysis():
    """Example 1: Skin tone analysis"""
    print("\n" + "="*70)
    print("EXAMPLE 1: SKIN TONE ANALYSIS")
    print("="*70)
    
    # Create test image
    img = create_test_hand_image()
    mask = create_test_hand_mask()
    
    # Analyze
    analyzer = SkinAnalyzer()
    result = analyzer.analyze(img, mask)
    
    print(f"\n馃搳 Analysis Result:")
    print(f"  Skin Type: {result['tone_classification']['skin_type']}")
    print(f"  Average HSV: {result['color_stats']['avg_hsv']}")
    print(f"  Brightness: {result['color_stats']['brightness']:.1f}")
    print(f"  Saturation: {result['color_stats']['saturation']:.1f}")
    print(f"  Is Warm: {result['tone_classification']['is_warm']}")
    print(f"  Is Cool: {result['tone_classification']['is_cool']}")
    
    return result


def example_2_hand_shape_analysis():
    """Example 2: Hand shape analysis"""
    print("\n" + "="*70)
    print("EXAMPLE 2: HAND SHAPE ANALYSIS")
    print("="*70)
    
    # Create test landmarks
    landmarks = create_test_landmarks()
    
    # Analyze
    analyzer = HandShapeAnalyzer()
    result = analyzer.analyze(landmarks)
    
    print(f"\n馃枑锔? Analysis Result:")
    print(f"  Hand Type: {result['classification']['hand_type']}")
    print(f"  Average Ratio: {result['classification']['average_ratio']:.2f}")
    print(f"  Primary Nail Shape: {result['nail_shape_recommendations']['primary_recommendation']}")
    print(f"  Alternatives: {result['nail_shape_recommendations']['secondary_options']}")
    print(f"  Reasoning: {result['nail_shape_recommendations']['reasoning']}")
    
    return result


def example_3_nail_shape_transform():
    """Example 3: Nail shape transformation"""
    print("\n" + "="*70)
    print("EXAMPLE 3: NAIL SHAPE TRANSFORMATION")
    print("="*70)
    
    # Create test nail mask
    nail_mask = np.zeros((100, 50), dtype=np.uint8)
    cv2.ellipse(nail_mask, (25, 50), (15, 40), 0, 0, 360, 255, -1)
    
    # Transform
    transformer = NailShapeTransformer()
    
    print(f"\n馃拝 Transforming nail to different shapes:")
    
    shapes_preview = transformer.preview_shapes(nail_mask)
    for shape_name, transformed_mask in shapes_preview.items():
        white_pixels = np.sum(transformed_mask > 0)
        print(f"  {shape_name}: {white_pixels} pixels")
    
    return shapes_preview


def example_4_color_database():
    """Example 4: Color database creation"""
    print("\n" + "="*70)
    print("EXAMPLE 4: COLOR DATABASE")
    print("="*70)
    
    # Create database
    db = ColorDatabase(cache_dir='./cache')
    
    # Create and add sample style images
    for style_id in range(1, 6):
        # Create different colored nail images
        if style_id == 1:
            # Red
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :] = [0, 0, 200]  # BGR: red
        elif style_id == 2:
            # Blue
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :] = [200, 0, 0]  # BGR: blue
        elif style_id == 3:
            # Pink
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :] = [100, 50, 150]  # BGR: pink
        elif style_id == 4:
            # Gold
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :] = [0, 200, 255]  # BGR: gold/yellow
        else:
            # Purple
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :] = [150, 0, 100]  # BGR: purple
        
        # Add some variation
        noise = np.random.randint(-10, 10, img.shape)
        img = cv2.add(img, noise.astype(np.uint8))
        
        # Save temporarily
        temp_path = f'./cache/test_style_{style_id}.jpg'
        cv2.imwrite(temp_path, img)
        
        # Add to database
        db.add_style(style_id, temp_path, f'http://example.com/style_{style_id}')
    
    # Save database
    db.save_database()
    
    print(f"\n馃帹 Color Database Created:")
    print(f"  Total Styles: {len(db.db)}")
    
    stats = db.get_statistics()
    print(f"  Brightness Range: {stats['brightness_range']}")
    print(f"  Saturation Range: {stats['saturation_range']}")
    
    return db


def example_5_recommendations():
    """Example 5: Generate comprehensive recommendations"""
    print("\n" + "="*70)
    print("EXAMPLE 5: COMPREHENSIVE RECOMMENDATIONS")
    print("="*70)
    
    # Get individual analyses
    skin_result = example_1_skin_analysis()
    hand_result = example_2_hand_shape_analysis()
    
    # Create recommendation engine
    engine = RecommendationEngine()
    
    # Generate recommendations
    recommendations = engine.generate_recommendations(skin_result, hand_result)
    
    print(f"\n馃挕 Recommendations Generated:")
    print(f"  Skin Type: {recommendations['user_profile']['skin_type']}")
    print(f"  Hand Type: {recommendations['user_profile']['hand_type']}")
    print(f"  Primary Nail Shape: {recommendations['combined_recommendations'][0]['nail_shape']}")
    print(f"  Color Palette: {recommendations['combined_recommendations'][0]['skin_compatibility']['best_colors']}")
    
    # Generate report
    report = engine.generate_report(recommendations)
    print("\n" + report)
    
    return recommendations


def example_6_full_pipeline():
    """Example 6: Complete pipeline end-to-end"""
    print("\n" + "="*70)
    print("EXAMPLE 6: FULL PIPELINE END-TO-END")
    print("="*70)
    
    # Initialize pipeline
    pipeline = NailRecommendationPipeline(cache_dir='./cache')
    
    # Create test data
    hand_image = create_test_hand_image()
    hand_mask = create_test_hand_mask()
    landmarks = create_test_landmarks()
    
    # Create test nail masks (one per finger)
    nail_masks = {}
    for i, finger in enumerate(['thumb', 'index', 'middle', 'ring', 'pinky']):
        mask = np.zeros((50, 30), dtype=np.uint8)
        cv2.ellipse(mask, (15, 25), (10, 20), 0, 0, 360, 255, -1)
        nail_masks[finger] = mask
    
    print(f"\n馃殌 Running full pipeline...")
    print(f"  Input: Hand image ({hand_image.shape})")
    print(f"  Mask: Hand mask ({hand_mask.shape})")
    print(f"  Landmarks: {landmarks.shape}")
    print(f"  Nail masks: {len(nail_masks)} fingers")
    
    # Generate recommendations
    result = pipeline.recommend_nails(
        hand_image=hand_image,
        hand_mask=hand_mask,
        landmarks=landmarks,
        nail_masks=nail_masks
    )
    
    print(f"\n鉁?Pipeline execution complete!")
    print(f"  Status: {result.get('status')}")
    print(f"  Components analyzed: {list(result.get('components', {}).keys())}")
    
    if result.get('status') == 'success':
        print("\n" + result.get('report', ''))
    
    return result


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("AI NAIL VIRTUAL TRY-ON - COMPLETE EXAMPLES")
    print("="*70)
    
    # Create output directory
    Path('./output').mkdir(exist_ok=True)
    Path('./cache').mkdir(exist_ok=True)
    
    try:
        # Run examples
        results = {}
        
        results['example_1'] = example_1_skin_analysis()
        results['example_2'] = example_2_hand_shape_analysis()
        results['example_3'] = example_3_nail_shape_transform()
        results['example_4'] = example_4_color_database()
        results['example_5'] = example_5_recommendations()
        results['example_6'] = example_6_full_pipeline()
        
        # Save all results
        output_path = Path('./output/complete_examples_results.json')
        with open(output_path, 'w') as f:
            json.dump({k: str(v) for k, v in results.items()}, f, indent=2, default=str)
        
        print("\n" + "="*70)
        print("鉁?ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print(f"Results saved to: {output_path}")
        print("="*70 + "\n")
        
        return 0
    
    except Exception as e:
        print(f"\n鉁?Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

