#!/bin/bash

# Production script to run the app with Docker (simulating EB environment)
echo "🚀 Starting TripPlanner Production Environment with Docker"

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

# Set production environment
export ENVIRONMENT=production
export DEBUG=false

# Start with production settings
echo "🐳 Starting production Docker services..."
docker-compose -f docker-compose.prod.yml up --build

echo "✅ Production environment started!"
echo "📱 Frontend: http://localhost"
echo "🔧 Backend API: http://localhost:8000"


