@echo off
setlocal EnableExtensions
cls
color 0B
set "ROOT=%~dp0"
echo ====================================================
echo     BIM SCHEDULE - Gerar aplicativo desktop (.exe)
echo ====================================================
echo.
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo [ERRO] Ambiente Python nao encontrado. Execute install.bat primeiro.
  goto :fail
)

echo [1/4] Build do frontend...
cd /d "%ROOT%frontend"
call npm run build
if errorlevel 1 goto :fail

echo [2/4] Empacotando o servico local (PyInstaller)...
"%ROOT%.venv\Scripts\python.exe" -m pip install --quiet pyinstaller
if errorlevel 1 goto :fail
cd /d "%ROOT%desktop\service"
"%ROOT%.venv\Scripts\python.exe" -m PyInstaller --noconfirm --log-level WARN bim-schedule-service.spec
if errorlevel 1 goto :fail

echo [3/4] Instalando dependencias do Electron...
cd /d "%ROOT%desktop"
call npm install
if errorlevel 1 goto :fail
if not exist "%ROOT%desktop\node_modules\electron\dist\electron.exe" (
  call npm install-scripts approve electron
  call npm rebuild electron
)

echo [4/4] Gerando o aplicativo...
call npx electron-builder --win dir
if errorlevel 1 goto :fail

echo.
echo Criando atalho na Area de Trabalho...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\BIM SCHEDULE.lnk'); $s.TargetPath='%ROOT%desktop\dist\win-unpacked\BIM SCHEDULE.exe'; $s.WorkingDirectory='%ROOT%desktop\dist\win-unpacked'; $s.IconLocation='%ROOT%desktop\dist\win-unpacked\BIM SCHEDULE.exe,0'; $s.Save()"

echo.
echo ====================================================
echo Pronto: desktop\dist\win-unpacked\BIM SCHEDULE.exe
echo Atalho "BIM SCHEDULE" criado na Area de Trabalho.
echo ====================================================
pause
exit /b 0

:fail
echo.
echo [ERRO] A geracao do aplicativo falhou. Leia a mensagem acima.
pause
exit /b 1
