@echo off
cd /d "%~dp0"
echo Starting SELEZNEV Local Share 2.0...
python -m pip install -r requirements.txt
echo.
echo Login: admin
echo Password: 1234
echo.
echo Open http://127.0.0.1:8000
python app.py
pause
