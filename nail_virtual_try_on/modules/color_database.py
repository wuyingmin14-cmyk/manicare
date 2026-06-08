# Color Database Module
# Builds and manages color database from nail style images

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path
from sklearn.cluster import KMeans
import hashlib

class ColorDatabase:
    """
    Builds and manages a database of nail style colors
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize ColorDatabase
        
        Args:
            cache_dir: Directory to cache database
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path('./cache')
        self.cache_dir.mkdir(exist_ok=True)
        self.db = {}
        self.db_path = self.cache_dir / 'style_color_db.json'
    
    def extract_dominant_colors(self, 
                               image: np.ndarray, 
                               n_colors: int = 5,
                               exclude_white: bool = True) -> List[List[float]]:
        """
        Extract dominant colors from image using KMeans
        
        Args:
            image: Input image (BGR)
            n_colors: Number of dominant colors to extract
            exclude_white: Exclude near-white colors (high V in HSV)
        
        Returns:
            List of dominant colors in HSV format
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Reshape for clustering
        pixels = hsv.reshape(-1, 3).astype(float)
        
        # Filter out near-white colors (background, etc.)
        if exclude_white:
            v_values = pixels[:, 2]
            valid_mask = v_values < 240
            pixels = pixels[valid_mask]
        
        if len(pixels) < n_colors:
            n_colors = max(1, len(pixels) // 10)
        
        # KMeans clustering
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        # Get cluster centers
        colors = kmeans.cluster_centers_.tolist()
        
        # Sort by brightness (descending)
        colors = sorted(colors, key=lambda c: c[2], reverse=True)
        
        return colors
    
    def calculate_color_properties(self, image: np.ndarray) -> Dict:
        """
        Calculate color properties of nail image
        
        Args:
            image: Nail style image
        
        Returns:
            Dictionary with color properties
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Remove near-white pixels
        v_channel = hsv[:, :, 2]
        valid_pixels = hsv[v_channel < 240]
        
        if len(valid_pixels) == 0:
            valid_pixels = hsv.reshape(-1, 3)
        
        # Calculate statistics
        h_values = valid_pixels[:, 0].astype(float)
        s_values = valid_pixels[:, 1].astype(float)
        v_values = valid_pixels[:, 2].astype(float)
        
        properties = {
            'avg_hue': float(np.mean(h_values)),
            'avg_saturation': float(np.mean(s_values)),
            'avg_brightness': float(np.mean(v_values)),
            'brightness': float(np.mean(v_values)),
            'saturation': float(np.mean(s_values)),
            'hue_std': float(np.std(h_values)),
            'saturation_std': float(np.std(s_values)),
            'brightness_std': float(np.std(v_values)),
        }
        
        # Calculate contrast (difference between min and max brightness)
        contrast = float(np.max(v_values) - np.min(v_values))
        properties['contrast'] = contrast
        
        return properties
    
    def add_style(self, 
                  style_id: int,
                  image_path: str,
                  style_url: str = "",
                  metadata: Optional[Dict] = None) -> Dict:
        """
        Add a nail style to the database
        
        Args:
            style_id: Unique style identifier
            image_path: Path to style image
            style_url: URL to original style image
            metadata: Additional metadata
        
        Returns:
            Database entry
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Cannot load image: {image_path}")
        
        # Extract colors
        dominant_colors = self.extract_dominant_colors(image)
        
        # Calculate properties
        properties = self.calculate_color_properties(image)
        
        # Create database entry
        entry = {
            'style_id': style_id,
            'image_path': str(image_path),
            'style_url': style_url,
            'dominant_colors': dominant_colors,
            'properties': properties,
            'metadata': metadata or {},
        }
        
        self.db[style_id] = entry
        
        return entry
    
    def batch_add_styles(self, 
                        styles_data: List[Dict]) -> None:
        """
        Add multiple styles to database
        
        Args:
            styles_data: List of dictionaries with 'id', 'path', 'url', 'metadata'
        """
        for style_info in styles_data:
            self.add_style(
                style_id=style_info['id'],
                image_path=style_info['path'],
                style_url=style_info.get('url', ''),
                metadata=style_info.get('metadata', {}),
            )
    
    def calculate_color_similarity(self, 
                                  color1: List[float], 
                                  color2: List[float]) -> float:
        """
        Calculate similarity between two colors (HSV)
        
        Args:
            color1: HSV color [H, S, V]
            color2: HSV color [H, S, V]
        
        Returns:
            Similarity score (0-1)
        """
        color1 = np.array(color1)
        color2 = np.array(color2)
        
        # Normalize components
        h_dist = min(abs(color1[0] - color2[0]), 180 - abs(color1[0] - color2[0]))
        s_dist = abs(color1[1] - color2[1])
        v_dist = abs(color1[2] - color2[2])
        
        # Weighted distance
        total_dist = (h_dist * 0.3 + s_dist * 0.3 + v_dist * 0.4)
        
        # Convert to similarity (0-1)
        similarity = 1.0 - (total_dist / 180)
        
        return max(0.0, min(1.0, similarity))
    
    def find_compatible_styles(self, 
                              skin_color: List[float],
                              search_type: str = 'high_contrast',
                              top_n: int = 5) -> List[Dict]:
        """
        Find compatible nail styles for skin color
        
        Args:
            skin_color: Average skin color in HSV
            search_type: 'high_contrast' or 'harmonious'
            top_n: Number of results to return
        
        Returns:
            List of compatible styles sorted by score
        """
        results = []
        
        for style_id, entry in self.db.items():
            dominant_color = entry['dominant_colors'][0]  # Primary color
            properties = entry['properties']
            
            if search_type == 'high_contrast':
                # High contrast means large brightness difference
                brightness_diff = abs(properties['avg_brightness'] - skin_color[2])
                compatibility_score = brightness_diff / 255.0
                
                # Prefer saturated colors
                saturation_bonus = properties['avg_saturation'] / 255.0 * 0.3
                compatibility_score += saturation_bonus
                
            elif search_type == 'harmonious':
                # Similar hue and saturation
                color_sim = self.calculate_color_similarity(skin_color, dominant_color)
                compatibility_score = color_sim
            
            else:
                compatibility_score = 0.5
            
            results.append({
                'style_id': style_id,
                'score': float(compatibility_score),
                'url': entry.get('style_url', ''),
                'properties': properties,
                'dominant_colors': dominant_color,
            })
        
        # Sort by score
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        
        return results[:top_n]
    
    def save_database(self, output_path: Optional[str] = None) -> str:
        """
        Save database to JSON
        
        Args:
            output_path: Path to save database
        
        Returns:
            Path where database was saved
        """
        if output_path is None:
            output_path = str(self.db_path)
        
        # Convert to JSON-serializable format
        db_data = {}
        for key, entry in self.db.items():
            db_data[str(key)] = entry
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Database saved to {output_path}")
        return output_path
    
    def load_database(self, input_path: Optional[str] = None) -> None:
        """
        Load database from JSON
        
        Args:
            input_path: Path to load database from
        """
        if input_path is None:
            input_path = str(self.db_path)
        
        if not Path(input_path).exists():
            print(f"Database file not found: {input_path}")
            return
        
        with open(input_path, 'r', encoding='utf-8') as f:
            db_data = json.load(f)
        
        # Convert keys back to int
        self.db = {int(key): entry for key, entry in db_data.items()}
        
        print(f"✓ Database loaded from {input_path}")
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        if not self.db:
            return {}
        
        stats = {
            'total_styles': len(self.db),
            'brightness_range': [
                min(e['properties']['avg_brightness'] for e in self.db.values()),
                max(e['properties']['avg_brightness'] for e in self.db.values()),
            ],
            'saturation_range': [
                min(e['properties']['avg_saturation'] for e in self.db.values()),
                max(e['properties']['avg_saturation'] for e in self.db.values()),
            ],
        }
        return stats


# Example usage
if __name__ == "__main__":
    db = ColorDatabase()
    print("ColorDatabase initialized")
