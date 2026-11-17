@echo off
setlocal EnableExtensions
cls
color 0A
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo [ERRO] Ambiente Python nao encontrado. Execute install.bat primeiro.
  pause
  exit /b 1
)
if not exist "%ROOT%frontend\node_modules" (
  echo [ERRO] Dependencias do frontend nao encontradas. Execute install.bat primeiro.
  pause
  exit /b 1
)

echo ====================================================
echo       BIM SCHEDULE - Inicializador
echo ====================================================
echo.
start "BIM SCHEDULE - Backend" cmd /k "cd /d ""%ROOT%backend"" && set ""PYTHONPATH=%ROOT%backend"" && ""%ROOT%.venv\Scripts\python.exe"" -m app --port 8000"
start "BIM SCHEDULE - Frontend" cmd /k "cd /d ""%ROOT%frontend"" && npm run dev -- --host 127.0.0.1"
echo Backend: http://127.0.0.1:8000
echo Swagger: http://127.0.0.1:8000/docs
echo Frontend: http://127.0.0.1:3000
echo Dados: %%LOCALAPPDATA%%\BIM-SCHEDULE
echo.
echo Os dois terminais serao abertos separadamente. Feche-os para encerrar os servicos.
pause
