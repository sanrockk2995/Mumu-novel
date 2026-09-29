@echo off
chcp 65001 >nul
title MuMuAINovel Launcher
cd /d "%~dp0"

echo ========================================================
echo             MENU KHỞI ĐỘNG DỰ ÁN MUMUAINOVEL
echo ========================================================
echo [1] Chạy Web hoàn chỉnh (Cổng 8000 - Tự mở trình duyệt)
echo [2] Chạy chế độ Dev (Backend 8000 + Frontend Vite 5173)
echo [3] Build lại giao diện Frontend (npm run build)
echo [4] Thoát
echo ========================================================
set /p choice="Nhập lựa chọn [1-4] (mặc định 1): "

if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    call "%~dp0run.bat"
    exit /b
)

if "%choice%"=="2" (
    echo Đang khởi động Backend và Frontend Dev...
    set PYTHONUTF8=1
    set PYTHONIOENCODING=utf-8
    
    start "MuMuAINovel - Backend" cmd /k "cd /d ""%~dp0backend"" && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    start "MuMuAINovel - Frontend Dev" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
    
    start "" powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:5173'"
    exit /b
)

if "%choice%"=="3" (
    echo Đang build lại Frontend sang backend/static...
    cd /d "%~dp0frontend"
    call npm run build
    echo Build hoàn tất!
    pause
    exit /b
)

if "%choice%"=="4" (
    exit /b
)

pause
