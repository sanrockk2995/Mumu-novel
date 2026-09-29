@echo off
chcp 65001 >nul
title MuMuAINovel
cd /d "%~dp0"

echo ========================================================
echo             KHỞI ĐỘNG DỰ ÁN MUMUAINOVEL
echo ========================================================
echo  - Địa chỉ:  http://localhost:8000
echo  - Tài khoản: admin
echo  - Mật khẩu:  admin123
echo ========================================================

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist "%~dp0backend\venv\Scripts\python.exe" (
    echo [LỖI] Không tìm thấy môi trường Python tại backend\venv!
    echo Vui lòng đảm bảo thư mục backend\venv tồn tại.
    pause
    exit /b 1
)

:: Tự động mở trình duyệt sau 3 giây
start "" powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000'"

:: Chạy máy chủ backend (phục vụ cả API và giao diện Web)
cd /d "%~dp0backend"
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
