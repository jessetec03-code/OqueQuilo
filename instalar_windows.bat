@echo off
REM Code Meat - instalacao no Windows (clique duas vezes neste arquivo)
REM Cria um ambiente Python so do projeto (.venv) e instala tudo. Nao precisa de Git.
cd /d "%~dp0"
echo.
echo  CODE MEAT - instalacao
echo  Pasta: %CD%
echo.
echo %CD% | findstr /i "OneDrive" >nul && (
  echo  ATENCAO: o projeto esta dentro do OneDrive.
  echo  Recomendado: feche esta janela, mova a pasta para C:\code-meat
  echo  e rode este arquivo de novo. O OneDrive tenta sincronizar varios GB.
  echo.
  choice /c SN /m " Continuar mesmo assim"
  if errorlevel 2 exit /b 1
)
where python >nul 2>nul || (
  echo  Python nao encontrado. Instale em https://www.python.org/downloads/
  echo  marcando "Add Python to PATH" e rode este arquivo de novo.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo  [1/4] Criando o ambiente .venv ...
  python -m venv .venv || (echo  Falha ao criar o ambiente. & pause & exit /b 1)
)
echo  [2/4] Atualizando o pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo  [3/4] Instalando o sistema ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo  Falha no requirements.txt & pause & exit /b 1)
echo  [4/4] Instalando o reconhecimento de alimentos (1 a 3 GB, pode demorar) ...
".venv\Scripts\python.exe" -m pip install -r requirements-visao.txt || (
  echo.
  echo  O reconhecimento local nao foi instalado. O sistema funciona em modo manual.
  echo  Veja docs\GUIA_EQUIPE.md, secao 8.
)
echo.
echo  Pronto. Para abrir o sistema, clique duas vezes em iniciar_windows.bat
pause
