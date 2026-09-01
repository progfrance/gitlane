@echo off
REM GitLane — installation offline (Windows / conda + pip)
REM Usage: install_offline.bat [conda_env_name]
setlocal

set ENV_NAME=%~1
if "%ENV_NAME%"=="" set ENV_NAME=gitlane
set BACKEND_DIR=%~dp0backend

echo == GitLane offline install ==
echo Env: %ENV_NAME%
echo.

where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo conda not found - creating a plain venv instead.
    cd /d "%BACKEND_DIR%"
    if not exist .venv python -m venv .venv
    call .venv\Scripts\activate.bat
    if exist "%BACKEND_DIR%\wheels" (
        pip install --no-index --find-links="%BACKEND_DIR%\wheels" -r requirements.txt
    ) else (
        pip install -r requirements.txt
    )
    echo.
    echo Lancement : "%BACKEND_DIR%\.venv\Scripts\python" -m uvicorn app.main:app --host 127.0.0.1 --port 8088
) else (
    call conda create -n %ENV_NAME% python=3.13 -y
    call conda activate %ENV_NAME%
    if exist "%BACKEND_DIR%\wheels" (
        pip install --no-index --find-links="%BACKEND_DIR%\wheels" -r "%BACKEND_DIR%\requirements.txt"
    ) else (
        pip install -r "%BACKEND_DIR%\requirements.txt"
    )
    echo.
    echo Lancement : conda activate %ENV_NAME% ^&^& python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
)

endlocal