from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
MAJOR, MINOR, PATCH = [int(part) for part in VERSION.split(".")]


def make_icon(path: Path) -> None:
    width = height = 64
    pixels = bytearray()
    for y in range(height - 1, -1, -1):
        for x in range(width):
            dx = x - 32
            dy = y - 32
            r2 = dx * dx + dy * dy
            if r2 <= 29 * 29:
                b, g, r, a = 105, 176, 68, 255
                if ((x - 32) ** 2) / (15 ** 2) + ((y - 31) ** 2) / (21 ** 2) <= 1:
                    b, g, r, a = 228, 246, 224, 255
                if (x - 32) ** 2 + (y - 39) ** 2 <= 8 * 8:
                    b, g, r, a = 49, 78, 126, 255
                if 30 <= x <= 34 and 14 <= y <= 29:
                    b, g, r, a = 30, 24, 20, 255
                if 24 <= y <= 34 and abs(x - 32) <= (34 - y):
                    b, g, r, a = 30, 24, 20, 255
            else:
                b, g, r, a = 30, 24, 20, 255
            pixels += bytes((b, g, r, a))

    mask_row = ((width + 31) // 32) * 4
    mask = bytes(mask_row * height)
    dib = struct.pack(
        "<IIIHHIIIIII",
        40, width, height * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0,
    ) + pixels + mask
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, len(dib), 22)
    path.write_bytes(header + entry + dib)


def make_version_info(path: Path) -> None:
    path.write_text(
        f'''VSVersionInfo(\n  ffi=FixedFileInfo(\n    filevers=({MAJOR}, {MINOR}, {PATCH}, 0),\n    prodvers=({MAJOR}, {MINOR}, {PATCH}, 0),\n    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)\n  ),\n  kids=[\n    StringFileInfo([StringTable('040904B0', [\n      StringStruct('CompanyName', 'AVOCADOSS'),\n      StringStruct('FileDescription', 'AVOCADOSS Downloader'),\n      StringStruct('FileVersion', '{VERSION}'),\n      StringStruct('InternalName', 'AVOCADOSS-Downloader'),\n      StringStruct('OriginalFilename', 'AVOCADOSS-Downloader.exe'),\n      StringStruct('ProductName', 'AVOCADOSS Downloader'),\n      StringStruct('ProductVersion', '{VERSION}'),\n      StringStruct('LegalCopyright', 'Copyright (c) 2026 AVOCADOSS')\n    ])]),\n    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n  ]\n)\n''',
        encoding="utf-8",
    )


ASSETS.mkdir(parents=True, exist_ok=True)
make_icon(ASSETS / "app.ico")
make_version_info(ASSETS / "version_info.txt")
print(f"Generated Windows resources for v{VERSION}")
