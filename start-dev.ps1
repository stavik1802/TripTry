# PowerShell version of start-dev.sh for Windows

Write-Host "🚀 Starting TripPlanner Development Environment" -ForegroundColor Green

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "❌ Docker is not running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Create .env file if it doesn't exist
if (-not (Test-Path "Backend\.env")) {
    Write-Host "📝 Creating .env file from example..." -ForegroundColor Yellow
    Copy-Item "Backend\env.example" "Backend\.env"
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Please edit Backend\.env and add your API keys!" -ForegroundColor Yellow
    Write-Host "   Required keys:"
    Write-Host "   - OPENAI_API_KEY (get from https://platform.openai.com/api-keys)"
    Write-Host "   - TAVILY_API_KEY (get from https://tavily.com/)"
    Write-Host ""
    Write-Host "   Optional keys for enhanced features:"
    Write-Host "   - GOOGLE_MAPS_API_KEY"
    Write-Host "   - WEATHER_API_KEY"
    Write-Host "   - FLIGHT_API_KEY"
    Write-Host ""
    Read-Host "Press Enter to continue after adding your API keys"
}

# Start services
Write-Host "🐳 Starting Docker services..." -ForegroundColor Blue
docker-compose up --build -d

# Wait for services to be ready
Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service health
Write-Host "🔍 Checking service health..." -ForegroundColor Blue

# Check backend
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Backend is healthy" -ForegroundColor Green
    } else {
        Write-Host "❌ Backend is not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Backend is not responding" -ForegroundColor Red
}

# Check frontend
try {
    $response = Invoke-WebRequest -Uri "http://localhost" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Frontend is healthy" -ForegroundColor Green
    } else {
        Write-Host "❌ Frontend is not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Frontend is not responding" -ForegroundColor Red
}

# Get MongoDB URI from .env file
$envContent = Get-Content ".env" -ErrorAction SilentlyContinue
$mongoUri = "localhost:27017"
if ($envContent) {
    $mongoLine = $envContent | Where-Object { $_ -match "^MONGO_URI=" }
    if ($mongoLine) {
        $mongoUri = $mongoLine -replace "^MONGO_URI=", ""
        $mongoUri = $mongoUri -replace '"', ""
        $mongoUri = $mongoUri -replace "'", ""
    }
}

Write-Host ""
Write-Host "🎉 TripPlanner is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "📱 Frontend: http://localhost" -ForegroundColor Cyan
Write-Host "🔧 Backend API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🗄️  MongoDB: $mongoUri" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Useful commands:" -ForegroundColor Yellow
Write-Host "  View logs: docker-compose logs -f"
Write-Host "  Stop services: docker-compose down"
Write-Host "  Restart: docker-compose restart"
Write-Host ""


