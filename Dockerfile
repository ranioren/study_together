FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Reflex (e.g., unzip, curl)
RUN apt-get update && apt-get install -y \
    unzip \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose ports for Reflex (Frontend: 3000, Backend: 8000)
EXPOSE 3000 8000

CMD ["python", "main.py"]
