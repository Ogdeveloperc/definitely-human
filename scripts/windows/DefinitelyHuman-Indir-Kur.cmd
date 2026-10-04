@echo off
rem Definitely Human - download the latest installer from GitHub Releases and run it.
rem Double-click this file. Run it again later to update to the newest version.
title Definitely Human - Indir ve Kur
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = Get-Content -LiteralPath '%~f0' -Raw; Invoke-Expression ($s.Substring($s.LastIndexOf('#POWERSHELL#') + 12))"
echo.
pause
exit /b

#POWERSHELL#
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # the progress bar makes Invoke-WebRequest very slow
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repo = 'Ogdeveloperc/definitely-human'
function Say($m, $c = 'Green') { Write-Host ''; Write-Host $m -ForegroundColor $c }

try {
  Say '[1/3] En yeni surum bulunuyor... / Finding the latest version...'
  $rel = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest" -Headers @{ 'User-Agent' = 'definitely-human' }
  $asset = $rel.assets | Where-Object { $_.name -like 'DefinitelyHuman-Setup-*.exe' } | Select-Object -First 1
  if (-not $asset) { throw "Surumde kurulum dosyasi yok / no installer in release $($rel.tag_name)" }
  Write-Host ("      {0}  ({1:N0} MB)" -f $asset.name, ($asset.size / 1MB))

  Say '[2/3] Indiriliyor... / Downloading...'
  $dir = Join-Path $env:TEMP 'DefinitelyHuman'
  New-Item -ItemType Directory -Force $dir | Out-Null
  $exe = Join-Path $dir $asset.name
  Invoke-WebRequest $asset.browser_download_url -OutFile $exe -UseBasicParsing
  if ((Get-Item $exe).Length -ne $asset.size) { throw 'Dosya eksik indi / incomplete download' }

  Say '[3/3] Kurulum baslatiliyor (yonetici izni istenecek)... / Starting setup (admin permission needed)...'
  Start-Process $exe -Wait
  Say 'Tamam! Masaustundeki "Definitely Human" ile acabilirsiniz. / Done!'
}
catch {
  Say "HATA / ERROR: $_" 'Red'
  Write-Host 'Internet baglantisini kontrol edip bu dosyayi tekrar calistirin.'
  Write-Host "Ya da elle indirin / or download manually: https://github.com/$repo/releases/latest"
}
