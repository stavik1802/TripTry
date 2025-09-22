#!/bin/bash

echo "🚀 Starting TripPlanner Production Environment"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f Backend/.env ]; then
    echo "📝 Creating .env file from example..."
    cp Backend/env.example Backend/.env
    echo "⚠️  Please edit Backend/.env and add your API keys"
fi

# Build and start services in production mode
echo "🐳 Building and starting production services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 15

# Check service health
echo "🔍 Checking service health..."

# Check backend
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend is not responding"
fi

# Check frontend
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ Frontend is healthy"
else
    echo "❌ Frontend is not responding"
fi

echo ""
echo "🎉 TripPlanner Production is ready!"
echo ""
echo "📱 Frontend: http://localhost"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "🗄️  MongoDB: localhost:27017"
echo ""
echo "📋 Production commands:"
echo "  View logs: docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
echo "  Stop services: docker-compose -f docker-compose.yml -f docker-compose.prod.yml down"
echo "  Update: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d"
echo ""



