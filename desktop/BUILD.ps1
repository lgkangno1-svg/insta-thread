$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
  python make_windows_resources.py
  python -m unittest test_core.py -v
  python -m pip install --upgrade "pyinstaller>=6.10,<7"
  pyinstaller --noconfirm --clean --onefile --windowed `
    --name AVOCADOSS-Downloader `
    --paths . `
    --icon assets/app.ico `
    --version-file assets/version_info.txt `
    --add-data "VERSION;." `
    --add-data "assets/app.ico;assets" `
    app.py
  if (-not (Test-Path dist/AVOCADOSS-Downloader.exe)) { throw 'EXE was not created' }
  $hash = (Get-FileHash dist/AVOCADOSS-Downloader.exe -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  AVOCADOSS-Downloader.exe" | Set-Content -NoNewline -Encoding ascii dist/AVOCADOSS-Downloader.exe.sha256
  Write-Host "Built dist/AVOCADOSS-Downloader.exe"
  Write-Host "SHA256 $hash"
}
finally {
  Pop-Location
}
