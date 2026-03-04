# Script de Reconstrucție Automată BVB Monitor
Write-Host "--- Pornire Proces Rebuild BVB Monitor ---" -ForegroundColor Cyan

# 1. Curățenie fișiere vechi
Write-Host "[1/4] Curățare mediu de build vechi..." -ForegroundColor Yellow
Remove-Item -Path "build", "dist", "bvb.spec", "bvb.build" -Force -Recurse -ErrorAction SilentlyContinue

# 2. Verificare/Creare Virtual Environment
if (-Not (Test-Path "venv")) {
    Write-Host "[2/4] Creare Virtual Environment nou..." -ForegroundColor Yellow
    python -m venv venv
} else {
    Write-Host "[2/4] Virtual Environment existent găsit." -ForegroundColor Green
}

# 3. Instalare/Update Dependency-uri
Write-Host "[3/4] Instalare pachete necesare (pandas, requests, matplotlib, lxml, pyinstaller)..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt

# 4. Generare Executabil
Write-Host "[4/4] Rulare PyInstaller pentru v1.0.22..." -ForegroundColor Yellow
.\venv\Scripts\pyinstaller.exe --clean --onefile --noconsole --name "BvbMonitor" bvb.py

Write-Host "`n--- PROCES FINALIZAT CU SUCCES! ---" -ForegroundColor Green
Write-Host "Executabilul se află în folderul: $(Get-Location)\dist\BvbMonitor.exe" -ForegroundColor White
