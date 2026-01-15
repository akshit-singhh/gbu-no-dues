# Use a slim Python image
FROM python:3.11-slim-bookworm

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV ENV=production

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    curl \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m fastapiuser

# Copy project files
COPY . .

# Fix ownership (IMPORTANT)
RUN chown -R fastapiuser:fastapiuser /app

# Switch to non-root user
USER fastapiuser

# Expose port
EXPOSE 8000

# Start FastAPI using Gunicorn (PRODUCTION)
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--proxy-headers"]
