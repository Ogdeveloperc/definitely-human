@echo off
rem Definitely Human - download the latest installer from the private GitHub repo and run it.
rem Double-click this file. Re-run it later to update to the newest version.
title Definitely Human - Indir ve Kur
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = Get-Content -LiteralPath '%~f0' -Raw; Invoke-Expression ($s.Substring($s.LastIndexOf('#POWERSHELL#') + 12))"
echo.
pause
exit /b

#POWERSHELL#
$ErrorActionPreference = 'Stop'
$repo = 'Ogdeveloperc/definitely-human'
function Say($m, $c = 'Green') { Write-Host ''; Write-Host $m -ForegroundColor $c }

try {
  # 1) GitHub CLI (official, via winget)
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Say '[1/4] GitHub araci kuruluyor (gh)... / Installing GitHub CLI...'
    winget install --id GitHub.cli -e --silent --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { $env:Path += ";$env:ProgramFiles\GitHub CLI" }
  } else { Say '[1/4] GitHub araci hazir. / GitHub CLI found.' }

  # 2) Sign in (browser) only if needed
  $loggedIn = $true
  gh auth status --hostname github.com *> $null; if ($LASTEXITCODE -ne 0) { $loggedIn = $false }
  $didLogin = $false
  if (-not $loggedIn) {
    Say '[2/4] Tarayicida GitHub girisi acilacak. Ekrandaki kodu girip onaylayin.' 'Yellow'
    Write-Host '      A browser window will open for GitHub sign-in; enter the code shown here.'
    gh auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) { throw 'GitHub girisi yapilamadi / sign-in failed' }
    $didLogin = $true
  } else { Say '[2/4] GitHub girisi zaten var. / Already signed in.' }

  # 3) Download the newest installer
  Say '[3/4] En yeni kurulum dosyasi indiriliyor... / Downloading the latest installer...'
  $dir = Join-Path $env:TEMP 'DefinitelyHuman'
  New-Item -ItemType Directory -Force $dir | Out-Null
  Remove-Item "$dir\*.exe" -ErrorAction SilentlyContinue
  gh release download --repo $repo --pattern 'DefinitelyHuman-Setup-*.exe' --dir $dir --clobber
  if ($LASTEXITCODE -ne 0) { throw 'Indirme basarisiz / download failed' }
  $exe = Get-ChildItem "$dir\DefinitelyHuman-Setup-*.exe" | Sort-Object LastWriteTime | Select-Object -Last 1
  Write-Host "      $($exe.Name)"

  # 4) Run it (Windows will ask for administrator permission)
  Say '[4/4] Kurulum baslatiliyor (yonetici izni istenecek)... / Starting setup...'
  Start-Process $exe.FullName -Wait

  if ($didLogin) {
    $a = Read-Host 'GitHub oturumu bu bilgisayardan kapatilsin mi? / Sign out of GitHub on this PC? (E/H)'
    if ($a -match '^[EeYy]') { gh auth logout --hostname github.com; Say 'GitHub oturumu kapatildi. / Signed out.' }
  }
  Say 'Tamam! Masaustundeki "Definitely Human" ile acabilirsiniz. / Done!'
}
catch {
  Say "HATA / ERROR: $_" 'Red'
  Write-Host 'Internet baglantisini kontrol edip bu dosyayi tekrar calistirin.'
}
