# Release checklist

- Windows CI tests pass.
- PyInstaller creates `AVOCADOSS-Downloader.exe`.
- EXE starts without a console window.
- Analyze and download flow is verified against the production API.
- No browser-cookie, login, private-media, advertising, or tracking integration is present in the desktop client.
- SHA-256 is recorded from the build job.
