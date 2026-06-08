# Nail Shape Transform Module
# Geometric transformation for different nail shapes

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.ndimage import binary_dilation, binary_erosion

class NailShapeTransformer:
    """
    Transforms nail masks to different shapes while maintaining natural appearance
    """
    
    def __init__(self):
        """Initialize NailShapeTransformer"""
        self.supported_shapes = ['square', 'round', 'oval', 'almond', 'coffin']
    
    def _get_nail_contour(self, mask: np.ndarray) -> np.ndarray:
        """
        Extract nail contour from mask
        
        Args:
            mask: Binary nail mask
        
        Returns:
            Contour array
        """
        # Ensure binary mask
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8) * 255
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 0:
            raise ValueError("No contour found in mask")
        
        # Get largest contour
        contour = max(contours, key=cv2.contourArea)
        return contour
    
    def _reshape_to_square(self, 
                           contour: np.ndarray, 
                           mask_shape: Tuple) -> np.ndarray:
        """
        Reshape nail mask to square shape
        
        Args:
            contour: Nail contour
            mask_shape: Shape of output mask
        
        Returns:
            New binary mask
        """
        new_mask = np.zeros(mask_shape, dtype=np.uint8)
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Make width and height equal (square)
        side = max(w, h)
        center_x = x + w // 2
        center_y = y + h // 2
        
        # Draw square
        x1 = max(0, center_x - side // 2)
        y1 = max(0, center_y - side // 2)
        x2 = min(mask_shape[1], x1 + side)
        y2 = min(mask_shape[0], y1 + side)
        
        new_mask[y1:y2, x1:x2] = 255
        
        return new_mask
    
    def _reshape_to_round(self, 
                          contour: np.ndarray, 
                          mask_shape: Tuple) -> np.ndarray:
        """
        Reshape nail mask to round/circular shape
        
        Args:
            contour: Nail contour
            mask_shape: Shape of output mask
        
        Returns:
            New binary mask
        """
        new_mask = np.zeros(mask_shape, dtype=np.uint8)
        
        # Get bounding box and calculate circle
        x, y, w, h = cv2.boundingRect(contour)
        center_x = x + w // 2
        center_y = y + h // 2
        radius = max(w, h) // 2
        
        # Draw circle
        cv2.circle(new_mask, (center_x, center_y), radius, 255, -1)
        
        return new_mask
    
    def _reshape_to_oval(self, 
                         contour: np.ndarray, 
                         mask_shape: Tuple) -> np.ndarray:
        """
        Reshape nail mask to oval shape
        
        Args:
            contour: Nail contour
            mask_shape: Shape of output mask
        
        Returns:
            New binary mask
        """
        new_mask = np.zeros(mask_shape, dtype=np.uint8)
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Create oval (ellipse) with 1:1.4 aspect ratio for visual length
        center_x = x + w // 2
        center_y = y + h // 2
        axes_a = w // 2  # Minor axis
        axes_b = int(h * 0.7)  # Major axis (longer)
        
        # Draw ellipse
        cv2.ellipse(new_mask, (center_x, center_y), (axes_a, axes_b), 0, 0, 360, 255, -1)
        
        return new_mask
    
    def _reshape_to_almond(self, 
                           contour: np.ndarray, 
                           mask_shape: Tuple) -> np.ndarray:
        """
        Reshape nail mask to almond shape (pointed oval)
        
        Args:
            contour: Nail contour
            mask_shape: Shape of output mask
        
        Returns:
            New binary mask
        """
        new_mask = np.zeros(mask_shape, dtype=np.uint8)
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        center_x = x + w // 2
        center_y = y + h // 2
        
        # Create almond shape using two circles
        radius_small = w // 2
        radius_large = int(h * 0.6)
        
        # Top oval (pointer top)
        cv2.ellipse(new_mask, (center_x, center_y), 
                   (radius_small // 2, radius_large), 0, 0, 360, 255, -1)
        
        # Round the edges
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        new_mask = cv2.morphologyEx(new_mask, cv2.MORPH_CLOSE, kernel)
        
        return new_mask
    
    def _reshape_to_coffin(self, 
                           contour: np.ndarray, 
                           mask_shape: Tuple) -> np.ndarray:
        """
        Reshape nail mask to coffin shape (trapezoid)
        
        Args:
            contour: Nail contour
            mask_shape: Shape of output mask
        
        Returns:
            New binary mask
        """
        new_mask = np.zeros(mask_shape, dtype=np.uint8)
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Create trapezoid points (wider at base, narrower at tip)
        points = np.array([
            [x, y + h],              # Bottom left
            [x + w, y + h],          # Bottom right
            [x + int(w * 0.7), y],   # Top right (narrower)
            [x + int(w * 0.3), y],   # Top left (narrower)
        ], dtype=np.int32)
        
        # Draw filled polygon
        cv2.fillPoly(new_mask, [points], 255)
        
        return new_mask
    
    def transform_to_shape(self, 
                           nail_mask: np.ndarray, 
                           target_shape: str,
                           smooth: bool = True) -> np.ndarray:
        """
        Transform nail mask to target shape
        
        Args:
            nail_mask: Original nail mask (binary)
            target_shape: Target shape name ('square', 'round', 'oval', 'almond', 'coffin')
            smooth: Apply smoothing to edges
        
        Returns:
            Transformed nail mask
        """
        if target_shape not in self.supported_shapes:
            raise ValueError(f"Unsupported shape: {target_shape}. "
                           f"Supported: {self.supported_shapes}")
        
        # Get contour from original mask
        contour = self._get_nail_contour(nail_mask)
        
        # Apply transformation based on shape
        shape_methods = {
            'square': self._reshape_to_square,
            'round': self._reshape_to_round,
            'oval': self._reshape_to_oval,
            'almond': self._reshape_to_almond,
            'coffin': self._reshape_to_coffin,
        }
        
        new_mask = shape_methods[target_shape](contour, nail_mask.shape)
        
        # Smooth edges if requested
        if smooth:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            new_mask = cv2.morphologyEx(new_mask, cv2.MORPH_CLOSE, kernel)
            new_mask = cv2.GaussianBlur(new_mask, (3, 3), 0)
        
        return new_mask
    
    def transform_nail_set(self, 
                           nail_masks: Dict[str, np.ndarray], 
                           target_shape: str) -> Dict[str, np.ndarray]:
        """
        Transform all nails in a set to the same shape
        
        Args:
            nail_masks: Dictionary of nail masks {'thumb': mask, 'index': mask, ...}
            target_shape: Target shape for all nails
        
        Returns:
            Dictionary of transformed masks
        """
        transformed = {}
        
        for finger_name, mask in nail_masks.items():
            transformed[finger_name] = self.transform_to_shape(mask, target_shape)
        
        return transformed
    
    def preview_shapes(self, 
                       nail_mask: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Generate previews of all available shapes
        
        Args:
            nail_mask: Original nail mask
        
        Returns:
            Dictionary of masks for all shapes
        """
        previews = {}
        
        for shape in self.supported_shapes:
            previews[shape] = self.transform_to_shape(nail_mask, shape)
        
        return previews


# Example usage
if __name__ == "__main__":
    # Test with sample mask
    transformer = NailShapeTransformer()
    
    # Create test nail mask
    test_mask = np.zeros((100, 50), dtype=np.uint8)
    cv2.ellipse(test_mask, (25, 50), (15, 40), 0, 0, 360, 255, -1)
    
    # Transform to different shapes
    transformed = transformer.preview_shapes(test_mask)
    print(f"Generated shapes: {list(transformed.keys())}")
