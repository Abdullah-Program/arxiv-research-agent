@echo off
title ResearchForge AI — Launcher
echo.
echo  ╔══════════════════════════════════════╗
echo  ║      RESEARCHFORGE AI  v2.0          ║
echo  ║      Agentic RAG System              ║
echo  ╚══════════════════════════════════════╝
echo.

:: Terminal 1 — FastAPI Backend (port 8000)
start "ResearchForge :: Backend (port 8000)" cmd /k "cd /d %~dp0src && echo [BACKEND] Starting FastAPI on http://localhost:8000 && python api.py"

:: Wait for backend to init
timeout /t 4 /nobreak > nul

:: Terminal 2 — React Frontend (port 5173)
start "ResearchForge :: Frontend (port 5173)" cmd /k "cd /d %~dp0frontend && echo [FRONTEND] Starting React on http://localhost:5173 && npm run dev"

:: Wait for frontend to compile
timeout /t 5 /nobreak > nul

:: Open browser
start http://localhost:5173

echo.
echo  Both servers are starting...
echo  Backend:   http://localhost:8000/docs
echo  Frontend:  http://localhost:5173
echo.
echo  To stop: Close the two server terminal windows
echo.
pause
