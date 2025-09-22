#!/bin/bash

echo "🚀 Starting TripPlanner Development Environment"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f Backend/.env ]; then
    echo "📝 Creating .env file from example..."
    cp Backend/env.example Backend/.env
    echo ""
    echo "⚠️  IMPORTANT: Please edit Backend/.env and add your API keys!"
    echo "   Required keys:"
    echo "   - OPENAI_API_KEY (get from https://platform.openai.com/api-keys)"
    echo "   - TAVILY_API_KEY (get from https://tavily.com/)"
    echo ""
    echo "   Optional keys for enhanced features:"
    echo "   - GOOGLE_MAPS_API_KEY"
    echo "   - WEATHER_API_KEY"
    echo "   - FLIGHT_API_KEY"
    echo ""
    read -p "Press Enter to continue after adding your API keys..."
fi

# Start services
echo "🐳 Starting Docker services..."
docker-compose up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check backend
if curl -f http://localhost:8000/health > /dev/null 2>&1 || powershell -Command "try { Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" 2>/dev/null; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend is not responding"
fi

# Check frontend
if curl -f http://localhost > /dev/null 2>&1 || powershell -Command "try { Invoke-WebRequest -Uri http://localhost -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" 2>/dev/null; then
    echo "✅ Frontend is healthy"
else
    echo "❌ Frontend is not responding"
fi

# Get MongoDB URI from .env file
MONGO_URI=$(grep "MONGO_URI=" .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [ -z "$MONGO_URI" ]; then
    MONGO_URI="localhost:27017"
fi

echo ""
echo "🎉 TripPlanner is ready!"
echo ""
echo "📱 Frontend: http://localhost"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "🗄️  MongoDB: $MONGO_URI"
echo ""
echo "📋 Useful commands:"
echo "  View logs: docker-compose logs -f"
echo "  Stop services: docker-compose down"
echo "  Restart: docker-compose restart"
echo ""
