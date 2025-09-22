#!/bin/bash

# Development script to run the app with Docker (local development)
echo "🐳 Starting TripPlanner Development Environment with Docker"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build frontend first
echo "🔨 Building frontend..."
cd trip_ui
npm ci
npm run build
cd ..

# Start services with Docker Compose
echo "🚀 Starting Docker services..."
docker-compose up --build

echo "✅ Development environment started!"
echo "📱 Frontend: http://localhost"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"


