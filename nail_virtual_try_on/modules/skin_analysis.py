# Skin Tone Analysis Module
# Analyzes skin color and classifies skin tone type

import cv2
import numpy as np
from typing import Dict, Tuple, List, Optional
import json
from pathlib import Path

class SkinAnalyzer:
    """
    Analyzes skin tone from hand images and provides color recommendations
    """
    
    def __init__(self, config_dict: Optional[Dict] = None):
        """
        Initialize SkinAnalyzer
        
        Args:
            config_dict: Configuration dictionary with thresholds
        """
        if config_dict is None:
            from config import SKIN_TONE_THRESHOLDS
            config_dict = SKIN_TONE_THRESHOLDS
        
        self.config = config_dict
        self.avg_hsv = None
        self.skin_type = None
        self.color_histogram = None
    
    def extract_skin_color(self, 
                          image: np.ndarray, 
                          mask: Optional[np.ndarray] = None) -> Dict:
        """
        Extract skin color statistics from hand region
        
        Args:
            image: Input image (BGR)
            mask: Hand mask (optional, if None, uses entire image)
        
        Returns:
            Dictionary with skin color features
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Apply mask if provided
        if mask is not None:
            # Ensure mask is single channel
            if len(mask.shape) == 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            # Threshold mask
            mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]
            # Extract skin region
            skin_region = hsv[mask > 0]
        else:
            skin_region = hsv.reshape(-1, 3)
        
        if len(skin_region) == 0:
            raise ValueError("No skin region found in mask")
        
        # Calculate statistics
        h_channel = skin_region[:, 0].astype(float)
        s_channel = skin_region[:, 1].astype(float)
        v_channel = skin_region[:, 2].astype(float)
        
        # Average color
        avg_h = np.mean(h_channel)
        avg_s = np.mean(s_channel)
        avg_v = np.mean(v_channel)
        
        # Store for later use
        self.avg_hsv = [avg_h, avg_s, avg_v]
        
        # Histogram
        hist = cv2.calcHist([hsv], [0, 1, 2], mask, (8, 8, 8), 
                            [0, 180, 0, 256, 0, 256])
        self.color_histogram = hist
        
        return {
            'avg_hsv': self.avg_hsv,
            'std_hsv': [np.std(h_channel), np.std(s_channel), np.std(v_channel)],
            'brightness': float(avg_v),
            'saturation': float(avg_s),
            'hue': float(avg_h),
            'histogram': hist,
        }
    
    def classify_skin_tone(self, avg_hsv: Optional[List] = None) -> Dict:
        """
        Classify skin tone based on HSV values
        
        Args:
            avg_hsv: Average HSV values [H, S, V]
        
        Returns:
            Dictionary with skin type classification
        """
        if avg_hsv is None:
            if self.avg_hsv is None:
                raise ValueError("Must call extract_skin_color first or provide avg_hsv")
            avg_hsv = self.avg_hsv
        
        h, s, v = avg_hsv
        
        # Normalize H to 0-360 range (OpenCV uses 0-180)
        h_normalized = h * 2  # Convert from OpenCV range
        
        # Classify by hue and brightness
        is_warm = ((h_normalized >= self.config['hue_warm_min'] and 
                    h_normalized <= self.config['hue_warm_max']) or
                   h_normalized > 330)  # Reds
        
        is_cool = (h_normalized >= self.config['hue_cool_min'] and 
                   h_normalized <= self.config['hue_cool_max'])
        
        is_dark = v < self.config['brightness_dark']
        is_light = v >= self.config['brightness_light']
        
        # Determine skin type
        if is_dark:
            skin_type = 'dark_skin'
        elif is_cool and is_light:
            skin_type = 'cool_white'
        elif is_warm:
            skin_type = 'warm_yellow'
        else:
            skin_type = 'neutral'
        
        self.skin_type = skin_type
        
        return {
            'skin_type': skin_type,
            'hue': float(h_normalized),
            'saturation': float(s),
            'brightness': float(v),
            'is_warm': bool(is_warm),
            'is_cool': bool(is_cool),
            'is_dark': bool(is_dark),
        }
    
    def analyze(self, 
                image: np.ndarray, 
                mask: Optional[np.ndarray] = None) -> Dict:
        """
        Complete skin analysis pipeline
        
        Args:
            image: Input image (BGR)
            mask: Hand mask (optional)
        
        Returns:
            Comprehensive analysis dictionary
        """
        # Extract color
        color_stats = self.extract_skin_color(image, mask)
        
        # Classify tone
        tone_class = self.classify_skin_tone()
        
        return {
            'color_stats': color_stats,
            'tone_classification': tone_class,
            'analysis_complete': True,
        }
    
    def get_recommendations_metadata(self) -> Dict:
        """
        Get metadata for color recommendations based on current skin analysis
        
        Returns:
            Dictionary with recommendation parameters
        """
        if self.skin_type is None:
            raise ValueError("Must analyze skin first")
        
        return {
            'skin_type': self.skin_type,
            'avg_hsv': self.avg_hsv,
            'recommendation_targets': self._get_recommendation_targets(),
        }
    
    def _get_recommendation_targets(self) -> Dict:
        """
        Generate recommendation targets based on skin type
        """
        from config import COLOR_RECOMMENDATION_RULES
        
        if self.skin_type not in COLOR_RECOMMENDATION_RULES:
            return {
                'high_contrast': [],
                'harmonious': [],
            }
        
        return COLOR_RECOMMENDATION_RULES[self.skin_type]
    
    def export_analysis(self, output_path: str) -> None:
        """
        Export analysis to JSON
        """
        analysis_data = {
            'skin_type': self.skin_type,
            'avg_hsv': self.avg_hsv,
            'recommendations': self.get_recommendations_metadata(),
        }
        
        with open(output_path, 'w') as f:
            json.dump(analysis_data, f, indent=2)


# Example usage
if __name__ == "__main__":
    # Test with sample data
    analyzer = SkinAnalyzer()
    
    # Create test image
    test_img = np.uint8(np.random.rand(100, 100, 3) * 255)
    
    # Analyze
    result = analyzer.analyze(test_img)
    print("Analysis result:", result)
