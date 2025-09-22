@echo off
echo 🚀 Setting up TripPlanner Multi-Agent System

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Create .env file if it doesn't exist
if not exist "Backend\.env" (
    echo 📝 Creating .env file from example...
    copy "Backend\env.example" "Backend\.env"
    echo.
    echo ⚠️  IMPORTANT: Please edit Backend\.env and add your API keys!
    echo    Required keys:
    echo    - OPENAI_API_KEY ^(get from https://platform.openai.com/api-keys^)
    echo    - TAVILY_API_KEY ^(get from https://tavily.com/^)
    echo.
    echo    Optional keys for enhanced features:
    echo    - GOOGLE_MAPS_API_KEY
    echo    - WEATHER_API_KEY
    echo    - FLIGHT_API_KEY
    echo.
    pause
)

REM Start services
echo 🐳 Starting Docker services...
docker-compose up --build -d

REM Wait for services to be ready
echo ⏳ Waiting for services to be ready...
timeout /t 15 /nobreak >nul

REM Check service health
echo 🔍 Checking service health...

REM Check backend
curl -f http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Backend is healthy
) else (
    echo ❌ Backend is not responding
)

REM Check frontend
curl -f http://localhost/health >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Frontend is healthy
) else (
    echo ❌ Frontend is not responding
)

echo.
echo 🎉 TripPlanner is ready!
echo.
echo 📱 Frontend: http://localhost
echo 🔧 Backend API: http://localhost:8000
echo 📚 API Docs: http://localhost:8000/docs
echo 🗄️  MongoDB: localhost:27017
echo.
echo 📋 Useful commands:
echo   View logs: docker-compose logs -f
echo   Stop services: docker-compose down
echo   Restart: docker-compose restart
echo.
pause







