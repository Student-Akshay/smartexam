FROM python:3.11-slim

# Install system libraries required by MediaPipe and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgles2 \
    libegl1 \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

ENV PORT=10000
EXPOSE 10000

# Start server using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "run:app"]
