# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Build creates /app/dist
RUN npm run build

# Stage 2: Setup Backend info
FROM python:3.9-slim
WORKDIR /app/backend

# Install system dependencies (for OpenCV/GLib if needed)
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY backend/ .

# Copy Frontend Build from Stage 1 -> ../dist (relative to /app/backend is /app/dist)
COPY --from=frontend-builder /app/dist ../dist

# Environment variables
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose port
EXPOSE 8000

# Run the single-process server
CMD ["python", "server.py"]
