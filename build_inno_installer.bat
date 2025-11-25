@echo off
REM Build script for MTG Archive Inno Setup installer
REM Requires Inno Setup to be installed: https://jrsoftware.org/isdl.php

echo ================================
echo MTG Archive Installer Builder
echo ================================
echo.

REM Check if Inno Setup is installed
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
    echo ERROR: Inno Setup not found!
    echo.
    echo Please install Inno Setup 6 from:
    echo https://jrsoftware.org/isdl.php
    echo.
    echo Default installation path: C:\Program Files (x86)\Inno Setup 6\
    echo.
    pause
    exit /b 1
)

echo Found Inno Setup at: %ISCC_PATH%
echo.

REM Check if .iss file exists
if not exist "MTG_Archive_Setup.iss" (
    echo ERROR: MTG_Archive_Setup.iss not found!
    echo Please run this script from the project root directory.
    echo.
    pause
    exit /b 1
)

echo Building installer...
echo.

REM Compile the installer
"%ISCC_PATH%" "MTG_Archive_Setup.iss"

if errorlevel 1 (
    echo.
    echo ================================
    echo ERROR: Build failed!
    echo ================================
    echo.
    pause
    exit /b 1
)

echo.
echo ================================
echo Build completed successfully!
echo ================================
echo.
echo Installer created at: dist\MTG_Archive_Setup.exe
echo.
echo You can now distribute this installer to users.
echo.
pause
