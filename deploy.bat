@echo off
REM Quick deployment script for Firebase Hosting (Windows)

echo.
echo 🔥 MTG Archive Firebase Deployment
echo ===================================
echo.

REM Check if Firebase CLI is installed
where firebase >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Firebase CLI not found. Installing...
    call npm install -g firebase-tools
)

echo 📦 Checking Firebase setup...
call firebase --version

echo.
echo Select deployment mode:
echo 1) Deploy to Firebase (production)
echo 2) Test locally with emulator
echo 3) Just show current project
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" (
    echo 🚀 Deploying to Firebase Hosting...
    call firebase deploy --only hosting
    echo.
    echo ✅ Deployment complete!
    echo Visit: https://mtg-archive-357ca.web.app
) else if "%choice%"=="2" (
    echo 🧪 Starting Firebase emulator...
    call firebase emulators:start
) else if "%choice%"=="3" (
    echo 📋 Current Firebase project:
    call firebase projects:list
) else (
    echo Invalid choice
)

pause
