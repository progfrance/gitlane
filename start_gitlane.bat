@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "REQ_FILE=%BACKEND_DIR%\requirements.txt"
set "APP_DIR=%BACKEND_DIR%"
set "ENV_NAME=gitlane"
set "HOST=127.0.0.1"
set "PORT=8088"

if not exist "%BACKEND_DIR%\app" (
  echo [ERROR] Backend folder not found: "%BACKEND_DIR%\app"
  pause
  exit /b 1
)

if not exist "%REQ_FILE%" (
  echo [ERROR] Missing requirements file: "%REQ_FILE%"
  pause
  exit /b 1
)

set "CONDA_EXE=C:\ProgramData\miniforge3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" (
  where conda >nul 2>&1
  if %errorlevel%==0 (
    set "CONDA_EXE=conda"
  ) else (
    echo [ERROR] conda not found.
    echo Expected: C:\ProgramData\miniforge3\Scripts\conda.exe
    pause
    exit /b 1
  )
)

echo [INFO] Checking conda env "%ENV_NAME%"...
"%CONDA_EXE%" run -n %ENV_NAME% python --version >nul 2>&1
if errorlevel 1 (
  echo [INFO] Creating conda env "%ENV_NAME%" with Python 3.13...
  "%CONDA_EXE%" create -n %ENV_NAME% python=3.13 -y
  if errorlevel 1 goto :error
)

echo [INFO] Installing/updating backend dependencies...
"%CONDA_EXE%" run -n %ENV_NAME% python -m pip install -r "%REQ_FILE%"
if errorlevel 1 goto :error

echo [INFO] Starting backend on http://%HOST%:%PORT% ...
start "GitLane Backend" cmd /k ""%CONDA_EXE%" run -n %ENV_NAME% python -m uvicorn app.main:app --app-dir "%APP_DIR%" --host %HOST% --port %PORT%"

timeout /t 2 /nobreak >nul
start "" "http://%HOST%:%PORT%/picker"

echo [OK] GitLane started.
echo - Backend window: "GitLane Backend"
echo - Browser: http://%HOST%:%PORT%/picker
exit /b 0

:error
echo [ERROR] Failed to start GitLane.
pause
exit /b 1
