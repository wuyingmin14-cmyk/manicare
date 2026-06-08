# Hand Shape Analysis Module
# Analyzes hand morphology and recommends nail shapes

import numpy as np
from typing import Dict, List, Tuple, Optional
import json

class HandShapeAnalyzer:
    """
    Analyzes hand shape characteristics from keypoints
    and recommends appropriate nail shapes
    """
    
    def __init__(self, config_dict: Optional[Dict] = None):
        """
        Initialize HandShapeAnalyzer
        
        Args:
            config_dict: Configuration with thresholds
        """
        if config_dict is None:
            from config import HAND_SHAPE_PARAMS
            config_dict = HAND_SHAPE_PARAMS
        
        self.config = config_dict
        self.finger_metrics = {}
        self.hand_type = None
        self.average_ratio = None
    
    def _calculate_finger_metrics(self, landmarks: np.ndarray) -> Dict:
        """
        Calculate morphological metrics for each finger
        
        MediaPipe Hands landmark structure:
        - 0: wrist
        - 1-4: thumb
        - 5-8: index
        - 9-12: middle
        - 13-16: ring
        - 17-20: pinky
        
        Args:
            landmarks: Array of shape (21, 2) or (21, 3) with x,y (,z) coords
        
        Returns:
            Dictionary with metrics for each finger
        """
        landmarks = np.array(landmarks)
        if landmarks.shape[0] != 21:
            raise ValueError(f"Expected 21 landmarks, got {landmarks.shape[0]}")
        
        # Define finger indices (tip, PIP, MCP, base)
        finger_groups = {
            'thumb': [4, 3, 2, 1],
            'index': [8, 7, 6, 5],
            'middle': [12, 11, 10, 9],
            'ring': [16, 15, 14, 13],
            'pinky': [20, 19, 18, 17],
        }
        
        metrics = {}
        ratios = []
        
        for finger_name, indices in finger_groups.items():
            tip = landmarks[indices[0]][:2]  # Finger tip
            base = landmarks[indices[-1]][:2]  # Base (MCP)
            mid = landmarks[indices[2]][:2]  # Middle segment
            
            # Calculate length (tip to base)
            length = np.linalg.norm(tip - base)
            
            # Calculate width (average of MCP and PIP segments)
            seg1 = np.linalg.norm(landmarks[indices[2]][:2] - landmarks[indices[1]][:2])
            seg2 = np.linalg.norm(landmarks[indices[1]][:2] - landmarks[indices[0]][:2])
            avg_width = (seg1 + seg2) / 2
            
            # Avoid division by zero
            if avg_width < 0.1:
                avg_width = 0.1
            
            ratio = length / avg_width
            ratios.append(ratio)
            
            metrics[finger_name] = {
                'length': float(length),
                'width': float(avg_width),
                'length_width_ratio': float(ratio),
            }
        
        # Calculate hand-level statistics
        avg_ratio = np.mean(ratios)
        std_ratio = np.std(ratios)
        
        self.finger_metrics = metrics
        self.average_ratio = avg_ratio
        
        return {
            'finger_metrics': metrics,
            'average_ratio': float(avg_ratio),
            'ratio_std': float(std_ratio),
            'ratios': [float(r) for r in ratios],
        }
    
    def classify_hand_shape(self, avg_ratio: Optional[float] = None) -> Dict:
        """
        Classify hand shape based on finger length-to-width ratio
        
        Args:
            avg_ratio: Average length/width ratio across fingers
        
        Returns:
            Dictionary with hand type classification
        """
        if avg_ratio is None:
            if self.average_ratio is None:
                raise ValueError("Must calculate metrics first or provide avg_ratio")
            avg_ratio = self.average_ratio
        
        # Classification rules
        if avg_ratio < self.config['short_wide_threshold']:
            hand_type = 'short_wide'
            hand_description = 'Short and wide hands'
        elif avg_ratio > self.config['long_thin_threshold']:
            hand_type = 'long_thin'
            hand_description = 'Long and thin hands'
        else:
            hand_type = 'standard'
            hand_description = 'Standard hand proportions'
        
        self.hand_type = hand_type
        
        return {
            'hand_type': hand_type,
            'description': hand_description,
            'average_ratio': float(avg_ratio),
            'threshold_short_wide': float(self.config['short_wide_threshold']),
            'threshold_long_thin': float(self.config['long_thin_threshold']),
        }
    
    def recommend_nail_shapes(self, hand_type: Optional[str] = None) -> Dict:
        """
        Recommend nail shapes based on hand type
        
        Args:
            hand_type: Hand type classification
        
        Returns:
            Dictionary with recommended nail shapes
        """
        if hand_type is None:
            if self.hand_type is None:
                raise ValueError("Must classify hand first or provide hand_type")
            hand_type = self.hand_type
        
        from config import NAIL_SHAPE_RECOMMENDATIONS
        
        if hand_type not in NAIL_SHAPE_RECOMMENDATIONS:
            recommended_shapes = ['oval', 'almond']  # Default
        else:
            recommended_shapes = NAIL_SHAPE_RECOMMENDATIONS[hand_type]
        
        recommendations = {
            'hand_type': hand_type,
            'primary_recommendation': recommended_shapes[0],
            'secondary_options': recommended_shapes[1:],
            'all_recommended': recommended_shapes,
            'reasoning': self._get_recommendation_reasoning(hand_type),
        }
        
        return recommendations
    
    def _get_recommendation_reasoning(self, hand_type: str) -> str:
        """Get reasoning for recommendation"""
        reasoning = {
            'short_wide': 'Oval/round shapes visually elongate short fingers',
            'long_thin': 'Square/round shapes add visual balance and substance',
            'standard': 'Universal shapes work well with standard proportions',
        }
        return reasoning.get(hand_type, 'Standard recommendation')
    
    def analyze(self, landmarks: np.ndarray) -> Dict:
        """
        Complete hand shape analysis pipeline
        
        Args:
            landmarks: Array of hand landmarks (21, 2)
        
        Returns:
            Comprehensive analysis dictionary
        """
        # Calculate metrics
        metrics = self._calculate_finger_metrics(landmarks)
        
        # Classify hand
        classification = self.classify_hand_shape()
        
        # Recommend shapes
        recommendations = self.recommend_nail_shapes()
        
        return {
            'metrics': metrics,
            'classification': classification,
            'nail_shape_recommendations': recommendations,
            'analysis_complete': True,
        }
    
    def export_analysis(self, output_path: str) -> None:
        """Export analysis to JSON"""
        analysis_data = {
            'hand_type': self.hand_type,
            'average_ratio': self.average_ratio,
            'finger_metrics': self.finger_metrics,
        }
        
        with open(output_path, 'w') as f:
            json.dump(analysis_data, f, indent=2)


# Example usage
if __name__ == "__main__":
    # Test with sample landmarks
    analyzer = HandShapeAnalyzer()
    
    # Create test landmarks (21 points)
    test_landmarks = np.random.rand(21, 2) * 100
    
    # Analyze
    result = analyzer.analyze(test_landmarks)
    print("Analysis result:", result)
