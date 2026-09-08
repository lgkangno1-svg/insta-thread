from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException

_secret_text = os.getenv("DOWNLOAD_TOKEN_SECRET", "").strip()
_SECRET = _secret_text.encode("utf-8") if _secret_text else secrets.token_bytes(32)


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(value, high))


def sponsor_gate_enabled() -> bool:
    return os.getenv("SPONSOR_GATE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def sponsor_gate_seconds() -> int:
    if not sponsor_gate_enabled():
        return 0
    return _bounded_int("SPONSOR_GATE_SECONDS", 4, 0, 15)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _url_digest(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def issue_analysis_token(url: str, asset_ids: list[str]) -> str:
    now = int(time.time())
    ttl = _bounded_int("ANALYSIS_TOKEN_TTL_SECONDS", 900, 60, 3600)
    payload = {
        "u": _url_digest(url),
        "a": sorted(set(asset_ids)),
        "iat": now,
        "exp": now + ttl,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64encode(hmac.new(_SECRET, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_analysis_token(token: str, url: str, asset_id: str) -> None:
    try:
        body, signature = token.split(".", 1)
        supplied_sig = _b64decode(signature)
    except Exception as exc:
        raise HTTPException(status_code=403, detail="Invalid or missing analysis token") from exc

    expected_sig = hmac.new(_SECRET, body.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(supplied_sig, expected_sig):
        raise HTTPException(status_code=403, detail="Invalid or expired analysis token")

    try:
        payload = json.loads(_b64decode(body))
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        allowed_assets = payload["a"]
        url_hash = payload["u"]
    except Exception as exc:
        raise HTTPException(status_code=403, detail="Invalid or expired analysis token") from exc

    now = int(time.time())
    if expires_at < now or issued_at > now + 30:
        raise HTTPException(status_code=403, detail="Analysis token expired; analyze the link again")
    if not hmac.compare_digest(str(url_hash), _url_digest(url)):
        raise HTTPException(status_code=403, detail="Analysis token does not match this URL")
    if not isinstance(allowed_assets, list) or asset_id not in allowed_assets:
        raise HTTPException(status_code=403, detail="Asset was not present in the analyzed result")

    gate = sponsor_gate_seconds()
    ready_at = issued_at + gate
    if gate and now < ready_at:
        remaining = max(1, ready_at - now)
        raise HTTPException(status_code=429, detail=f"Download gate is not ready. Retry in {remaining}s")
