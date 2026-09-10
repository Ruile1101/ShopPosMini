@echo off
setlocal
cd /d "%~dp0"

if "%DATABASE_URL%"=="" (
    echo DATABASE_URL is not set.
    echo Example:
    echo   set DATABASE_URL=postgresql+psycopg2://shoppos:CHANGE_ME@192.168.1.50:5432/shoppos
    echo   start_server.bat
    exit /b 1
)

for /f "usebackq tokens=2 delims={}" %%i in (`python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()"`) do set SERVER_IP=%%i

if "%SERVER_IP%"=="" set SERVER_IP=127.0.0.1

if "%FLASK_RUN_HOST%"=="" set FLASK_RUN_HOST=0.0.0.0
if "%FLASK_RUN_PORT%"=="" set FLASK_RUN_PORT=5000

echo.
echo ShopPOS PostgreSQL server launcher
echo DATABASE_URL is configured.
echo Server LAN URL: http://%SERVER_IP%:%FLASK_RUN_PORT%/
echo Client laptops should open: http://%SERVER_IP%:%FLASK_RUN_PORT%/
echo.

python start.py
