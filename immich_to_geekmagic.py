#!/usr/bin/env python3
"""
Fetch today's memories from Immich server and upload them to GeekMagic.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import tempfile
from PIL import Image
from urllib.parse import quote
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ImmichClient:
    """Client for interacting with Immich API."""
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize Immich client.
        
        Args:
            base_url: Base URL of Immich server (e.g., http://192.168.1.18:2283)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'x-api-key': api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def get_user_info(self) -> Optional[Dict]:
        """Get the current user's information including their ID."""
        url = f"{self.base_url}/api/users/me"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting user info: {e}")
            return None
    
    def search_memories(self, target_date: Optional[datetime] = None) -> List[Dict]:
        """
        Search for today's memories (photos from this day in previous years).
        
        Args:
            target_date: The date to search for (default: today)
        
        Returns:
            List of memory assets
        """
        today = target_date or datetime.now()
        
        print(f"Searching for memories on this day ({today.month}/{today.day})...")
        
        # Search for assets from this day/month in previous years
        # We'll search from 1-10 years ago
        url = f"{self.base_url}/api/search/metadata"
        
        memories = []
        
        for years_ago in range(1, 11):  # Search 1-10 years ago
            target_year = today.year - years_ago
            
            # Create date range for this specific day in the past year
            start_date = f"{target_year}-{today.month:02d}-{today.day:02d}T00:00:00.000Z"
            end_date = f"{target_year}-{today.month:02d}-{today.day:02d}T23:59:59.999Z"
            
            search_payload = {
                "takenAfter": start_date,
                "takenBefore": end_date
            }
            
            try:
                response = requests.post(url, headers=self.headers, json=search_payload)
                response.raise_for_status()
                result = response.json()
                
                # Get assets from the search results
                assets = result.get('assets', {}).get('items', [])
                if assets:
                    print(f"  Found {len(assets)} memories from {target_year}")
                    memories.extend(assets)
                    
            except requests.exceptions.RequestException as e:
                # Continue searching other years even if one fails
                continue
        
        if memories:
            years = {}
            for memory in memories:
                date_str = (
                    memory.get('exifInfo', {}).get('dateTimeOriginal') or 
                    memory.get('fileCreatedAt') or
                    memory.get('createdAt')
                )
                if date_str:
                    try:
                        if date_str.endswith('Z'):
                            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:
                            date = datetime.fromisoformat(date_str)
                        years[date.year] = years.get(date.year, 0) + 1
                    except:
                        pass
            if years:
                print(f"\nTotal: {len(memories)} memories from years: {sorted(years.keys())}")
        else:
            print("No memories found for this day in previous years")
        
        return memories
    
    def download_asset(self, asset_id: str, output_path: str) -> bool:
        """
        Download an asset from Immich.
        
        Args:
            asset_id: ID of the asset to download
            output_path: Path to save the downloaded file
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/api/assets/{asset_id}/original"
        
        try:
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Downloaded asset {asset_id} to {output_path}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error downloading asset {asset_id}: {e}")
            return False


class GeekMagicClient:
    """Client for uploading to GeekMagic."""
    
    def __init__(self, base_url: str):
        """
        Initialize GeekMagic client.
        
        Args:
            base_url: Base URL of GeekMagic device (e.g., http://192.168.1.107/)
        """
        self.base_url = base_url.rstrip('/')
    
    def get_file_list(self) -> List[str]:
        """
        Get list of existing files on GeekMagic device.
        
        Returns:
            List of filenames
        """
        try:
            url = f"{self.base_url}/filelist?dir=/image/"
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse the response - it might be JSON or HTML
            try:
                data = response.json()
                # If it's JSON, extract filenames
                if isinstance(data, list):
                    return [item.get('name', item) if isinstance(item, dict) else str(item) for item in data]
                elif isinstance(data, dict) and 'files' in data:
                    return [f.get('name', f) if isinstance(f, dict) else str(f) for f in data['files']]
                return []
            except json.JSONDecodeError:
                # Parse HTML response to extract filenames
                import re
                html = response.text
                # Look for href='/image//filename' patterns
                pattern = r"href='/image//([^']+)'"
                matches = re.findall(pattern, html)
                return matches
                
        except requests.exceptions.RequestException as e:
            print(f"Error getting file list: {e}")
            return []
    
    def delete_file(self, filename: str) -> bool:
        """
        Delete a file from GeekMagic device.
        
        Args:
            filename: Name of the file to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use the delete endpoint with proper path format
            # Note: The path uses double slash (/image//)
            file_path = f"/image//{filename}"
            url = f"{self.base_url}/delete?file={quote(file_path)}"
            
            response = requests.get(url)
            response.raise_for_status()
            
            print(f"Deleted {filename} from GeekMagic")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error deleting {filename}: {e}")
            return False
    
    def resize_image(self, input_path: str, output_path: str, size: tuple = (240, 240)) -> bool:
        """
        Resize and crop an image to fill the specified size without black bars.
        
        Args:
            input_path: Path to the input image
            output_path: Path to save the resized image
            size: Target size as (width, height) tuple
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with Image.open(input_path) as img:
                # Convert RGBA to RGB if necessary
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Calculate the aspect ratios
                img_aspect = img.width / img.height
                target_aspect = size[0] / size[1]
                
                # Crop to match target aspect ratio, then resize
                if img_aspect > target_aspect:
                    # Image is wider than target - crop width
                    new_width = int(img.height * target_aspect)
                    left = (img.width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, img.height))
                else:
                    # Image is taller than target - crop height
                    new_height = int(img.width / target_aspect)
                    top = (img.height - new_height) // 2
                    img = img.crop((0, top, img.width, top + new_height))
                
                # Now resize to exact target size
                img = img.resize(size, Image.Resampling.LANCZOS)
                
                # Save as JPEG
                img.save(output_path, 'JPEG', quality=85)
                
            return True
        except Exception as e:
            print(f"Error resizing image: {e}")
            return False
    
    def upload_image_direct(self, image_path: str) -> bool:
        """
        Upload an image directly to GeekMagic without PHP processing.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            upload_url = f"{self.base_url}/doUpload?dir=%2Fimage%2F"
            print(f"Uploading directly to GeekMagic at {upload_url}...")
            
            filename = os.path.basename(image_path)
            
            # Read the entire file into memory to avoid Content-Length issues
            with open(image_path, 'rb') as f:
                file_data = f.read()
            
            files = {
                'file': (filename, file_data, 'image/jpeg')
            }
            
            response = requests.post(upload_url, files=files)
            response.raise_for_status()
            
            print(f"Successfully uploaded {filename} to GeekMagic")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error uploading image: {e}")
            return False


def main():
    """Main function to fetch memories and upload to GeekMagic."""
    
    # Configuration - all values loaded from .env file
    IMMICH_URL = os.getenv('IMMICH_URL')
    IMMICH_API_KEY = os.getenv('IMMICH_API_KEY')
    GEEKMAGIC_URL = os.getenv('GEEKMAGIC_URL')
    
    # Allow overriding the date for testing (format: MM-DD or YYYY-MM-DD)
    TEST_DATE = os.getenv('TEST_DATE', '')
    
    # Validate required environment variables
    if not IMMICH_API_KEY:
        print("Error: IMMICH_API_KEY is required")
        print("Please set it in your .env file")
        sys.exit(1)
    
    if not IMMICH_URL:
        print("Error: IMMICH_URL is required")
        print("Please set it in your .env file")
        sys.exit(1)
    
    if not GEEKMAGIC_URL:
        print("Error: GEEKMAGIC_URL is required")
        print("Please set it in your .env file")
        sys.exit(1)
    
    # Parse test date if provided
    search_date = None
    if TEST_DATE:
        try:
            if len(TEST_DATE) == 5:  # MM-DD format
                month, day = map(int, TEST_DATE.split('-'))
                search_date = datetime.now().replace(month=month, day=day)
            else:  # YYYY-MM-DD format
                search_date = datetime.fromisoformat(TEST_DATE)
        except Exception as e:
            print(f"Warning: Could not parse TEST_DATE '{TEST_DATE}': {e}")
            print("Using today's date instead")
    
    print("="*60)
    print("Immich to GeekMagic Memory Uploader")
    print("="*60)
    print(f"Immich Server: {IMMICH_URL}")
    print(f"GeekMagic Device: {GEEKMAGIC_URL}")
    print(f"Image Resize: 240x240 pixels")
    if search_date:
        print(f"Search Date: {search_date.strftime('%B %d')} (testing mode)")
    print("="*60)
    
    # Initialize clients
    immich = ImmichClient(IMMICH_URL, IMMICH_API_KEY)
    geekmagic = GeekMagicClient(GEEKMAGIC_URL)
    
    # Fetch memories
    print("\nFetching memories from Immich...")
    memories = immich.search_memories(search_date)
    
    if not memories:
        print("No memories found for today.")
        return
    
    # Get existing files on GeekMagic
    print("\nChecking existing files on GeekMagic...")
    existing_files = geekmagic.get_file_list()
    print(f"Found {len(existing_files)} existing files on device")
    
    # Build list of asset ID suffixes we're going to upload
    memory_suffixes = set()
    for memory in memories:
        asset_id = memory.get('id') or memory.get('assetId')
        if asset_id:
            # Get the last part of the UUID (what appears in truncated filenames)
            asset_suffix = asset_id.split('-')[-1]
            memory_suffixes.add(asset_suffix)
    
    # Delete files that aren't in our upload list
    deleted_count = 0
    for existing_file in existing_files:
        # Check if this file corresponds to any current memory
        should_keep = any(suffix in existing_file for suffix in memory_suffixes)
        if not should_keep:
            if geekmagic.delete_file(existing_file):
                deleted_count += 1
    
    if deleted_count > 0:
        print(f"Deleted {deleted_count} old files from device")
    
    # Process each memory
    uploaded_count = 0
    skipped_count = 0
    failed_count = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, memory in enumerate(memories, 1):
            print(f"\n[{i}/{len(memories)}] Processing memory...")
            
            # Extract asset ID (API structure may vary)
            asset_id = memory.get('id') or memory.get('assetId')
            if not asset_id:
                print("Warning: Could not find asset ID in memory")
                failed_count += 1
                continue
            
            # Check if file already exists on device
            # The device may truncate filenames, so check if any existing file contains the asset_id suffix
            target_filename = f"resized_{asset_id}.jpg"
            asset_suffix = asset_id.split('-')[-1]  # Get last part of UUID
            already_exists = any(asset_suffix in existing_file for existing_file in existing_files)
            
            if already_exists:
                print(f"Skipping {asset_id} - already on device")
                skipped_count += 1
                continue
            
            # Download the asset
            temp_file = os.path.join(temp_dir, f"memory_{asset_id}.jpg")
            if not immich.download_asset(asset_id, temp_file):
                failed_count += 1
                continue
            
            # Resize the image to 240x240
            resized_file = os.path.join(temp_dir, target_filename)
            if not geekmagic.resize_image(temp_file, resized_file, (240, 240)):
                print("Warning: Failed to resize image, uploading original")
                resized_file = temp_file
            
            # Upload to GeekMagic
            success = geekmagic.upload_image_direct(resized_file)
            
            if success:
                uploaded_count += 1
            else:
                failed_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("Upload Summary")
    print("="*60)
    print(f"Total memories: {len(memories)}")
    print(f"Successfully uploaded: {uploaded_count}")
    print(f"Skipped (already on device): {skipped_count}")
    print(f"Failed: {failed_count}")
    if deleted_count > 0:
        print(f"Old files deleted: {deleted_count}")
    print("="*60)


if __name__ == "__main__":
    main()
