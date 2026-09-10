from fastapi.testclient import TestClient

from app import monetization
from app.main import app

client = TestClient(app)


def _reset_metrics() -> None:
    with monetization._lock:
        monetization._counters.clear()
        monetization._loaded = False


def test_campaign_stays_disabled_without_valid_https_url(monkeypatch):
    monkeypatch.setenv("MONETIZATION_ENABLED", "true")
    monkeypatch.setenv("MONETIZATION_CAMPAIGN_ID", "campaign-1")
    monkeypatch.setenv("MONETIZATION_SPONSOR_URL", "http://example.com/offer")
    assert monetization.campaign_config()["enabled"] is False


def test_campaign_runtime_config_is_clamped(monkeypatch):
    monkeypatch.setenv("MONETIZATION_ENABLED", "true")
    monkeypatch.setenv("MONETIZATION_CAMPAIGN_ID", "campaign-1")
    monkeypatch.setenv("MONETIZATION_SPONSOR_URL", "https://example.com/offer")
    monkeypatch.setenv("MONETIZATION_DELAY_SECONDS", "999")
    monkeypatch.setenv("MONETIZATION_FREQUENCY", "999")
    config = monetization.campaign_config()
    assert config["enabled"] is True
    assert config["delaySeconds"] == 15
    assert config["frequency"] == 20
    assert config["sponsorUrl"] == "https://example.com/offer"


def test_aggregate_metrics_persist_without_personal_data(monkeypatch, tmp_path):
    metrics_file = tmp_path / "metrics.json"
    monkeypatch.setenv("MONETIZATION_METRICS_FILE", str(metrics_file))
    _reset_metrics()
    monetization.record_event("impression", "campaign-1", "instagram")
    monetization.record_event("click", "campaign-1", "instagram")
    snapshot = monetization.snapshot()
    assert snapshot["campaign-1:instagram:impression"] == 1
    assert snapshot["campaign-1:instagram:click"] == 1
    text = metrics_file.read_text(encoding="utf-8")
    assert "http" not in text
    assert "cookie" not in text.lower()


def test_event_api_accepts_known_event_and_rejects_unknown(monkeypatch, tmp_path):
    monkeypatch.setenv("MONETIZATION_METRICS_FILE", str(tmp_path / "events.json"))
    _reset_metrics()
    ok = client.post(
        "/api/v1/monetization/events",
        json={"event": "download_ready", "campaign_id": "campaign-1", "platform": "youtube"},
    )
    assert ok.status_code == 204
    bad = client.post(
        "/api/v1/monetization/events",
        json={"event": "arbitrary", "campaign_id": "campaign-1", "platform": "youtube"},
    )
    assert bad.status_code == 422
