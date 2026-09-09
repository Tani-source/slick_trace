# Multi-stage Dockerfile for 100% Free Hosting (Hugging Face Spaces / Render / Koyeb / Railway)
# Exposes port 7860 (Hugging Face Spaces default) or uses $PORT dynamically.

# --- Stage 1: Build Vite React Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python Backend & Unified Production Server ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Install runtime OS dependencies for geospatial & ML packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install lightweight CPU PyTorch (~180MB instead of 3GB CUDA)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install backend Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend

# Copy built frontend assets from Stage 1 into frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set working directory to backend
WORKDIR /app/backend

# Ensure data and cache directories exist and are owned by user 1000
RUN mkdir -p /app/backend/data/uploads /app/backend/data/runs /app/backend/data/cache && \
    useradd -m -u 1000 user && \
    chown -R user:user /app
USER user

# Expose default port
EXPOSE 7860

# Launch Uvicorn on dynamic PORT (7860 for HF Spaces, or $PORT for Render/Koyeb)
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
