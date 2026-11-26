@echo off
REM Code Meat - inicia o servidor (clique duas vezes neste arquivo)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo  Rode primeiro o instalar_windows.bat
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run.py %*
pause
