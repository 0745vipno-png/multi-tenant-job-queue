@echo off
setlocal
:: 1. 設定編碼為 UTF-8
chcp 65001 >nul

echo.
echo 🚀 Starting SaaS Job Queue Engine...
echo ---------------------------------------

:: 2. 清除緩存
echo 🧹 Cleaning __pycache__...
powershell -NoProfile -Command "Get-ChildItem -Path . -Include '__pycache__','*.pyc' -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse"

:: 3. 設定 PYTHONPATH 並執行測試
set PYTHONPATH=.
echo 🧪 Running Full Lifecycle Integration Test...
python -m pytest -s tests/unit/integration/test_full_lifecycle.py

:: 4. 判斷結果並顯示對應 Emoji
if %errorlevel% equ 0 (
	echo.
    powershell -NoProfile -Command "Write-Host '🎉 ALL SYSTEMS GO! Your Engine is rock solid.' -ForegroundColor Green"
    powershell -NoProfile -Command "Write-Host '✅ [Success] Submit, Lease, and Ack Lifecycle Completed.' -ForegroundColor Green"
) else (
    powershell -NoProfile -Command "Write-Host '`n❌ TEST FAILED. Check the error trace above.' -ForegroundColor Red"
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo 測試結束。
pause
