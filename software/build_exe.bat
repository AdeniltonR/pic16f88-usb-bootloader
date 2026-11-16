@echo off
REM ========================================================================================================
REM  NOME: Adenilton Ribeiro
REM  DATA: 15/11/2026
REM  PROJETO: build_exe.bat
REM  VERSAO: 1.1.0
REM  DESCRICAO: - feat: Gera o executavel (Windows) do gravador do bootloader UART do PIC16F88
REM             - fix: venv e arquivos temporarios do build ficam no disco local (%LOCALAPPDATA%),
REM                    fora do Google Drive (o Drive corrompe o venv: "No module named pip._vendor.rich")
REM             - docs: Python 3.11+ - PyInstaller - PyQt6 - pyserial
REM  USO: dois cliques neste arquivo, ou no cmd/Git Bash:  ./build_exe.bat
REM  SAIDA: dist\BootloaderPIC16F88.exe (config\ e data\logs\ sao criados ao lado do .exe)
REM ========================================================================================================

setlocal
cd /d "%~dp0"
set APP=BootloaderPIC16F88
set LOCAL=%LOCALAPPDATA%\%APP%
set VENV=%LOCAL%\venv
set WORK=%LOCAL%\build
set PY=%VENV%\Scripts\python.exe

echo.
echo === [1/4] Ambiente virtual em %VENV% ===
if exist "%PY%" (
    "%PY%" -m pip --version >nul 2>&1 || (
        echo venv com problema, recriando...
        rmdir /s /q "%VENV%"
    )
)
if not exist "%PY%" (
    python -m venv "%VENV%" || goto erro
)

echo.
echo === [2/4] Dependencias (PyQt6, pyserial, PyInstaller) ===
"%PY%" -m pip install --upgrade pip >nul
"%PY%" -m pip install -r requirements.txt pyinstaller || goto erro

echo.
echo === [3/4] Limpando build anterior ===
if exist "%WORK%" rmdir /s /q "%WORK%"
if exist "dist\%APP%.exe" del /q "dist\%APP%.exe"

echo.
echo === [4/4] Gerando o executavel ===
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "%APP%" ^
    --paths "%CD%" ^
    --workpath "%WORK%" ^
    --specpath "%WORK%" ^
    --distpath "%CD%\dist" ^
    --hidden-import serial.tools.list_ports ^
    --hidden-import serial.tools.list_ports_windows ^
    "%CD%\main.py" || goto erro

REM copia a configuracao padrao para junto do .exe (se ainda nao existir la)
if not exist "dist\config" mkdir "dist\config"
if not exist "dist\config\settings.json" copy /y "config\settings.json" "dist\config\settings.json" >nul

echo.
echo ============================================================
echo  OK: dist\%APP%.exe
echo ============================================================
explorer dist
goto fim

:erro
echo.
echo ============================================================
echo  ERRO ao gerar o executavel. Veja as mensagens acima.
echo ============================================================
pause
exit /b 1

:fim
endlocal
pause
