from app import main
from app.models import DownloadRequest


def test_direct_download_normalizes_share_text_before_ticket_verification(monkeypatch):
    raw = "复制打开抖音 https://v.douyin.com/AbCdEf/ 看看视频"
    normalized = "https://v.douyin.com/AbCdEf/"
    calls = []

    monkeypatch.setenv("ENABLE_DIRECT_DOWNLOAD", "true")
    monkeypatch.setattr(main, "extract_supported_url", lambda value: normalized if value == raw else value)
    monkeypatch.setattr(
        main,
        "verify_analysis_token",
        lambda token, url, asset_id: calls.append((token, url, asset_id)),
    )
    monkeypatch.setattr(main.downloader, "download", lambda url, asset_id: (url, asset_id))

    payload = DownloadRequest(url=raw, asset_id="video:best", analysis_token="x" * 20)
    assert main.download_media(payload) == (normalized, "video:best")
    assert calls == [("x" * 20, normalized, "video:best")]
