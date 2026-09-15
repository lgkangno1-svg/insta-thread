# AVOCADOSS Downloader for Windows

Windows desktop client for the existing AVOCADOSS public-media API.

## Supported links

- YouTube
- Instagram / Reels
- Threads
- Douyin / 도우인
- Xiaohongshu / 샤오홍슈 / RedNote

The desktop app does not scrape browser cookies, does not require login, and contains no AdSense or sponsor gate. It sends only the URL the user explicitly analyzes to `https://download.avocadoss.co.kr` and uses the same analyze/job/file pipeline as the web app.

## User flow

1. Paste a link or copied share message.
2. Click **링크 분석**.
3. Choose the returned video/image/archive option.
4. Choose a download folder.
5. Click **선택 항목 다운로드**.

The default folder is the current Windows user's Downloads folder. Filename collisions are resolved with `(2)`, `(3)`, etc.

## Local development

```powershell
cd desktop
python app.py
```

No third-party runtime packages are required; the app uses the Python standard library and Tkinter.

## Build EXE

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name AVOCADOSS-Downloader --paths desktop desktop/app.py
```

Output:

```text
dist/AVOCADOSS-Downloader.exe
```

GitHub Actions also builds and uploads the EXE as an artifact on desktop-related pull requests and on pushes to `main` that touch `desktop/**`.
