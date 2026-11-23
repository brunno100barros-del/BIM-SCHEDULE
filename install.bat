@echo off
setlocal EnableExtensions
cls
color 0B
set "ROOT=%~dp0"
echo ====================================================
echo       BIM SCHEDULE - Instalacao do ambiente
echo ====================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado no PATH. Instale Python 3.11 ou 3.12.
  pause
  exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Node.js nao encontrado no PATH. Instale uma versao LTS.
  pause
  exit /b 1
)

python -c "import sys; print('Python', sys.version.split()[0])"
call node --version
call npm --version

echo.
echo [1/5] Criando ambiente virtual Python...
if not exist "%ROOT%.venv\Scripts\python.exe" (
  python -m venv "%ROOT%.venv"
  if errorlevel 1 goto :fail
)

echo [2/5] Instalando dependencias do backend...
"%ROOT%.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%backend\requirements.txt"
if errorlevel 1 goto :fail

echo [3/5] Preparando a pasta de dados e o banco...
echo       Dados em %%LOCALAPPDATA%%\BIM-SCHEDULE. Dados de versoes anteriores (backend\bim_schedule.db
echo       e backend\uploads) sao COPIADOS e validados; os originais nao sao alterados.
cd /d "%ROOT%backend"
set "PYTHONPATH=%ROOT%backend"
"%ROOT%.venv\Scripts\python.exe" -m app prepare
if errorlevel 1 goto :fail

echo [4/5] Instalando dependencias do frontend...
cd /d "%ROOT%frontend"
call npm install
if errorlevel 1 goto :fail

echo [5/5] Validando build do frontend...
call npm run build
if errorlevel 1 goto :fail

echo.
echo ====================================================
echo Instalacao concluida. Execute start.bat para abrir.
echo ====================================================
pause
exit /b 0

:fail
echo.
echo [ERRO] A instalacao ou validacao falhou. Leia a mensagem acima.
pause
exit /b 1
