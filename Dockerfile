FROM python:3.11-slim

# Install system dependencies for moviepy and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    libjpeg-dev \
    zlib1g-dev \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create app directory
WORKDIR /app

# Copy application files
COPY immich_to_geekmagic.py .

# Run initial sync on startup; Ofelia (docker-compose) handles recurring scheduling
CMD ["python3", "/app/immich_to_geekmagic.py"]
