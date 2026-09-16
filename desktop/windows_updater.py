from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class WindowsUpdaterError(RuntimeError):
    pass


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_update_script(new_exe: Path, current_exe: Path, pid: int, log_path: Path) -> str:
    source = _ps_quote(str(new_exe))
    target = _ps_quote(str(current_exe))
    log = _ps_quote(str(log_path))
    app_pid = int(pid)
    return f"""$ErrorActionPreference = 'Stop'
$Source = {source}
$Target = {target}
$Log = {log}
$AppPid = {app_pid}

function Write-UpdateLog([string]$Message) {{
    try {{
        $stamp = (Get-Date).ToString('s')
        Add-Content -LiteralPath $Log -Value ($stamp + ' ' + $Message) -Encoding UTF8
    }} catch {{ }}
}}

Write-UpdateLog 'updater started'

try {{
    for ($wait = 0; $wait -lt 240; $wait++) {{
        if (-not (Get-Process -Id $AppPid -ErrorAction SilentlyContinue)) {{ break }}
        Start-Sleep -Milliseconds 250
    }}

    if (Get-Process -Id $AppPid -ErrorAction SilentlyContinue) {{
        Write-UpdateLog 'old process did not exit within 60 seconds'
        exit 10
    }}

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {{
        Write-UpdateLog 'verified update executable is missing'
        exit 12
    }}

    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    $updated = $false

    for ($attempt = 1; $attempt -le 20; $attempt++) {{
        try {{
            Copy-Item -LiteralPath $Source -Destination $Target -Force -ErrorAction Stop
            $targetHash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash
            if ($targetHash -ne $sourceHash) {{
                throw 'post-copy SHA-256 mismatch'
            }}
            $updated = $true
            Write-UpdateLog ('replacement succeeded on attempt ' + $attempt)
            break
        }} catch {{
            Write-UpdateLog ('replacement attempt ' + $attempt + ' failed: ' + $_.Exception.Message)
            Start-Sleep -Milliseconds 500
        }}
    }}

    if (-not $updated) {{
        Write-UpdateLog 'could not replace the original executable; launching verified update from temp as fallback'
        Start-Process -FilePath $Source
        exit 11
    }}

    $workDir = Split-Path -LiteralPath $Target -Parent
    Start-Process -FilePath $Target -WorkingDirectory $workDir
    Start-Sleep -Milliseconds 750
    Remove-Item -LiteralPath $Source -Force -ErrorAction SilentlyContinue
    Write-UpdateLog 'updated executable launched successfully'
    exit 0
}} catch {{
    Write-UpdateLog ('fatal updater error: ' + $_.Exception.Message)
    try {{ Start-Process -FilePath $Source }} catch {{ }}
    exit 20
}}
"""


def encode_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def schedule_windows_self_update(new_exe: Path, current_exe: Path, pid: int) -> Path:
    if os.name != "nt":
        raise WindowsUpdaterError("자동 교체는 Windows 실행파일에서만 지원합니다.")

    source = new_exe.resolve()
    target = current_exe.resolve()
    if not source.is_file() or not target.is_file():
        raise WindowsUpdaterError("업데이트할 실행파일을 찾을 수 없습니다.")

    log_path = Path(tempfile.gettempdir()) / f"AVOCADOSS-Updater-{int(pid)}.log"
    try:
        log_path.write_text(
            f"source={source}\ntarget={target}\npid={int(pid)}\n",
            encoding="utf-8",
        )
    except OSError:
        pass

    script = build_update_script(source, target, int(pid), log_path)
    encoded = encode_powershell(script)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                encoded,
            ],
            creationflags=flags,
            close_fds=True,
        )
    except OSError as exc:
        raise WindowsUpdaterError(f"업데이트 교체 프로세스를 시작하지 못했습니다: {exc}") from exc
    return log_path


def patch_windows_updater(core_module: Any) -> None:
    def patched(new_exe: Path, current_exe: Path, pid: int) -> Path:
        try:
            return schedule_windows_self_update(new_exe, current_exe, pid)
        except WindowsUpdaterError as exc:
            raise core_module.ApiError(str(exc)) from exc

    core_module.schedule_windows_self_update = patched
