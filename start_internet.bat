@echo off
cd /d "%~dp0"

echo ==========================================
echo SELEZNEV Local Share - Internet Tunnel
echo ==========================================
echo.
echo Step 1: Starting local server...
echo.

start "SELEZNEV Local Share" cmd /k "cd /d %~dp0 && python -m pip install -r requirements.txt && python app.py"

echo Waiting 5 seconds...
timeout /t 5 >nul

echo.
echo Step 2: Checking cloudflared...
where cloudflared >nul 2>nul

if %errorlevel% neq 0 (
    if exist "%~dp0cloudflared.exe" (
        echo Using local cloudflared.exe...
        "%~dp0cloudflared.exe" tunnel --url http://localhost:8000
        pause
        exit /b
    )

    echo.
    echo cloudflared not found.
    echo Trying to install via winget...
    winget install --id Cloudflare.cloudflared -e
)

echo.
echo Step 3: Starting public HTTPS tunnel...
echo.
echo IMPORTANT:
echo Copy the https://xxxxx.trycloudflare.com link from the window below.
echo This link is your temporary internet address.
echo.
echo Login page is protected by your app login/password.
echo.
cloudflared tunnel --url http://localhost:8000

pause