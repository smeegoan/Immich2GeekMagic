# Immich to GeekMagic Memory Uploader

This Python program fetches today's memories from your Immich server and uploads them to your GeekMagic device.

## Features

- Fetches memories from Immich server for today's date (from previous years)
- Downloads memory images
- Automatically resizes images to 240x240 pixels (perfect for GeekMagic display)
- Preserves image orientation (fixes rotated photos)
- Uploads images directly to GeekMagic device
- **Automatic retry logic** for when GeekMagic device is offline
- **Docker/Portainer support** with scheduled execution
- Configurable via environment variables

## Prerequisites

- Docker and Docker Compose (recommended) OR Python 3.7+
- Access to an Immich server with API key
- GeekMagic device on your network

## Quick Start with Docker

1. Build the Docker image:
```bash
docker build -t immich-geekmagic-sync .
```

2. Run with environment variables:
```bash
docker run --rm \
  -e IMMICH_URL=http://192.168.1.18:2283 \
  -e IMMICH_API_KEY=your-api-key-here \
  -e GEEKMAGIC_URL=http://192.168.1.107 \
  -e GEEKMAGIC_MAX_RETRIES=10 \
  -e GEEKMAGIC_RETRY_DELAY=300 \
  immich-geekmagic-sync
```

3. Or use Docker Compose (see `docker-compose.yml`)

## Configuration

Set these environment variables in Docker/Portainer:

### Required:
- `IMMICH_API_KEY`: Your Immich API key (get from Immich UI: User Settings → Account Settings → API Keys)
- `IMMICH_URL`: Immich server URL (e.g., `http://192.168.1.18:2283`)
- `GEEKMAGIC_URL`: GeekMagic device URL (e.g., `http://192.168.1.107`)

### Optional:
- `GEEKMAGIC_MAX_RETRIES`: Maximum connection attempts (default: `10`)
- `GEEKMAGIC_RETRY_DELAY`: Seconds between retries (default: `300` = 5 minutes)
- `TEST_DATE`: Override the date to search for memories (format: `MM-DD` or `YYYY-MM-DD`)
- `TZ`: Timezone for scheduling (e.g., `America/New_York`, `Europe/London`)

## Usage

### Docker Compose:
```bash
docker-compose up
```

### Docker Run:
```bash
docker run --rm \
  -e IMMICH_URL=http://192.168.1.18:2283 \
  -e IMMICH_API_KEY=your-api-key \
  -e GEEKMAGIC_URL=http://192.168.1.107 \
  immich-geekmagic-sync
```

### Standalone Python:
```bash
export IMMICH_API_KEY=your-api-key
export IMMICH_URL=http://192.168.1.18:2283
export GEEKMAGIC_URL=http://192.168.1.107
python immich_to_geekmagic.py
```

### Test with a specific date:
```bash
docker run --rm \
  -e IMMICH_URL=http://192.168.1.18:2283 \
  -e IMMICH_API_KEY=your-api-key \
  -e GEEKMAGIC_URL=http://192.168.1.107 \
  -e TEST_DATE=12-25 \
  immich-geekmagic-sync
```

## How to Get Your Immich API Key

1. Open your Immich web interface
2. Click on your profile picture (top right)
3. Go to "Account Settings"
4. Navigate to "API Keys" tab
5. Click "New API Key"
6. Give it a name (e.g., "GeekMagic Uploader")
7. Copy the generated API key

## Automated Scheduling

The docker-compose.yml includes Ofelia scheduler that runs the sync at **7:50 AM daily**.

To change the schedule, edit the Ofelia label in docker-compose.yml:
```yaml
ofelia.job-exec.sync-memories.schedule: "0 50 7 * * *"  # second minute hour day month weekday
```

Examples:
- `0 0 8 * * *` - Daily at 8:00 AM
- `0 30 9 * * 1-5` - Weekdays at 9:30 AM

After changes, restart: `docker-compose down && docker-compose up -d`

Check scheduler logs: `docker logs ofelia-scheduler`

## Troubleshooting

### "Error: IMMICH_API_KEY is required"
- Make sure the environment variable is set in your Docker container/compose file

### "Error fetching memories"
- Check that your Immich server URL is correct
- Verify your API key is valid
- Ensure the Immich server is accessible from Docker container
- Try using host IP instead of localhost (e.g., `http://192.168.1.18:2283` not `http://localhost:2283`)

### "GeekMagic device unreachable"
- The script will automatically retry with delays (default: 10 attempts × 5 minutes)
- Verify GeekMagic device URL is correct
- Check that the GeekMagic device is powered on and connected to network
- If using Docker, try `network_mode: host` in docker-compose.yml
- Test connectivity: `docker exec immich-geekmagic-sync ping 192.168.1.107`
- Try increasing `GEEKMAGIC_MAX_RETRIES` or `GEEKMAGIC_RETRY_DELAY` environment variables

### Container exits immediately
- Check logs: `docker logs immich-geekmagic-sync`
- Verify all required environment variables are set
- Make sure network connectivity is working

## Notes

- The program creates temporary files during download and resize which are automatically cleaned up
- Images are automatically resized to 240x240 pixels to optimize for the GeekMagic display
- Images are uploaded one at a time to avoid overwhelming the GeekMagic device
- The program searches for photos taken on today's date in previous years (1-10 years ago)

## License

MIT License - see [LICENSE](LICENSE) file for details.
