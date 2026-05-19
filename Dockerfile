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

# Pull in environment variables set in DigitalOcean for the build phase
ARG API_URL
ARG APP_URL
ENV API_URL=$API_URL
ENV APP_URL=$APP_URL

# Pre-build the Reflex frontend so the server starts instantly and passes DO health checks
RUN cd web && reflex export --frontend-only --no-zip

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose ports for Reflex (Frontend: 3000, Backend: 8000)
EXPOSE 3000 8000

CMD ["python", "main.py"]
