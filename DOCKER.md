# Immich to GeekMagic Memory Sync - Docker

Automated daily sync of Immich memories to GeekMagic display.

## Quick Start with Portainer

### Option 1: Using Portainer Stacks

1. In Portainer, go to **Stacks** → **Add stack**
2. Name it: `immich-geekmagic-sync`
3. Copy the contents of `docker-compose.yml` into the web editor
4. Under **Environment variables**, add:
   ```
   IMMICH_URL=http://192.168.1.18:2283
   IMMICH_API_KEY=your-api-key-here
   GEEKMAGIC_URL=http://192.168.1.107/
   TZ=Europe/Lisbon
   ```
5. Click **Deploy the stack**

### Option 2: Using Docker CLI

```bash
# Build the image
docker build -t immich-geekmagic-sync .

# Run the container
docker run -d \
  --name immich-geekmagic-sync \
  --restart unless-stopped \
  -e TZ=Europe/Lisbon \
  -v $(pwd)/.env:/app/.env:ro \
  immich-geekmagic-sync
```

### Option 3: Using Docker Compose

```bash
docker-compose up -d
```

## Configuration

Edit the `.env` file with your settings:

```env
IMMICH_URL=http://192.168.1.18:2283
IMMICH_API_KEY=your-api-key-here
GEEKMAGIC_URL=http://192.168.1.107/
```

## Schedule

By default, the sync runs:
- **Daily at 8:00 AM** (server time)
- **Once immediately** when the container starts

### Changing the Schedule

Edit the cron schedule in `Dockerfile`:

```dockerfile
# Current: Daily at 8:00 AM
RUN echo "0 8 * * * cd /app && python immich_to_geekmagic.py >> /var/log/cron.log 2>&1" > /etc/crontabs/root

# Examples:
# Every 6 hours: "0 */6 * * *"
# Twice daily (8 AM and 8 PM): "0 8,20 * * *"
# Every day at noon: "0 12 * * *"
```

## Monitoring

### View logs in Portainer:
1. Go to **Containers**
2. Click on `immich-geekmagic-sync`
3. Click **Logs**

### View logs via Docker CLI:
```bash
# Container logs
docker logs -f immich-geekmagic-sync

# Cron logs
docker exec immich-geekmagic-sync tail -f /var/log/cron.log
```

## Manual Trigger

Run a sync manually without waiting for the scheduled time:

```bash
docker exec immich-geekmagic-sync python /app/immich_to_geekmagic.py
```

## Timezone Configuration

Set the `TZ` environment variable to your timezone:

**Common timezones:**
- `Europe/Lisbon` (WET/WEST) - Portugal
- `America/New_York` (EST/EDT)
- `America/Chicago` (CST/CDT)
- `America/Los_Angeles` (PST/PDT)
- `Europe/London` (GMT/BST)
- `Asia/Tokyo` (JST)

In Portainer:
1. Edit the stack
2. Add environment variable: `TZ=Your/Timezone`
3. Update the stack

## Troubleshooting

### Container won't start
- Check logs: `docker logs immich-geekmagic-sync`
- Verify `.env` file exists and has correct values
- Ensure Immich and GeekMagic are accessible from the container

### Sync not running
- Check cron logs: `docker exec immich-geekmagic-sync cat /var/log/cron.log`
- Verify timezone is correct
- Manually trigger to test: `docker exec immich-geekmagic-sync python /app/immich_to_geekmagic.py`

### Network issues
- Ensure the container can reach both Immich and GeekMagic
- Try using IP addresses instead of hostnames in `.env`
- Check if you need to use `host` network mode

## Image Size

The Docker image is minimal (~150MB) and uses:
- Alpine Linux (lightweight base)
- Python 3.11
- Only essential dependencies

## Updates

To update the container after code changes:

```bash
# Rebuild
docker-compose build --no-cache

# Restart
docker-compose up -d
```

Or in Portainer:
1. Edit the stack
2. Click **Update the stack**
3. Enable **Re-pull image and redeploy**
