FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install uv

# Copy all source files
COPY . .

# Set environment variables (can be overridden at runtime)
ENV OBSIDIAN_VAULT_PATH=/data/obsidian

# Create volume mount points
VOLUME ["/data/obsidian", "/app/repo"]

# Default command
ENTRYPOINT ["python", "claude_code_is_programmable_obsidian.py"]