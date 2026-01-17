# ------------------------------------------------------------
# Base image
# ------------------------------------------------------------
FROM python:3.11-slim-bookworm

# ------------------------------------------------------------
# Environment variables
# ------------------------------------------------------------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production

# ------------------------------------------------------------
# Set working directory
# ------------------------------------------------------------
WORKDIR /app

# ------------------------------------------------------------
# System dependencies
# ------------------------------------------------------------
# Installs wkhtmltopdf and fonts (xfonts) needed for PDF generation
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    curl \
    ca-certificates \
    wkhtmltopdf \
    xfonts-75dpi \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Upgrade pip
# ------------------------------------------------------------
RUN pip install --upgrade pip

# ------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------
# Copy requirements.txt first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. FIX: Install ONLY the new package (This creates a new fast layer)
RUN pip install captcha==0.5.0

# ------------------------------------------------------------
# Create non-root user for security
# ------------------------------------------------------------
RUN useradd -m fastapiuser

# ------------------------------------------------------------
# Copy project files
# ------------------------------------------------------------
# Copy app files after dependencies are installed
COPY . .

# ------------------------------------------------------------
# Fix file ownership
# ------------------------------------------------------------
RUN chown -R fastapiuser:fastapiuser /app

# ------------------------------------------------------------
# Switch to non-root user
# ------------------------------------------------------------
USER fastapiuser

# ------------------------------------------------------------
# Expose port for the app
# ------------------------------------------------------------
EXPOSE 8000

# ------------------------------------------------------------
# Start FastAPI with Gunicorn + UvicornWorker
# ------------------------------------------------------------
# Using --forwarded-allow-ips="*" to fix the proxy error
CMD gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    --workers $(python -c "import os; print(max(1, (os.cpu_count() or 1) * 2 + 1))") \
    --bind 0.0.0.0:8000 \
    --forwarded-allow-ips="*"