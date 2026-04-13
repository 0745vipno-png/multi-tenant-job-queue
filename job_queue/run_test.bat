@echo off
:: 1. 強制設定終端機編碼為 UTF-8 (解決 Emoji 亂碼問題)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 >nul

:: 2. 呼叫外部 PowerShell 執行（這樣語法最穩，不會閃退）
powershell -NoProfile -ExecutionPolicy Bypass -File "run_test.ps1"
:: 2. 使用 PowerShell 執行核心邏輯，並繞過權限限制 (ExecutionPolicy)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^

:: 3. 萬一腳本噴錯，保留現場不閃退
if %errorlevel% neq 0 (
    echo.
    echo ❌ [Error] 執行過程中發生錯誤，請檢查上方訊息。
    pause
)
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; ^
    Write-Host '`n🚀 Starting SaaS Job Queue Engine...' -ForegroundColor Cyan; ^
    Write-Host '🧹 Cleaning __pycache__...' -ForegroundColor Gray; ^
    Remove-Item -Path '**/__pycache__', '**/*.pyc' -Recurse -Force -ErrorAction SilentlyContinue; ^
    if ($null -eq $env:VIRTUAL_ENV) { Write-Host '⚠️ Warning: Not in a virtual environment!' -ForegroundColor Red }; ^
    $env:PYTHONPATH = '.'; ^
    Write-Host '🧪 Running Full Lifecycle Integration Test...' -ForegroundColor Yellow; ^
    python -m pytest -s tests/unit/integration/test_full_lifecycle.py; ^
    if ($LASTEXITCODE -eq 0) { ^
        Write-Host '`n🎉 ALL SYSTEMS GO! Your Engine is rock solid.' -ForegroundColor Green; ^
        Write-Host '✅ [Success] Submit, Lease, and Ack Lifecycle Completed.' -ForegroundColor Green; ^
    } else { ^
        Write-Host '`n❌ TEST FAILED. Check the error trace above.' -ForegroundColor Red; ^
    }; ^
    Write-Host '`n按任意鍵退出...'; ^
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')"
