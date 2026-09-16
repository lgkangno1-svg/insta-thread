$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
  python make_windows_resources.py
  python -m pip install --upgrade -r requirements-build.txt
  python -m unittest test_core.py test_instagram_fallback.py test_desktop_extras.py test_windows_updater.py -v
  python -m py_compile app.py app_enhanced.py app_compact.py core.py desktop_extras.py instagram_fallback.py instagram_runtime_hook.py windows_updater.py make_windows_resources.py
  pyinstaller --noconfirm --clean --onefile --windowed `
    --name AVOCADOSS-Downloader `
    --paths . `
    --runtime-hook instagram_runtime_hook.py `
    --hidden-import instagram_fallback `
    --hidden-import windows_updater `
    --icon assets/app.ico `
    --version-file assets/version_info.txt `
    --add-data "VERSION;." `
    --add-data "assets/app.ico;assets" `
    app_compact.py
  if (-not (Test-Path dist/AVOCADOSS-Downloader.exe)) { throw 'EXE was not created' }
  $hash = (Get-FileHash dist/AVOCADOSS-Downloader.exe -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  AVOCADOSS-Downloader.exe" | Set-Content -NoNewline -Encoding ascii dist/AVOCADOSS-Downloader.exe.sha256
  Write-Host "Built dist/AVOCADOSS-Downloader.exe"
  Write-Host "SHA256 $hash"
}
finally {
  Pop-Location
}
