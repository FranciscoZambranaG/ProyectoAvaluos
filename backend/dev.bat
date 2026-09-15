@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [backend] No se encontro .venv. Crea el entorno primero:
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
