#!/usr/bin/env python3
"""
Fetch today's memories from Immich server and upload them to GeekMagic.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import tempfile
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import quote
from dotenv import load_dotenv

try:
    from moviepy import VideoFileClip
    import numpy as np
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: moviepy not installed. Video conversion will be disabled.")
    print("Install with: pip install moviepy")

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
            
            # Check content type to ensure it's an image or video
            content_type = response.headers.get('content-type', '').lower()
            if not (content_type.startswith('image/') or content_type.startswith('video/')):
                print(f"Skipping asset {asset_id} - not an image or video (type: {content_type})")
                return False
            
            is_video = content_type.startswith('video/')
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify the file was downloaded and is not empty
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                print(f"Error: Downloaded file is empty for asset {asset_id}")
                return False
            
            # Verify it's a valid image (skip verification for videos)
            if not is_video:
                try:
                    with Image.open(output_path) as img:
                        img.verify()  # Verify it's a valid image
                except Exception as e:
                    print(f"Error: Downloaded file is not a valid image for asset {asset_id}: {e}")
                    return False
            
            file_size_kb = file_size / 1024
            asset_type = "video" if is_video else "image"
            print(f"Downloaded {asset_type} {asset_id} ({file_size_kb:.1f} KB)")
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
    
    def check_connection(self, timeout: int = 5) -> bool:
        """
        Check if GeekMagic device is accessible.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            True if device is accessible, False otherwise
        """
        try:
            response = requests.get(self.base_url, timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_file_list(self) -> List[Dict[str, Any]]:
        """
        Get list of existing files on GeekMagic device with their sizes.
        
        Returns:
            List of dicts with 'name' and 'size' (in bytes, or None if unavailable)
        """
        try:
            url = f"{self.base_url}/filelist?dir=/image/"
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse the response - it might be JSON or HTML
            try:
                data = response.json()
                # If it's JSON, extract filenames and sizes
                if isinstance(data, list):
                    return [
                        {'name': item.get('name', item) if isinstance(item, dict) else str(item),
                         'size': item.get('size') if isinstance(item, dict) else None}
                        for item in data
                    ]
                elif isinstance(data, dict) and 'files' in data:
                    return [
                        {'name': f.get('name', f) if isinstance(f, dict) else str(f),
                         'size': f.get('size') if isinstance(f, dict) else None}
                        for f in data['files']
                    ]
                return []
            except json.JSONDecodeError:
                # Parse HTML response to extract filenames only
                import re
                html = response.text
                # Look for href='/image//filename' patterns
                pattern = r"href='/image//([^']+)'"
                matches = re.findall(pattern, html)
                return [{'name': m, 'size': None} for m in matches]
                
        except requests.exceptions.RequestException as e:
            print(f"Error getting file list: {e}")
            return []

    def get_file_size_kb(self, filename: str) -> Optional[float]:
        """
        Attempt to determine the file size on the GeekMagic device for a given filename.

        Returns the size in KB if available, otherwise None.
        """
        try:
            # The device serves files under /image//<filename>
            file_path = f"/image//{filename}"
            url = f"{self.base_url}{file_path}"

            # Use HEAD if available to get Content-Length
            head = requests.head(url, allow_redirects=True, timeout=5)
            if head.status_code == 200:
                cl = head.headers.get('content-length')
                if cl and cl.isdigit():
                    return int(cl) / 1024.0

            # Fallback to GET with range to avoid downloading whole file
            # Request first byte to get headers
            r = requests.get(url, stream=True, timeout=5)
            r.raise_for_status()
            cl = r.headers.get('content-length')
            if cl and cl.isdigit():
                return int(cl) / 1024.0

        except requests.exceptions.RequestException:
            pass

        return None

    def get_used_space_kb(self) -> float:
        """
        Compute the total used space (in KB) of files under /image/ on the device
        using sizes from the API response.

        Returns 0.0 if sizes cannot be determined.
        """
        files = self.get_file_list()
        total = 0.0
        for f in files:
            if f.get('size') is not None:
                total += f['size'] / 1024.0
            else:
                # Fallback: try to get size via HEAD request
                size_kb = self.get_file_size_kb(f['name'])
                if size_kb is not None:
                    total += size_kb
        return total
    
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
    
    def resize_image(self, input_path: str, output_path: str, size: tuple = (240, 240), photo_datetime: Optional[datetime] = None) -> bool:
        """
        Resize and crop an image to fill the specified size without black bars.
        
        Args:
            input_path: Path to the input image
            output_path: Path to save the resized image
            size: Target size as (width, height) tuple
            photo_datetime: Optional datetime when photo was taken (for year overlay)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with Image.open(input_path) as img:
                # Apply EXIF orientation to prevent rotated images
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass  # If EXIF orientation fails, continue without it
                
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
                
                # Draw year text on the image if provided
                if photo_datetime:
                    draw = ImageDraw.Draw(img)
                    year_text = str(photo_datetime.year)
                    
                    # Try to use a nice font with proper size
                    font = None
                    font_size = int(size[1] * 0.15)  # 15% of image height
                    
                    # Try multiple font paths (Windows, Linux/Docker)
                    font_paths = [
                        "arial.ttf",  # Windows
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux/Docker
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Alternative Linux
                        "/System/Library/Fonts/Helvetica.ttc",  # macOS
                    ]
                    
                    for font_path in font_paths:
                        try:
                            font = ImageFont.truetype(font_path, font_size)
                            break
                        except:
                            continue
                    
                    # If no TrueType font found, we'll draw larger text manually
                    if not font:
                        font = ImageFont.load_default()
                    
                    # Get text bounding box
                    if font:
                        bbox = draw.textbbox((0, 0), year_text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                    else:
                        # Rough estimate if font fails
                        text_width = len(year_text) * 8
                        text_height = 12
                    
                    # Position at bottom center with some padding
                    x = (size[0] - text_width) // 2
                    y = int(size[1] * 0.88) - text_height  # 12% from bottom
                    
                    # Choose color based on time of day photo was taken
                    hour = photo_datetime.hour
                    
                    if 6 <= hour < 12:
                        # Morning (6 AM - 12 PM): Gold/Yellow
                        text_color = (255, 215, 0)  # Gold
                        shadow_color = (139, 115, 0)  # Dark goldenrod
                    elif 12 <= hour < 18:
                        # Afternoon (12 PM - 6 PM): Orange
                        text_color = (255, 140, 0)  # Dark orange
                        shadow_color = (139, 69, 0)  # Saddle brown
                    elif 18 <= hour < 21:
                        # Evening (6 PM - 9 PM): Purple/Magenta
                        text_color = (255, 0, 255)  # Magenta
                        shadow_color = (139, 0, 139)  # Dark magenta
                    else:
                        # Night (9 PM - 6 AM): Blue
                        text_color = (0, 191, 255)  # Deep sky blue
                        shadow_color = (0, 0, 139)  # Dark blue
                    
                    # Draw text with shadow for better visibility
                    # Shadow
                    draw.text((x + 2, y + 2), year_text, fill=shadow_color, font=font)
                    # Main text
                    draw.text((x, y), year_text, fill=text_color, font=font)
                
                # Save as JPEG
                img.save(output_path, 'JPEG', quality=85)
                
            return True
        except Exception as e:
            print(f"Error resizing image: {e}")
            return False
    
    def convert_video_to_gif(self, input_path: str, output_path: str, size: tuple = (240, 240), 
                           photo_datetime: Optional[datetime] = None, max_duration: int = 3, fps: int = 5) -> bool:
        """
        Convert a video to an animated GIF.
        
        Args:
            input_path: Path to the input video
            output_path: Path to save the GIF
            size: Target size as (width, height) tuple
            photo_datetime: Optional datetime when video was taken (for year overlay)
            max_duration: Maximum duration in seconds (default: 3)
            fps: Frames per second for the GIF (default: 5)
            
        Returns:
            True if successful, False otherwise
        """
        if not MOVIEPY_AVAILABLE:
            print("Error: moviepy not installed, cannot convert video")
            return False
        
        try:
            # Load video
            with VideoFileClip(input_path) as video:
                # Limit duration
                if video.duration > max_duration:
                    video = video.subclipped(0, max_duration)
                
                # Resize video maintaining aspect ratio and cropping
                video_aspect = video.w / video.h
                target_aspect = size[0] / size[1]
                
                if video_aspect > target_aspect:
                    # Video is wider - crop width
                    new_width = int(video.h * target_aspect)
                    x_center = video.w / 2
                    x1 = int(x_center - new_width/2)
                    x2 = int(x_center + new_width/2)
                    video = video.cropped(x1=x1, x2=x2)
                else:
                    # Video is taller - crop height
                    new_height = int(video.w / target_aspect)
                    y_center = video.h / 2
                    y1 = int(y_center - new_height/2)
                    y2 = int(y_center + new_height/2)
                    video = video.cropped(y1=y1, y2=y2)
                
                # Resize to target size
                video = video.resized(height=size[1], width=size[0])
                
                # Extract frames and add year overlay
                if photo_datetime:
                    def add_year_overlay(get_frame, t):
                        frame = get_frame(t)
                        img = Image.fromarray(frame.astype('uint8'))
                        draw = ImageDraw.Draw(img)
                        year_text = str(photo_datetime.year)
                        
                        # Try to use a nice font with proper size
                        font = None
                        font_size = int(size[1] * 0.15)
                        
                        # Try multiple font paths (Windows, Linux/Docker)
                        font_paths = [
                            "arial.ttf",
                            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                            "/System/Library/Fonts/Helvetica.ttc",
                        ]
                        
                        for font_path in font_paths:
                            try:
                                font = ImageFont.truetype(font_path, font_size)
                                break
                            except:
                                continue
                        
                        if not font:
                            font = ImageFont.load_default()
                        
                        # Get text size
                        if font:
                            bbox = draw.textbbox((0, 0), year_text, font=font)
                            text_width = bbox[2] - bbox[0]
                            text_height = bbox[3] - bbox[1]
                        else:
                            text_width = len(year_text) * 8
                            text_height = 12
                        
                        # Position at bottom center
                        x = (size[0] - text_width) // 2
                        y = int(size[1] * 0.88) - text_height
                        
                        # Choose color based on time of day
                        hour = photo_datetime.hour
                        if 6 <= hour < 12:
                            text_color = (255, 215, 0)  # Gold
                            shadow_color = (139, 115, 0)
                        elif 12 <= hour < 18:
                            text_color = (255, 140, 0)  # Orange
                            shadow_color = (139, 69, 0)
                        elif 18 <= hour < 21:
                            text_color = (255, 0, 255)  # Magenta
                            shadow_color = (139, 0, 139)
                        else:
                            text_color = (0, 191, 255)  # Blue
                            shadow_color = (0, 0, 139)
                        
                        # Draw text with shadow
                        draw.text((x + 2, y + 2), year_text, fill=shadow_color, font=font)
                        draw.text((x, y), year_text, fill=text_color, font=font)
                        
                        return np.array(img)
                    
                    video = video.transform(add_year_overlay)
                
                # Save as GIF with reduced colors for smaller file size
                video.write_gif(output_path, fps=fps, logger=None)
            
            return True
        except Exception as e:
            print(f"Error converting video to GIF: {e}")
            if 'video' in locals():
                try:
                    video.close()
                except:
                    pass
            return False
    
    def upload_image_direct(self, image_path: str) -> tuple[bool, float]:
        """
        Upload an image directly to GeekMagic without PHP processing.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (success: bool, file_size_kb: float)
        """
        try:
            upload_url = f"{self.base_url}/doUpload?dir=%2Fimage%2F"
            
            filename = os.path.basename(image_path)
            
            # Read file content
            with open(image_path, 'rb') as f:
                file_content = f.read()
            
            file_size_kb = len(file_content) / 1024
            
            print(f"Uploading {filename} ({file_size_kb:.1f} KB) to GeekMagic...")
            
            # Determine mime type based on file extension
            mime_type = 'image/gif' if filename.lower().endswith('.gif') else 'image/jpeg'
            
            # Use a fresh session to avoid connection reuse issues
            session = requests.Session()
            
            # Pass raw bytes directly in tuple format
            files = {
                'file': (filename, file_content, mime_type)
            }
            
            # Post without manually setting Content-Length, use fresh session
            response = session.post(upload_url, files=files)
            response.raise_for_status()
            session.close()
            
            print(f"✓ Successfully uploaded {filename} ({file_size_kb:.1f} KB)")
            return True, file_size_kb
            
        except requests.exceptions.RequestException as e:
            print(f"Error uploading image: {e}")
            if 'session' in locals():
                session.close()
            return False, 0.0


def wait_for_geekmagic(geekmagic: GeekMagicClient, max_retries: int = 10, retry_delay: int = 300) -> bool:
    """
    Wait for GeekMagic device to become available with retry logic.
    
    Args:
        geekmagic: GeekMagicClient instance
        max_retries: Maximum number of connection attempts
        retry_delay: Delay between retries in seconds (default: 5 minutes)
        
    Returns:
        True if connection successful, False if max retries reached
    """
    for attempt in range(1, max_retries + 1):
        print(f"\nAttempt {attempt}/{max_retries}: Checking GeekMagic connection...")
        
        if geekmagic.check_connection():
            print("✓ GeekMagic device is online and accessible")
            return True
        
        if attempt < max_retries:
            current_time = datetime.now().strftime("%H:%M:%S")
            next_retry = datetime.now() + timedelta(seconds=retry_delay)
            print(f"✗ GeekMagic device is not accessible at {current_time}")
            print(f"  Waiting {retry_delay // 60} minutes before next attempt...")
            print(f"  Next retry at: {next_retry.strftime('%H:%M:%S')}")
            time.sleep(retry_delay)
        else:
            print(f"✗ GeekMagic device unreachable after {max_retries} attempts")
    
    return False


def main():
    """Main function to fetch memories and upload to GeekMagic."""
    
    # Configuration - all values loaded from .env file
    IMMICH_URL = os.getenv('IMMICH_URL')
    IMMICH_API_KEY = os.getenv('IMMICH_API_KEY')
    GEEKMAGIC_URL = os.getenv('GEEKMAGIC_URL')
    
    # Retry configuration
    MAX_RETRIES = int(os.getenv('GEEKMAGIC_MAX_RETRIES', '10'))
    RETRY_DELAY = int(os.getenv('GEEKMAGIC_RETRY_DELAY', '300'))  # 5 minutes default
    
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
    
    # Wait for GeekMagic device to be available
    print("\nWaiting for GeekMagic device to be available...")
    if not wait_for_geekmagic(geekmagic, MAX_RETRIES, RETRY_DELAY):
        print("\n❌ Could not connect to GeekMagic device. Please check:")
        print("  1. Device is powered on")
        print("  2. Device is connected to network")
        print("  3. URL is correct in .env file")
        print(f"  4. Expected connection window: 7:50 AM - 10:00 AM")
        sys.exit(1)
    
    # Get existing files on GeekMagic
    print("\nChecking existing files on GeekMagic...")
    existing_files = geekmagic.get_file_list()
    print(f"Found {len(existing_files)} existing files on device")

    # Determine total device space (KB) from env or default
    DEFAULT_TOTAL_SPACE_KB = int(os.getenv('GEEKMAGIC_TOTAL_SPACE_KB', '600'))
    total_device_kb = DEFAULT_TOTAL_SPACE_KB

    # Try to compute currently used space
    used_space_kb = geekmagic.get_used_space_kb()
    if used_space_kb and used_space_kb > 0:
        print(f"Device reports ~{used_space_kb:.1f} KB used")
        # If used space exceeds default total, keep default but warn
        if used_space_kb > total_device_kb:
            print(f"Warning: used space ({used_space_kb:.1f} KB) exceeds configured total ({total_device_kb} KB).")
        remaining_kb = max(total_device_kb - used_space_kb, 0.0)
    else:
        # Fallback: assume nothing used
        used_space_kb = 0.0
        remaining_kb = float(total_device_kb)

    print(f"Disk space: {used_space_kb:.1f} KB used / {total_device_kb} KB total ({remaining_kb:.1f} KB free)")
    
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
    deleted_size_kb = 0.0
    for existing_file in existing_files:
        filename = existing_file['name']
        file_size = existing_file.get('size', 0)
        # Check if this file corresponds to any current memory
        should_keep = any(suffix in filename for suffix in memory_suffixes)
        if not should_keep:
            if geekmagic.delete_file(filename):
                deleted_count += 1
                if file_size:
                    deleted_size_kb += file_size / 1024.0

    # If we deleted files, refresh used/remaining space
    if deleted_count > 0:
        print(f"Deleted {deleted_count} old files (~{deleted_size_kb:.1f} KB freed)")
        used_space_kb = geekmagic.get_used_space_kb()
        remaining_kb = max(total_device_kb - used_space_kb, 0.0)
        print(f"After deletion: {used_space_kb:.1f} KB used / {remaining_kb:.1f} KB free")
    
    # PHASE 1: Process all memories and calculate sizes
    print("\n" + "="*60)
    print("PHASE 1: Processing all memories...")
    print("="*60)
    
    processed_memories = []  # List of dicts with memory info, file path, size, year
    already_on_device = 0
    failed_processing = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, memory in enumerate(memories, 1):
            print(f"\n[{i}/{len(memories)}] Processing memory...")
            
            # Extract asset ID (API structure may vary)
            asset_id = memory.get('id') or memory.get('assetId')
            if not asset_id:
                print("Warning: Could not find asset ID in memory")
                failed_processing += 1
                continue
            
            # Determine asset type
            asset_type = memory.get('type', '').upper()
            is_video = asset_type == 'VIDEO'
            
            # Check if file already exists on device
            file_ext = ".gif" if is_video else ".jpg"
            target_filename = f"resized_{asset_id}{file_ext}"
            asset_suffix = asset_id.split('-')[-1]
            already_exists = any(asset_suffix in f['name'] for f in existing_files)
            
            if already_exists:
                print(f"Already on device: {asset_id}")
                already_on_device += 1
                continue
            
            # Extract datetime from memory metadata
            photo_datetime = None
            photo_year = None
            date_str = (
                memory.get('exifInfo', {}).get('dateTimeOriginal') or 
                memory.get('fileCreatedAt') or
                memory.get('createdAt')
            )
            if date_str:
                try:
                    if date_str.endswith('Z'):
                        photo_datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        photo_datetime = datetime.fromisoformat(date_str)
                    photo_year = photo_datetime.year
                    print(f"Memory from {photo_datetime.strftime('%Y-%m-%d %H:%M')}")
                except:
                    pass
            
            # Download the asset
            temp_ext = ".mp4" if is_video else ".jpg"
            temp_file = os.path.join(temp_dir, f"memory_{asset_id}{temp_ext}")
            if not immich.download_asset(asset_id, temp_file):
                failed_processing += 1
                continue
            
            # Process the asset (resize image or convert video to GIF)
            resized_file = os.path.join(temp_dir, target_filename)
            if is_video:
                if not MOVIEPY_AVAILABLE:
                    print(f"Skipping video {asset_id} - moviepy not installed")
                    failed_processing += 1
                    continue
                if not geekmagic.convert_video_to_gif(temp_file, resized_file, (240, 240), photo_datetime):
                    print("Warning: Failed to convert video to GIF")
                    failed_processing += 1
                    continue
            else:
                if not geekmagic.resize_image(temp_file, resized_file, (240, 240), photo_datetime):
                    print("Warning: Failed to resize image")
                    failed_processing += 1
                    continue
            
            # Get file size
            try:
                file_size_kb = os.path.getsize(resized_file) / 1024.0
                print(f"Processed: {file_size_kb:.1f} KB")
                
                # Store processed memory info
                processed_memories.append({
                    'memory': memory,
                    'asset_id': asset_id,
                    'file_path': resized_file,
                    'filename': target_filename,
                    'size_kb': file_size_kb,
                    'year': photo_year or 'unknown',
                    'datetime': photo_datetime
                })
            except Exception as e:
                print(f"Warning: Could not determine file size: {e}")
                failed_processing += 1
                continue
        
        # PHASE 2: Select memories to upload with fair distribution across years
        print("\n" + "="*60)
        print("PHASE 2: Selecting memories for upload...")
        print("="*60)
        
        # Group by year
        memories_by_year = {}
        for pm in processed_memories:
            year = pm['year']
            if year not in memories_by_year:
                memories_by_year[year] = []
            memories_by_year[year].append(pm)
        
        # Show distribution
        print(f"\nProcessed {len(processed_memories)} new memories:")
        for year in sorted(memories_by_year.keys()):
            count = len(memories_by_year[year])
            total_size = sum(m['size_kb'] for m in memories_by_year[year])
            print(f"  {year}: {count} memories ({total_size:.1f} KB)")
        
        print(f"\nAvailable space: {remaining_kb:.1f} KB")
        
        # Calculate total needed space
        total_needed_kb = sum(m['size_kb'] for m in processed_memories)
        print(f"Total space needed: {total_needed_kb:.1f} KB")
        
        # Select memories using round-robin across years
        selected_for_upload = []
        
        if total_needed_kb <= remaining_kb:
            # All fit - upload everything
            print("✓ All memories fit! Uploading all processed memories.")
            selected_for_upload = processed_memories
        else:
            # Need to select subset - use round-robin across years
            # Prioritize photos (JPGs) over videos (GIFs) to save space
            print("⚠ Not all memories fit. Selecting balanced subset across years...")
            print("  Prioritizing photos over videos (GIFs) to maximize count...")
            
            # Separate photos and GIFs by year
            photos_by_year = {}
            gifs_by_year = {}
            
            for year in memories_by_year:
                photos_by_year[year] = [m for m in memories_by_year[year] if not m['filename'].endswith('.gif')]
                gifs_by_year[year] = [m for m in memories_by_year[year] if m['filename'].endswith('.gif')]
            
            available_space = remaining_kb
            years = sorted(photos_by_year.keys())
            
            # PHASE 2A: Round-robin selection of photos first
            photo_indices = {year: 0 for year in years}
            
            while available_space > 0 and any(photo_indices[y] < len(photos_by_year[y]) for y in years):
                for year in years:
                    if photo_indices[year] < len(photos_by_year[year]):
                        candidate = photos_by_year[year][photo_indices[year]]
                        if candidate['size_kb'] <= available_space:
                            selected_for_upload.append(candidate)
                            available_space -= candidate['size_kb']
                            photo_indices[year] += 1
                        else:
                            photo_indices[year] += 1  # Skip this one, too large
                    
                    if available_space <= 0:
                        break
            
            # PHASE 2B: If space remains, add GIFs using round-robin
            if available_space > 0:
                print(f"  Space remaining after photos: {available_space:.1f} KB, adding GIFs...")
                gif_indices = {year: 0 for year in years}
                
                while available_space > 0 and any(gif_indices[y] < len(gifs_by_year.get(y, [])) for y in years):
                    for year in years:
                        if year in gifs_by_year and gif_indices[year] < len(gifs_by_year[year]):
                            candidate = gifs_by_year[year][gif_indices[year]]
                            if candidate['size_kb'] <= available_space:
                                selected_for_upload.append(candidate)
                                available_space -= candidate['size_kb']
                                gif_indices[year] += 1
                            else:
                                gif_indices[year] += 1  # Skip this one, too large
                        
                        if available_space <= 0:
                            break
            
            # Show selection summary
            selected_by_year = {}
            photos_selected = sum(1 for m in selected_for_upload if not m['filename'].endswith('.gif'))
            gifs_selected = sum(1 for m in selected_for_upload if m['filename'].endswith('.gif'))
            
            for m in selected_for_upload:
                year = m['year']
                selected_by_year[year] = selected_by_year.get(year, 0) + 1
            
            print(f"\nSelected {len(selected_for_upload)} memories for upload:")
            print(f"  Photos: {photos_selected}, GIFs: {gifs_selected}")
            for year in sorted(selected_by_year.keys()):
                print(f"  {year}: {selected_by_year[year]} memories")
        
        # PHASE 3: Upload selected memories
        print("\n" + "="*60)
        print("PHASE 3: Uploading selected memories...")
        print("="*60)
        
        uploaded_count = 0
        failed_upload = 0
        total_uploaded_kb = 0.0
        
        for i, pm in enumerate(selected_for_upload, 1):
            print(f"\n[{i}/{len(selected_for_upload)}] Uploading {pm['filename']}...")
            
            success, uploaded_kb = geekmagic.upload_image_direct(pm['file_path'])
            
            if success:
                uploaded_count += 1
                total_uploaded_kb += uploaded_kb
                remaining_kb = max(remaining_kb - uploaded_kb, 0.0)
            else:
                failed_upload += 1
        
        # Calculate final counts
        skipped_count = len(processed_memories) - len(selected_for_upload)
        failed_count = failed_processing + failed_upload
    
    # Summary
    print("\n" + "="*60)
    print("Upload Summary")
    print("="*60)
    print(f"Total memories found: {len(memories)}")
    print(f"Already on device: {already_on_device}")
    print(f"Newly processed: {len(processed_memories)}")
    if len(processed_memories) > len(selected_for_upload):
        print(f"Selected for upload: {len(selected_for_upload)} (balanced across years)")
        print(f"Not uploaded (space limit): {skipped_count}")
    print(f"Successfully uploaded: {uploaded_count}")
    print(f"Failed: {failed_count}")
    if deleted_count > 0:
        print(f"Old files deleted: {deleted_count}")
    
    # Report device space status
    used_after_kb = geekmagic.get_used_space_kb() or (total_device_kb - remaining_kb)
    free_after_kb = max(total_device_kb - used_after_kb, 0.0)
    print(f"\nDevice space used: {used_after_kb:.1f} KB / {total_device_kb} KB ({(used_after_kb/total_device_kb*100) if total_device_kb else 0:.1f}%)")
    if free_after_kb <= total_device_kb * 0.1:
        print("⚠️  Warning: Disk space is near capacity!")
    print("="*60)


if __name__ == "__main__":
    main()
