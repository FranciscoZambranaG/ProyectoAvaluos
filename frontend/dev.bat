@echo off
cd /d "%~dp0"
if not exist "node_modules" (
    echo [frontend] No se encontro node_modules. Instala dependencias primero:
    echo   npm install
    pause
    exit /b 1
)
npm run dev
