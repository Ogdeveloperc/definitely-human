# Definitely Human - post-copy setup, run by Setup.exe (and safe to re-run for repairs/updates).
# Installs Python + dependencies (GPU build of PyTorch) with uv and downloads the model.
param([string]$AppDir = $PSScriptRoot)
$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Definitely Human - Kurulum / Setup"
Set-Location $AppDir

# Keep every tool cache inside the install folder (ASCII path, no user-profile surprises).
$env:UV_PYTHON_INSTALL_DIR = Join-Path $AppDir "python"
$env:UV_CACHE_DIR          = Join-Path $AppDir "cache"
$env:UV_LINK_MODE          = "copy"
$env:UV_PYTHON_PREFERENCE  = "only-managed"
$env:HF_HOME               = Join-Path $AppDir "hf"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
$uv = Join-Path $AppDir "bin\uv.exe"

function Step($n, $msg) { Write-Host ""; Write-Host "[$n/3] $msg" -ForegroundColor Green }

try {
  Step 1 "Python ve kutuphaneler kuruluyor (PyTorch GPU ~3 GB)... / Installing Python and libraries..."
  & $uv sync --frozen --no-dev
  if ($LASTEXITCODE -ne 0) { throw "uv sync failed ($LASTEXITCODE)" }

  Step 2 "AI tespit modeli indiriliyor (~4 GB)... / Downloading the detector model..."
  & (Join-Path $AppDir ".venv\Scripts\python.exe") -m definitely_human.cli download
  if ($LASTEXITCODE -ne 0) { throw "model download failed ($LASTEXITCODE)" }

  Step 3 "Ekran karti kontrol ediliyor... / Checking the GPU..."
  & (Join-Path $AppDir ".venv\Scripts\python.exe") -m definitely_human.cli doctor
  & $uv cache clean | Out-Null

  Write-Host ""
  Write-Host "Kurulum tamamlandi! / Setup complete!" -ForegroundColor Green
  Start-Sleep -Seconds 3
  exit 0
}
catch {
  Write-Host ""
  Write-Host "KURULUM HATASI / SETUP ERROR: $_" -ForegroundColor Red
  Write-Host "Internet baglantisini kontrol edip Setup.exe'yi tekrar calistirin."
  Write-Host "Check the internet connection and run Setup.exe again."
  Read-Host "Kapatmak icin Enter / Press Enter to close"
  exit 1
}
