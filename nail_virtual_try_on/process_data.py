#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Data Processing and Pipeline Script
Loads Excel data, builds color database, and generates recommendations
"""

import os
import sys
import argparse
import json
from pathlib import Path
import numpy as np
import cv2

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.data_loader import DataLoader
from modules.color_database import ColorDatabase
from modules.skin_analysis import SkinAnalyzer
from modules.hand_shape_analysis import HandShapeAnalyzer
from modules.recommendation_engine import RecommendationEngine
from pipeline import NailRecommendationPipeline


def main():
    """Main processing pipeline"""
    
    parser = argparse.ArgumentParser(description='AI Nail Virtual Try-On Data Processing')
    parser.add_argument('--excel', type=str, required=True, help='Path to Excel file')
    parser.add_argument('--cache', type=str, default='./cache', help='Cache directory')
    parser.add_argument('--output', type=str, default='./output', help='Output directory')
    parser.add_argument('--build-db', action='store_true', help='Build color database')
    parser.add_argument('--skip-download', action='store_true', help='Skip image download (use cache)')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    print("\n" + "="*60)
    print("AI NAIL VIRTUAL TRY-ON - DATA PROCESSING PIPELINE")
    print("="*60)
    
    try:
        # ========== STEP 1: Load Data from Excel ==========
        print("\n馃搳 STEP 1: Loading data from Excel file...")
        loader = DataLoader(args.excel, cache_dir=args.cache)
        hand_dataset, style_dataset = loader.get_all_data()
        
        # Save metadata
        loader.save_dataset_cache(hand_dataset, style_dataset, args.cache)
        
        print(f"\n鉁?Loaded {len(hand_dataset)} hand samples")
        print(f"鉁?Loaded {len(style_dataset)} style samples")
        
        # ========== STEP 2: Build Color Database ==========
        if args.build_db or not Path(args.cache / 'style_color_db.json').exists():
            print("\n馃帹 STEP 2: Building color database from styles...")
            color_db = ColorDatabase(cache_dir=args.cache)
            
            for i, style in enumerate(style_dataset):
                try:
                    print(f"  Processing style {i+1}/{len(style_dataset)}...")
                    
                    # Use raw image for color extraction
                    image = style['raw_img']
                    
                    # Create temporary file path
                    temp_path = Path(args.cache) / f"style_{style['style_id']}_raw.jpg"
                    cv2.imwrite(str(temp_path), image)
                    
                    # Add to database
                    color_db.add_style(
                        style_id=style['style_id'],
                        image_path=str(temp_path),
                        style_url=style['raw_url'],
                        metadata={'source': 'raw', 'format': 'raw'}
                    )
                
                except Exception as e:
                    print(f"  鈿?Error processing style {i}: {e}")
                    continue
            
            # Also process enhanced images if available
            for i, style in enumerate(style_dataset):
                if style['enhanced_img'] is not None:
                    try:
                        # Create enhanced entry
                        temp_path = Path(args.cache) / f"style_{style['style_id']}_enhanced.jpg"
                        cv2.imwrite(str(temp_path), style['enhanced_img'])
                        
                        # Add to database
                        style_id_enhanced = style['style_id'] * 1000 + i  # Unique ID for enhanced
                        color_db.add_style(
                            style_id=style_id_enhanced,
                            image_path=str(temp_path),
                            style_url=style['enhanced_url'],
                            metadata={'source': 'enhanced', 'format': 'enhanced'}
                        )
                    
                    except Exception as e:
                        print(f"  鈿?Error processing enhanced style {i}: {e}")
                        continue
            
            # Save database
            color_db.save_database()
            print(f"\n鉁?Color database built with {len(color_db.db)} entries")
            
            # Save statistics
            stats = color_db.get_statistics()
            with open(output_dir / 'color_db_statistics.json', 'w') as f:
                json.dump(stats, f, indent=2)
            print(f"鉁?Statistics saved to {output_dir / 'color_db_statistics.json'}")
        
        # ========== STEP 3: Analyze Hand Dataset ==========
        print("\n馃枑锔? STEP 3: Analyzing hand dataset...")
        skin_analyzer = SkinAnalyzer()
        hand_analyses = []
        
        for i, hand in enumerate(hand_dataset[:5]):  # Analyze first 5 for demo
            try:
                print(f"  Analyzing hand {i+1}/{min(5, len(hand_dataset))}...")
                
                img = hand['hand_img']
                
                # Analyze skin
                analysis = skin_analyzer.analyze(img)
                
                hand_analyses.append({
                    'hand_id': hand['hand_id'],
                    'skin_type': analysis['tone_classification']['skin_type'],
                    'avg_hsv': analysis['color_stats']['avg_hsv'],
                    'brightness': analysis['color_stats']['brightness'],
                })
            
            except Exception as e:
                print(f"  鈿?Error analyzing hand {i}: {e}")
                continue
        
        # Save analyses
        with open(output_dir / 'hand_analysis_results.json', 'w') as f:
            json.dump(hand_analyses, f, indent=2, default=str)
        print(f"鉁?Hand analysis results saved")
        
        # ========== STEP 4: Generate Recommendations ==========
        print("\n馃拝 STEP 4: Generating recommendations...")
        pipeline = NailRecommendationPipeline(
            color_db_path=str(Path(args.cache) / 'style_color_db.json'),
            cache_dir=args.cache
        )
        
        # Process first hand with database
        if hand_dataset and pipeline.color_database.db:
            print(f"  Generating recommendation for first hand sample...")
            
            result = pipeline.recommend_nails(
                hand_image=hand_dataset[0]['hand_img']
            )
            
            # Export result
            pipeline.export_results(result, output_dir)
            
            if result.get('status') == 'success':
                print("鉁?Recommendation generated successfully!")
                print("\n" + result.get('report', ''))
            else:
                print(f"鉁?Recommendation failed: {result.get('message')}")
        
        # ========== STEP 5: Create Test Interface ==========
        print("\n馃И STEP 5: Creating test data interface...")
        test_interface_data = {
            'status': 'ready',
            'datasets': {
                'hand_count': len(hand_dataset),
                'style_count': len(style_dataset),
                'database_entries': len(pipeline.color_database.db),
            },
            'sample_hand_analysis': hand_analyses[0] if hand_analyses else None,
            'color_db_path': str(Path(args.cache) / 'style_color_db.json'),
            'cache_dir': args.cache,
        }
        
        with open(output_dir / 'test_interface.json', 'w') as f:
            json.dump(test_interface_data, f, indent=2, default=str)
        
        # ========== Summary ==========
        print("\n" + "="*60)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*60)
        print(f"鉁?Loaded {len(hand_dataset)} hand samples")
        print(f"鉁?Loaded {len(style_dataset)} style samples")
        print(f"鉁?Built color database with {len(pipeline.color_database.db)} entries")
        print(f"鉁?Analyzed {len(hand_analyses)} hands")
        print(f"\nOutput directory: {output_dir}")
        print(f"Cache directory: {args.cache}")
        print("\nGenerated files:")
        for f in output_dir.glob('*.json'):
            print(f"  - {f.name}")
        print("\n" + "="*60)
        
        return 0
    
    except Exception as e:
        print(f"\n鉁?Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

