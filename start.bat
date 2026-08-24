@echo off
echo 🎬 Starting Viral DNA Extractor...
echo.

REM Check if backend dependencies are installed
if not exist "backend\venv" (
    echo 📦 Setting up Python virtual environment...
    cd backend
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
    cd ..
)

REM Check if frontend dependencies are installed
if not exist "frontend\node_modules" (
    echo 📦 Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo.
echo ✅ Setup complete!
echo.
echo Starting servers...
echo.
echo 🐍 Backend will run on http://localhost:5002
echo ⚛️  Frontend will run on http://localhost:3100
echo.
echo Press Ctrl+C to stop both servers
echo.

REM Start backend
start "Backend Server" cmd /k "cd backend && venv\Scripts\activate && python main.py"

REM Wait a bit for backend to start
timeout /t 3 /nobreak > nul

REM Start frontend
start "Frontend Server" cmd /k "cd frontend && npm run dev"

echo.
echo Both servers are starting in separate windows...
echo.
pause
