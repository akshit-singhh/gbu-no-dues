# Use a slim Python image
FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies including CA certificates
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

# Copy the entire project
COPY . .

# Expose the port Leapcell will use
EXPOSE 8000

# Start FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
