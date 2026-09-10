from app.services import downloader


def test_analyze_passes_normalized_share_url_and_returns_source_url(monkeypatch):
    raw = "标题 https://www.xiaohongshu.com/discovery/item/6a73dffa000000002c006ead?xsec_token=keep=&xsec_source=pc_share 复制打开"
    normalized = "https://www.xiaohongshu.com/discovery/item/6a73dffa000000002c006ead?xsec_token=keep=&xsec_source=pc_share"

    class Result:
        assets = [type("Asset", (), {"id": "image:0"})()]

        def model_copy(self, update):
            return update

    monkeypatch.setattr(downloader, "resolve_share_url", lambda url: url)
    monkeypatch.setattr(downloader.xiaohongshu_adapter, "analyze", lambda url: Result() if url == normalized else None)
    monkeypatch.setattr(downloader, "issue_analysis_token", lambda url, ids: f"ticket:{url}:{','.join(ids)}")
    monkeypatch.setattr(downloader, "sponsor_gate_enabled", lambda: False)
    monkeypatch.setattr(downloader, "sponsor_gate_seconds", lambda: 0)

    result = downloader.analyze(raw)
    assert result["source_url"] == normalized
    assert result["analysis_token"] == f"ticket:{normalized}:image:0"
