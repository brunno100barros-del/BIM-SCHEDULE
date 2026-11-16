@echo off
CLS
COLOR 0B
echo ====================================================
echo    BIM SCHEDULE — Instalador de Dependencias (Fase 2)
echo ====================================================
echo.

echo [1/4] Verificando ambiente Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no PATH. Instale o Python 3.10+ antes de continuar.
    pause
    exit /b 1
)

echo [2/4] Instalando dependencias do Backend (FastAPI + IfcOpenShell)...
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias do backend.
    pause
    exit /b 1
)
cd ..

echo [3/4] Verificando ambiente Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Node.js nao foi encontrado no PATH. Instale o Node.js 18+ antes de continuar.
    pause
    exit /b 1
)

echo [4/4] Instalando dependencias do Frontend (React + Three.js + Web-IFC)...
cd frontend
call npm install --legacy-peer-deps
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias do frontend.
    pause
    exit /b 1
)
cd ..

echo.
echo ====================================================
echo    INSTALACAO CONCLUIDA COM SUCESSO!
echo ====================================================
echo Execute o arquivo start.bat para iniciar a aplicacao.
pause
