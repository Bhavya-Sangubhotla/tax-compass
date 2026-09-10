# --- Stage 1: Build React frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/react-tax-assistant
COPY react-tax-assistant/package*.json ./
RUN npm ci
COPY react-tax-assistant/ ./
RUN npm run build

# --- Stage 2: Serve Python Backend and Static Assets ---
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python code
COPY *.py ./

# Copy React built files from Stage 1 into the location FastAPI expects
COPY --from=frontend-builder /app/react-tax-assistant/dist ./react-tax-assistant/dist

# Expose port (Cloud Run sets PORT environment variable, defaults to 8080)
EXPOSE 8080

# Start FastAPI application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]