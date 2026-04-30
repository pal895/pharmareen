@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo PharMareen is starting...
echo ================================================
echo.
echo Local app: http://localhost:8000
echo Health check: http://localhost:8000/health
echo Status page: http://localhost:8000/status
echo WhatsApp webhook: needs public HTTPS production URL
echo.

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found.
        echo Run setup.bat first, or install Python.
        echo.
        echo Press any key to close.
        pause >nul
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" app\main.py
set "RESULT=%ERRORLEVEL%"

echo.
if not "%RESULT%"=="0" (
    echo PharMareen startup failed.
    echo Please read the error above.
) else (
    echo PharMareen stopped.
)
echo.
echo Press any key to close.
pause >nul
exit /b %RESULT%
