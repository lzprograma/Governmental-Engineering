@echo off
setlocal
cd /d "%~dp0"
set PYTHON=python
if exist ".venv\Scripts\python.exe" set PYTHON=.venv\Scripts\python.exe
%PYTHON% -c "import fastapi, uvicorn, cryptography, httpx" >nul 2>&1
if errorlevel 1 (
  echo Instalando dependencias do painel Lunz...
  %PYTHON% -m pip install -e ".[server]"
  if errorlevel 1 (
    echo Falha ao instalar. Verifique Python, pip e conexao.
    pause
    exit /b 1
  )
)
%PYTHON% main.py On server
if errorlevel 1 pause
endlocal
