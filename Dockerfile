FROM python:3.11-slim

# Install system dependencies for moviepy and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    libjpeg-dev \
    zlib1g-dev \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create app directory
WORKDIR /app

# Copy application files
COPY immich_to_geekmagic.py .

# Create log file
RUN touch /var/log/cron.log

# Create cron job to run daily at 1:00 AM (Debian format)
RUN echo "0 1 * * * root cd /app && python immich_to_geekmagic.py >> /var/log/cron.log 2>&1" > /etc/cron.d/immich-sync && \
    chmod 0644 /etc/cron.d/immich-sync && \
    crontab /etc/cron.d/immich-sync

# Create startup script
RUN echo '#!/bin/bash' > /start.sh && \
    echo 'echo "Starting cron daemon..."' >> /start.sh && \
    echo 'cron' >> /start.sh && \
    echo 'echo "Cron daemon started. Running initial sync..."' >> /start.sh && \
    echo 'cd /app && python immich_to_geekmagic.py' >> /start.sh && \
    echo 'echo "Initial sync complete. Tailing logs..."' >> /start.sh && \
    echo 'tail -f /var/log/cron.log' >> /start.sh && \
    chmod +x /start.sh

# Run startup script
CMD ["/start.sh"]
