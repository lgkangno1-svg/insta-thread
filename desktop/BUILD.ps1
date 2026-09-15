$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install --upgrade "pyinstaller>=6.10,<7"
pyinstaller --noconfirm --clean --onefile --windowed --name AVOCADOSS-Downloader --paths desktop desktop/app.py
Write-Host "Built: $PWD\dist\AVOCADOSS-Downloader.exe"
