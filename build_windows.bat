@echo off
title Constructor de Produccion Windows - SURA Citas Bot
cd /d "%~dp0"
echo ==============================================================================
echo   SURA CITAS BOT - COMPILADOR Y GENERADOR DE INSTALADOR PARA WINDOWS
echo   ENGINEERED BY: SHION
echo ==============================================================================
echo.

REM 1. Verificar Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta en el PATH del sistema.
    pause
    exit /b 1
)

REM 2. Instalar dependencias si faltan
echo [1/3] Verificando dependencias...
pip install -r requirements.txt
python -m playwright install chromium

REM 3. Compilar ejecutable con PyInstaller
echo.
echo [2/3] Compilando ejecutable nativo protegido SuraCitas.exe...
python -m PyInstaller packaging\windows\SuraCitas_win.spec --clean -y

if not exist "dist\SuraCitas.exe" (
    echo [ERROR] No se pudo generar dist\SuraCitas.exe
    pause
    exit /b 1
)

REM 4. Detectar compilador Inno Setup (ISCC.exe)
echo.
echo [3/3] Generando instalador de 1-Clic con Inno Setup...
set "ISCC_PATH="
if exist "C:\Users\gamer\AppData\Local\Programs\InnoSetup\ISCC.exe" (
    set "ISCC_PATH=C:\Users\gamer\AppData\Local\Programs\InnoSetup\ISCC.exe"
) else if exist "%LOCALAPPDATA%\Programs\InnoSetup\ISCC.exe" (
    set "ISCC_PATH=%LOCALAPPDATA%\Programs\InnoSetup\ISCC.exe"
) else if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
    where ISCC.exe >nul 2>nul
    if %errorlevel% equ 0 (
        set "ISCC_PATH=ISCC.exe"
    )
)

if "%ISCC_PATH%"=="" (
    echo [ADVERTENCIA] Inno Setup (ISCC.exe) no fue encontrado en las rutas estandar.
    echo El ejecutable independiente dist\SuraCitas.exe fue generado exitosamente.
    echo Para compilar el instalador, instala Inno Setup 6 y ejecuta: ISCC packaging\windows\installer_setup.iss
    pause
    exit /b 0
)

"%ISCC_PATH%" "packaging\windows\installer_setup.iss"

if not exist "dist\Instalador_SuraCitas_Setup.exe" (
    echo [ERROR] No se pudo compilar el instalador.
    pause
    exit /b 1
)

echo.
echo ==============================================================================
echo   ✔ PROCESO DE COMPILACION WINDOWS FINALIZADO CON EXITO
echo ==============================================================================
echo   1. Ejecutable Independiente: dist\SuraCitas.exe
echo   2. Instalador de 1-Clic:     dist\Instalador_SuraCitas_Setup.exe
echo ==============================================================================
pause
