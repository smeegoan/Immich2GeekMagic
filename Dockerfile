FROM python:3.11-alpine

# Install dependencies
RUN apk add --no-cache \
    jpeg-dev \
    zlib-dev \
    libjpeg \
    dcron \
    && pip install --no-cache-dir \
    requests \
    Pillow \
    python-dotenv

# Create app directory
WORKDIR /app

# Copy application files
COPY immich_to_geekmagic.py .
COPY .env .

# Create cron job to run daily at 8:00 AM
RUN echo "0 8 * * * cd /app && python immich_to_geekmagic.py >> /var/log/cron.log 2>&1" > /etc/crontabs/root

# Create log file
RUN touch /var/log/cron.log

# Create startup script
RUN echo '#!/bin/sh' > /start.sh && \
    echo 'echo "Starting cron daemon..."' >> /start.sh && \
    echo 'crond' >> /start.sh && \
    echo 'echo "Cron daemon started. Running initial sync..."' >> /start.sh && \
    echo 'cd /app && python immich_to_geekmagic.py' >> /start.sh && \
    echo 'echo "Initial sync complete. Tailing logs..."' >> /start.sh && \
    echo 'tail -f /var/log/cron.log' >> /start.sh && \
    chmod +x /start.sh

# Run startup script
CMD ["/start.sh"]
