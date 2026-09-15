@echo off
setlocal
set "ROOT=%~dp0"

echo [run-dev] Levantando backend (http://localhost:8000) y frontend (http://localhost:5173) ...
start "Avaluos - Backend" cmd /k call "%ROOT%backend\dev.bat"
start "Avaluos - Frontend" cmd /k call "%ROOT%frontend\dev.bat"
echo [run-dev] Listo. Se abrieron dos ventanas. Cierralas o Ctrl+C ahi para detener cada servidor.
