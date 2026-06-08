# Data Loader Module
# Loads and processes data from Excel files

import pandas as pd
import requests
import cv2
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
import os
import io

class DataLoader:
    """
    Loads nail style and hand image data from Excel files
    """
    
    def __init__(self, excel_path: str, cache_dir: str = './cache'):
        """
        Initialize DataLoader
        
        Args:
            excel_path: Path to Excel file
            cache_dir: Directory to cache downloaded images
        """
        self.excel_path = excel_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Check if file exists
        if not Path(excel_path).exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
        
        print(f"✓ DataLoader initialized with: {excel_path}")
    
    def load_excel_sheets(self) -> Dict[str, pd.DataFrame]:
        """
        Load all sheets from Excel file
        
        Returns:
            Dictionary of DataFrames {sheet_name: DataFrame}
        """
        try:
            excel_file = pd.ExcelFile(self.excel_path)
            sheets = {}
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
                sheets[sheet_name] = df
                print(f"✓ Loaded sheet '{sheet_name}' with {len(df)} rows")
            
            return sheets
        
        except Exception as e:
            raise RuntimeError(f"Error loading Excel file: {e}")
    
    def download_image(self, url: str, timeout: int = 10) -> np.ndarray:
        """
        Download image from URL
        
        Args:
            url: Image URL
            timeout: Request timeout in seconds
        
        Returns:
            Image as numpy array (BGR)
        """
        try:
            # Check cache first
            cache_path = self._get_cache_path(url)
            if cache_path.exists():
                img = cv2.imread(str(cache_path))
                if img is not None:
                    return img
            
            # Download
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            # Convert to numpy array
            image_array = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if img is None:
                raise ValueError(f"Failed to decode image from {url}")
            
            # Cache
            cv2.imwrite(str(cache_path), img)
            
            return img
        
        except Exception as e:
            raise RuntimeError(f"Error downloading image from {url}: {e}")
    
    def _get_cache_path(self, url: str) -> Path:
        """Generate cache path from URL"""
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.jpg"
    
    def process_hand_dataset(self, sheets: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        Process hand dataset from Excel
        
        Expected Excel structure:
        - Column 1: Hand image URL
        - Column 2: Style fusion image URL
        
        Args:
            sheets: Dictionary of DataFrames
        
        Returns:
            List of hand dataset entries
        """
        # Detect hand sheet (usually first sheet or named "Hand" or "Sheet1")
        hand_sheet = None
        for name, df in sheets.items():
            if 'hand' in name.lower() or name == 'Sheet1':
                hand_sheet = df
                break
        
        if hand_sheet is None:
            hand_sheet = list(sheets.values())[0]
        
        hand_dataset = []
        
        for idx, row in hand_sheet.iterrows():
            try:
                # Get URLs from first two columns
                hand_url = row.iloc[0]
                style_url = row.iloc[1]
                
                # Handle NaN values
                if pd.isna(hand_url) or pd.isna(style_url):
                    continue
                
                hand_url = str(hand_url).strip()
                style_url = str(style_url).strip()
                
                # Skip invalid URLs
                if not hand_url.startswith('http'):
                    continue
                
                print(f"  Processing hand dataset row {idx + 1}...")
                
                # Download images
                hand_img = self.download_image(hand_url)
                style_img = self.download_image(style_url) if style_url.startswith('http') else None
                
                entry = {
                    'hand_id': idx,
                    'hand_url': hand_url,
                    'style_url': style_url if style_url.startswith('http') else None,
                    'hand_img': hand_img,
                    'style_img': style_img,
                }
                
                hand_dataset.append(entry)
                
            except Exception as e:
                print(f"  ⚠ Skipped row {idx}: {str(e)}")
                continue
        
        print(f"✓ Processed {len(hand_dataset)} hand samples")
        return hand_dataset
    
    def process_style_dataset(self, sheets: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        Process style dataset from Excel
        
        Expected Excel structure:
        - Column 1: Style raw image URL
        - Column 2: Style enhanced image URL
        
        Args:
            sheets: Dictionary of DataFrames
        
        Returns:
            List of style dataset entries
        """
        # Detect style sheet (usually second sheet or named "Style")
        style_sheet = None
        for name, df in sheets.items():
            if 'style' in name.lower() or name == 'Sheet2':
                style_sheet = df
                break
        
        if style_sheet is None:
            # Use second sheet if exists
            sheets_list = list(sheets.values())
            if len(sheets_list) > 1:
                style_sheet = sheets_list[1]
            else:
                raise ValueError("Cannot find style sheet")
        
        style_dataset = []
        
        for idx, row in style_sheet.iterrows():
            try:
                # Get URLs from first two columns
                raw_url = row.iloc[0]
                enhanced_url = row.iloc[1]
                
                # Handle NaN values
                if pd.isna(raw_url):
                    continue
                
                raw_url = str(raw_url).strip()
                enhanced_url = str(enhanced_url).strip() if not pd.isna(enhanced_url) else None
                
                # Skip invalid URLs
                if not raw_url.startswith('http'):
                    continue
                
                print(f"  Processing style dataset row {idx + 1}...")
                
                # Download images
                raw_img = self.download_image(raw_url)
                enhanced_img = None
                if enhanced_url and enhanced_url.startswith('http'):
                    enhanced_img = self.download_image(enhanced_url)
                
                entry = {
                    'style_id': idx,
                    'raw_url': raw_url,
                    'enhanced_url': enhanced_url,
                    'raw_img': raw_img,
                    'enhanced_img': enhanced_img,
                }
                
                style_dataset.append(entry)
                
            except Exception as e:
                print(f"  ⚠ Skipped row {idx}: {str(e)}")
                continue
        
        print(f"✓ Processed {len(style_dataset)} style samples")
        return style_dataset
    
    def get_all_data(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Load both hand and style datasets
        
        Returns:
            Tuple of (hand_dataset, style_dataset)
        """
        sheets = self.load_excel_sheets()
        
        print("\n📥 Processing hand dataset...")
        hand_dataset = self.process_hand_dataset(sheets)
        
        print("\n📥 Processing style dataset...")
        style_dataset = self.process_style_dataset(sheets)
        
        return hand_dataset, style_dataset
    
    def save_dataset_cache(self, 
                          hand_dataset: List[Dict],
                          style_dataset: List[Dict],
                          output_dir: str = './cache') -> None:
        """
        Save dataset metadata (without images) for reference
        
        Args:
            hand_dataset: Hand dataset
            style_dataset: Style dataset
            output_dir: Output directory
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Save hand dataset metadata
        hand_meta = [
            {k: v for k, v in entry.items() if k not in ['hand_img', 'style_img']}
            for entry in hand_dataset
        ]
        
        import json
        with open(output_dir / 'hand_dataset_meta.json', 'w') as f:
            json.dump(hand_meta, f, indent=2, default=str)
        
        # Save style dataset metadata
        style_meta = [
            {k: v for k, v in entry.items() if k not in ['raw_img', 'enhanced_img']}
            for entry in style_dataset
        ]
        
        with open(output_dir / 'style_dataset_meta.json', 'w') as f:
            json.dump(style_meta, f, indent=2, default=str)
        
        print(f"✓ Dataset metadata saved to {output_dir}")


# Example usage
if __name__ == "__main__":
    loader = DataLoader('./DATA.xlsx')
    print("DataLoader initialized")
