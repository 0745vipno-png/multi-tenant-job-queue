# 1. 介面美化
Write-Host "`n🚀 Starting SaaS Job Queue Engine..." -ForegroundColor Cyan

# 2. 清理舊的 Python 快取 (確保代碼 100% 同步)
Write-Host "🧹 Cleaning __pycache__..." -ForegroundColor Gray
Remove-Item -Path "**/__pycache__" -Recurse -Force -ErrorAction SilentlyContinue

# 3. 設定 PYTHONPATH (告訴 Python 專案根目錄在哪裡)
$env:PYTHONPATH = "."

# 4. 執行整合測試並印出 Step 1, 2, 3 勾勾
Write-Host "🧪 Running Full Lifecycle Integration Test..." -ForegroundColor Yellow
python -m pytest -s tests/unit/integration/test_full_lifecycle.py

# 5. 結束提示
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n🎉 ALL SYSTEMS GO! Your Engine is rock solid." -ForegroundColor Green
    Write-Host "✅ [Success] Submit, Lease, and Ack Lifecycle Completed." -ForegroundColor Green
} else {
    Write-Host "`n❌ TEST FAILED. Check the error trace above." -ForegroundColor Red
}

Write-Host "`nPress any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
