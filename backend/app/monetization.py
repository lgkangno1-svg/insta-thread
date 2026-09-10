from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


_ALLOWED_EVENTS = {
    "impression",
    "click",
    "continue",
    "download_started",
    "download_ready",
    "download_error",
}
_ALLOWED_PLATFORMS = {"download", "youtube", "instagram", "threads", "douyin", "xiaohongshu"}
_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)
_loaded = False


def _metrics_path() -> Path | None:
    raw = os.getenv("MONETIZATION_METRICS_FILE", "").strip()
    if not raw:
        return None
    return Path(raw)


def _load_once() -> None:
    global _loaded
    if _loaded:
        return
    path = _metrics_path()
    if path and path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(key, str) and isinstance(value, int) and value >= 0:
                        _counters[key] = value
        except (OSError, ValueError, TypeError):
            pass
    _loaded = True


def _persist() -> None:
    path = _metrics_path()
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(_counters), sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def campaign_config() -> dict[str, object]:
    campaign_id = os.getenv("MONETIZATION_CAMPAIGN_ID", "").strip()[:80]
    sponsor_url = os.getenv("MONETIZATION_SPONSOR_URL", "").strip()
    parsed = urlparse(sponsor_url) if sponsor_url else None
    valid_url = bool(parsed and parsed.scheme == "https" and parsed.netloc)
    requested = os.getenv("MONETIZATION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    try:
        delay = int(os.getenv("MONETIZATION_DELAY_SECONDS", "4"))
    except ValueError:
        delay = 4
    try:
        frequency = int(os.getenv("MONETIZATION_FREQUENCY", "1"))
    except ValueError:
        frequency = 1

    enabled = bool(requested and campaign_id and valid_url)
    return {
        "enabled": enabled,
        "delaySeconds": max(0, min(delay, 15)),
        "frequency": max(1, min(frequency, 20)),
        "campaignId": campaign_id if enabled else "",
        "sponsorLabel": os.getenv("MONETIZATION_SPONSOR_LABEL", "Sponsored message")[:80],
        "sponsorTitle": os.getenv("MONETIZATION_SPONSOR_TITLE", "A short message from our sponsor")[:160],
        "sponsorText": os.getenv("MONETIZATION_SPONSOR_TEXT", "")[:600],
        "sponsorUrl": sponsor_url if enabled else "",
        "sponsorCta": os.getenv("MONETIZATION_SPONSOR_CTA", "Visit sponsor")[:80],
        "affiliateDisclosure": os.getenv(
            "MONETIZATION_DISCLOSURE",
            "Some links may be affiliate links. A purchase may generate a commission at no extra cost to you.",
        )[:300],
    }


def record_event(event: str, campaign_id: str, platform: str) -> None:
    if event not in _ALLOWED_EVENTS or platform not in _ALLOWED_PLATFORMS:
        return
    campaign = campaign_id.strip()[:80] or "unconfigured"
    key = f"{campaign}:{platform}:{event}"
    with _lock:
        _load_once()
        _counters[key] += 1
        try:
            _persist()
        except OSError:
            # Metrics must never break the core downloader flow.
            pass


def snapshot() -> dict[str, int]:
    with _lock:
        _load_once()
        return dict(_counters)
