@echo off
setlocal
title PharMareen Local WhatsApp Bridge
cd /d "%~dp0"

echo PharMareen Local WhatsApp Bridge
echo.
echo This runs WhatsApp Web/Baileys on this Windows laptop.
echo The FastAPI backend stays on Replit.
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found.
  echo Install Node.js 20 LTS from:
  echo https://nodejs.org/en/download
  echo Then open a NEW Command Prompt and run this file again.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js 20 LTS from:
  echo https://nodejs.org/en/download
  pause
  exit /b 1
)

echo Node:
node -v
echo npm:
npm -v
echo.

if "%PHARMAREEN_BACKEND_URL%"=="" (
  echo PHARMAREEN_BACKEND_URL is missing.
  echo Example:
  echo set PHARMAREEN_BACKEND_URL=https://pharmareen-1--pal895.replit.app
  pause
  exit /b 1
)

if "%ALLOWED_WHATSAPP_NUMBERS%"=="" (
  echo ALLOWED_WHATSAPP_NUMBERS is missing.
  echo For safety, the bridge will not start without an allowlist.
  echo Example:
  echo set ALLOWED_WHATSAPP_NUMBERS=254757637709
  pause
  exit /b 1
)

if "%BAILEYS_SESSION_PATH%"=="" set BAILEYS_SESSION_PATH=.\.baileys_auth
if "%BAILEYS_LOG_LEVEL%"=="" set BAILEYS_LOG_LEVEL=info
if "%AUTO_RESET_BAILEYS_ON_LOGOUT%"=="" set AUTO_RESET_BAILEYS_ON_LOGOUT=true

echo Backend:
echo %PHARMAREEN_BACKEND_URL%
echo Allowlist configured.
echo Session path:
echo %BAILEYS_SESSION_PATH%
echo GROUP REPLIES: DISABLED
echo UNKNOWN NUMBER REPLIES: DISABLED
echo.

if /I "%RESET_BAILEYS_SESSION%"=="true" (
  echo RESET_BAILEYS_SESSION=true, clearing %BAILEYS_SESSION_PATH%
  rmdir /s /q "%BAILEYS_SESSION_PATH%" 2>nul
)

if exist package-lock.json (
  findstr /C:"7.0.0-rc.10" package-lock.json >nul 2>nul
  if not errorlevel 1 (
    echo Old invalid Baileys lockfile found. Reinstalling cleanly.
    rmdir /s /q node_modules 2>nul
    del /q package-lock.json 2>nul
  )
)

if not exist node_modules\@whiskeysockets\baileys (
  echo Installing WhatsApp bridge packages...
  npm install
  if errorlevel 1 (
    echo npm install failed. Check your internet connection and Node.js installation.
    pause
    exit /b 1
  )
)

echo Baileys package version:
node -e "console.log(require('@whiskeysockets/baileys/package.json').version)"
echo.
echo QR will appear below if WhatsApp login is needed.
echo Open WhatsApp on your phone: Settings or Menu > Linked devices > Link a device.
echo.

node baileys-bridge.js

echo.
echo Bridge stopped.
pause
