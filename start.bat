@echo off
CLS
COLOR 0A
echo ====================================================
echo    BIM SCHEDULE — Inicializador do Sistema (Fase 2)
echo ====================================================
echo.

echo [1/2] Iniciando Servidor Backend (FastAPI na porta 8000)...
start "BIM SCHEDULE - Backend" cmd /k "cd backend && python -m uvicorn app.main:app --reload --port 8000"

echo [2/2] Iniciando Servidor Frontend (Vite na porta 3000)...
start "BIM SCHEDULE - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ====================================================
echo    SISTEMA INICIALIZADO COM SUCESSO!
echo ====================================================
echo - Backend API: http://localhost:8000
echo - Documentacao API (Swagger): http://localhost:8000/docs
echo - Frontend WEB: http://localhost:3000
echo.
echo Pressione qualquer tecla para fechar esta janela de controle...
pause >nul
