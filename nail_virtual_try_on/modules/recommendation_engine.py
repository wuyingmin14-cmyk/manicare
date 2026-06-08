# Recommendation Engine Module
# Combines skin, hand, and color analysis for personalized recommendations

from typing import Dict, List, Optional
import numpy as np
import json
from pathlib import Path

class RecommendationEngine:
    """
    Generates personalized nail recommendations based on:
    - Skin tone analysis
    - Hand shape analysis
    - Color database compatibility
    """
    
    def __init__(self, color_database = None):
        """
        Initialize RecommendationEngine
        
        Args:
            color_database: ColorDatabase instance
        """
        self.color_database = color_database
        self.recommendations_cache = {}
    
    def generate_recommendations(self,
                                skin_analysis: Dict,
                                hand_analysis: Dict,
                                style_preferences: Optional[Dict] = None) -> Dict:
        """
        Generate comprehensive nail recommendations
        
        Args:
            skin_analysis: Output from SkinAnalyzer.analyze()
            hand_analysis: Output from HandShapeAnalyzer.analyze()
            style_preferences: User style preferences
        
        Returns:
            Comprehensive recommendation dictionary
        """
        skin_type = skin_analysis['tone_classification']['skin_type']
        hand_type = hand_analysis['classification']['hand_type']
        
        recommendations = {
            'user_profile': {
                'skin_type': skin_type,
                'hand_type': hand_type,
            },
            'skin_recommendations': self._get_skin_based_colors(skin_analysis),
            'hand_recommendations': hand_analysis['nail_shape_recommendations'],
            'combined_recommendations': self._combine_recommendations(
                skin_analysis, 
                hand_analysis,
                style_preferences
            ),
        }
        
        return recommendations
    
    def _get_skin_based_colors(self, skin_analysis: Dict) -> Dict:
        """
        Get color recommendations based on skin analysis
        
        Args:
            skin_analysis: Skin analysis results
        
        Returns:
            Color recommendations
        """
        skin_type = skin_analysis['tone_classification']['skin_type']
        avg_hsv = skin_analysis['color_stats']['avg_hsv']
        
        recommendations = {
            'skin_type': skin_type,
            'avg_color_hsv': avg_hsv,
        }
        
        # Get colors from database if available
        if self.color_database:
            high_contrast = self.color_database.find_compatible_styles(
                avg_hsv, 
                search_type='high_contrast',
                top_n=3
            )
            harmonious = self.color_database.find_compatible_styles(
                avg_hsv,
                search_type='harmonious',
                top_n=3
            )
            
            recommendations['high_contrast_styles'] = high_contrast
            recommendations['harmonious_styles'] = harmonious
        
        return recommendations
    
    def _combine_recommendations(self,
                                skin_analysis: Dict,
                                hand_analysis: Dict,
                                style_preferences: Optional[Dict] = None) -> List[Dict]:
        """
        Combine skin and hand recommendations
        
        Args:
            skin_analysis: Skin analysis results
            hand_analysis: Hand analysis results
            style_preferences: User preferences
        
        Returns:
            Combined recommendations
        """
        skin_type = skin_analysis['tone_classification']['skin_type']
        hand_type = hand_analysis['classification']['hand_type']
        
        # Generate recommendation score based on combinations
        recommendations = []
        
        # Primary recommendation
        primary_nail_shape = hand_analysis['nail_shape_recommendations']['primary_recommendation']
        
        recommendation = {
            'priority': 'primary',
            'nail_shape': primary_nail_shape,
            'nail_shape_reason': hand_analysis['nail_shape_recommendations']['reasoning'],
            'skin_compatibility': self._get_skin_color_rule(skin_type),
            'overall_score': 0.9,
        }
        
        recommendations.append(recommendation)
        
        # Secondary recommendations
        for alt_shape in hand_analysis['nail_shape_recommendations']['secondary_options']:
            recommendation = {
                'priority': 'secondary',
                'nail_shape': alt_shape,
                'nail_shape_reason': 'Alternative option for styling variation',
                'skin_compatibility': self._get_skin_color_rule(skin_type),
                'overall_score': 0.7,
            }
            recommendations.append(recommendation)
        
        return recommendations
    
    def _get_skin_color_rule(self, skin_type: str) -> Dict:
        """
        Get color rules for skin type
        
        Args:
            skin_type: Skin tone classification
        
        Returns:
            Color rules dictionary
        """
        rules = {
            'warm_yellow': {
                'best_colors': ['cool_pink', 'deep_blue', 'purple'],
                'avoid_colors': ['warm_brown', 'peachy'],
                'reasoning': 'Cool colors create high contrast with warm undertones'
            },
            'cool_white': {
                'best_colors': ['wine_red', 'deep_purple', 'cool_nude'],
                'avoid_colors': ['orange', 'warm_coral'],
                'reasoning': 'Rich colors complement cool undertones'
            },
            'dark_skin': {
                'best_colors': ['bright_red', 'gold', 'neon_pink'],
                'avoid_colors': ['dark_brown', 'muted_colors'],
                'reasoning': 'Bright and vibrant colors make a bold statement'
            },
            'neutral': {
                'best_colors': ['classic_red', 'nude', 'any_color'],
                'avoid_colors': [],
                'reasoning': 'Neutral tones work well with any color'
            }
        }
        
        return rules.get(skin_type, rules['neutral'])
    
    def rank_nail_styles(self,
                        nail_styles: List[Dict],
                        skin_type: str,
                        hand_type: str,
                        weights: Optional[Dict] = None) -> List[Dict]:
        """
        Rank nail styles based on skin and hand compatibility
        
        Args:
            nail_styles: List of nail style dictionaries
            skin_type: User skin tone type
            hand_type: User hand shape type
            weights: Custom scoring weights
        
        Returns:
            Ranked list of nail styles
        """
        if weights is None:
            weights = {
                'color_contrast': 0.4,
                'color_harmony': 0.2,
                'brightness': 0.2,
                'saturation': 0.2,
            }
        
        scored_styles = []
        
        for style in nail_styles:
            score = self._calculate_style_score(style, skin_type, hand_type, weights)
            style_copy = style.copy()
            style_copy['recommendation_score'] = score
            scored_styles.append(style_copy)
        
        # Sort by score
        scored_styles = sorted(scored_styles, key=lambda x: x['recommendation_score'], reverse=True)
        
        return scored_styles
    
    def _calculate_style_score(self,
                              style: Dict,
                              skin_type: str,
                              hand_type: str,
                              weights: Dict) -> float:
        """
        Calculate recommendation score for a style
        
        Args:
            style: Style dictionary
            skin_type: Skin tone type
            hand_type: Hand shape type
            weights: Scoring weights
        
        Returns:
            Recommendation score (0-1)
        """
        score = 0.0
        
        # Color contrast score
        if 'properties' in style and 'contrast' in style['properties']:
            contrast_score = min(style['properties']['contrast'] / 255.0, 1.0)
            score += contrast_score * weights.get('color_contrast', 0.4)
        
        # Brightness score (prefer medium to high brightness for most skin types)
        if 'properties' in style and 'avg_brightness' in style['properties']:
            brightness = style['properties']['avg_brightness']
            if skin_type == 'dark_skin':
                brightness_score = max(brightness / 255.0, 0.5)
            else:
                brightness_score = 1.0 - abs(brightness - 180) / 180.0
            
            score += brightness_score * weights.get('brightness', 0.2)
        
        # Base score
        score += 0.2
        
        # Normalize
        return min(1.0, score)
    
    def generate_report(self, recommendations: Dict) -> str:
        """
        Generate human-readable recommendation report
        
        Args:
            recommendations: Recommendations dictionary
        
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 60)
        report.append("PERSONALIZED NAIL RECOMMENDATION REPORT")
        report.append("=" * 60)
        
        # User profile
        profile = recommendations['user_profile']
        report.append(f"\n👤 YOUR PROFILE:")
        report.append(f"  Skin Type: {profile['skin_type']}")
        report.append(f"  Hand Type: {profile['hand_type']}")
        
        # Hand recommendations
        hand_rec = recommendations['hand_recommendations']
        report.append(f"\n💅 NAIL SHAPE RECOMMENDATION:")
        report.append(f"  Primary: {hand_rec['primary_recommendation'].upper()}")
        report.append(f"  Reason: {hand_rec['reasoning']}")
        if hand_rec['secondary_options']:
            report.append(f"  Alternatives: {', '.join(hand_rec['secondary_options'])}")
        
        # Combined recommendations
        report.append(f"\n✨ COMPREHENSIVE RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations['combined_recommendations'], 1):
            report.append(f"\n  Option {i}:")
            report.append(f"    Nail Shape: {rec['nail_shape']}")
            report.append(f"    Color Palette: {', '.join(rec['skin_compatibility']['best_colors'])}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
    
    def export_recommendations(self, 
                              recommendations: Dict, 
                              output_path: str) -> None:
        """
        Export recommendations to JSON
        
        Args:
            recommendations: Recommendations dictionary
            output_path: Path to save
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(recommendations, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✓ Recommendations exported to {output_path}")


# Example usage
if __name__ == "__main__":
    engine = RecommendationEngine()
    print("RecommendationEngine initialized")
