FROM python:3.10-slim

# Install system dependencies & FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-liberation \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source directories
COPY . .

# Expose web application port (7860 is default for Hugging Face Spaces)
EXPOSE 7860

ENV PORT=7860
ENV PYTHONUNBUFFERED=1

# Start the Autonomous Director web studio
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
