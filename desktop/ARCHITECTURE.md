# Architecture

The EXE is a thin Windows client. Extraction remains server-side so platform adapters can be fixed without forcing users to reinstall the application.

Flow:

`URL -> POST /api/v1/analyze -> asset selection -> POST /api/v1/jobs -> poll /api/v1/jobs/{id} -> GET /api/v1/jobs/{id}/file -> selected local folder`

Runtime code uses only the Python standard library (`tkinter`, `urllib`, `threading`, `pathlib`). PyInstaller is used only at build time to produce the single-file Windows executable.
