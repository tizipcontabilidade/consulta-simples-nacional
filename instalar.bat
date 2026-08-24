@echo off
REM Instalacao a partir do codigo-fonte (para quem mantem o sistema).
REM Quem so vai usar deve rodar o instalador em instalador\...-setup.exe

setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado no PATH.
    echo Instale o Python 3.10 ou mais novo: https://www.python.org/downloads/windows/
    exit /b 1
)

echo Criando ambiente virtual em .venv ...
if not exist ".venv" python -m venv .venv
if errorlevel 1 exit /b 1

echo Instalando dependencias ...
call ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
call ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Pronto.
echo   Interface web ....... .venv\Scripts\python.exe app.py
echo   Linha de comando .... .venv\Scripts\python.exe consultar.py --arquivo exemplos\clientes.txt
echo   Gerar instalador .... powershell -ExecutionPolicy Bypass -File construir.ps1
echo.
endlocal
