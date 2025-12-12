# Immich to GeekMagic Memory Uploader

This Python program fetches today's memories from your Immich server and uploads them to your GeekMagic device.

## Features

- Fetches memories from Immich server for today's date (from previous years)
- Downloads memory images
- Automatically resizes images to 240x240 pixels (perfect for GeekMagic display)
- Uploads images directly to GeekMagic device
- Configurable via environment variables

## Prerequisites

- Python 3.7 or higher
- Access to an Immich server with API key
- GeekMagic device on your network

## Installation

1. Install Python dependencies:
```powershell
pip install -r requirements.txt
```

## Configuration

The program uses environment variables for configuration:

### Required:
- `IMMICH_API_KEY`: Your Immich API key (get this from Immich UI: User Settings > Account Settings > API Keys)

### Optional:
- `IMMICH_URL`: Immich server URL (default: `http://192.168.1.18:2283`)
- `GEEKMAGIC_URL`: GeekMagic device URL (default: `http://192.168.1.107/`)
- `TEST_DATE`: Override the date to search for memories (format: `MM-DD` or `YYYY-MM-DD`)

## Usage

### PowerShell:

Set your Immich API key:
```powershell
$env:IMMICH_API_KEY = "your-api-key-here"
```

Run the program:
```powershell
python immich_to_geekmagic.py
```

### With custom configuration:
```powershell
$env:IMMICH_API_KEY = "your-api-key-here"
$env:IMMICH_URL = "http://192.168.1.18:2283"
$env:GEEKMAGIC_URL = "http://192.168.1.107/"
python immich_to_geekmagic.py
```

### To test with a specific date:
```powershell
$env:IMMICH_API_KEY = "your-api-key-here"
$env:TEST_DATE = "12-25"  # Search for Christmas memories
python immich_to_geekmagic.py
```

## How to Get Your Immich API Key

1. Open your Immich web interface
2. Click on your profile picture (top right)
3. Go to "Account Settings"
4. Navigate to "API Keys" tab
5. Click "New API Key"
6. Give it a name (e.g., "GeekMagic Uploader")
7. Copy the generated API key

## Troubleshooting

### "Error: IMMICH_API_KEY environment variable is required"
- Make sure you set the `IMMICH_API_KEY` environment variable before running the script

### "Error fetching memories"
- Check that your Immich server URL is correct
- Verify your API key is valid
- Ensure the Immich server is accessible from your machine

### "Error uploading image"
- Verify GeekMagic device URL is correct
- Check that the GeekMagic device is online and accessible

## Notes

- The program creates temporary files during download and resize which are automatically cleaned up
- Images are automatically resized to 240x240 pixels to optimize for the GeekMagic display
- Images are uploaded one at a time to avoid overwhelming the GeekMagic device
- The program searches for photos taken on today's date in previous years (1-10 years ago)

## License

This project is open source and available for personal use.
