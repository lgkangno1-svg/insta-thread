import pytest
from fastapi import HTTPException

from app.security import issue_analysis_token, sponsor_gate_seconds, verify_analysis_token


URL = "https://www.instagram.com/reel/ABC123/"


def test_analysis_token_accepts_bound_url_and_asset(monkeypatch):
    monkeypatch.setenv("SPONSOR_GATE_ENABLED", "false")
    token = issue_analysis_token(URL, ["video:best", "thumbnail:0"])
    verify_analysis_token(token, URL, "video:best")


def test_analysis_token_rejects_url_swap(monkeypatch):
    monkeypatch.setenv("SPONSOR_GATE_ENABLED", "false")
    token = issue_analysis_token(URL, ["video:best"])
    with pytest.raises(HTTPException) as exc:
        verify_analysis_token(token, "https://www.instagram.com/reel/OTHER/", "video:best")
    assert exc.value.status_code == 403


def test_analysis_token_rejects_asset_swap(monkeypatch):
    monkeypatch.setenv("SPONSOR_GATE_ENABLED", "false")
    token = issue_analysis_token(URL, ["video:best"])
    with pytest.raises(HTTPException) as exc:
        verify_analysis_token(token, URL, "thumbnail:0")
    assert exc.value.status_code == 403


def test_analysis_token_rejects_tampering(monkeypatch):
    monkeypatch.setenv("SPONSOR_GATE_ENABLED", "false")
    token = issue_analysis_token(URL, ["video:best"])
    body, sig = token.split(".", 1)
    replacement = "A" if sig[-1] != "A" else "B"
    tampered = f"{body}.{sig[:-1]}{replacement}"
    with pytest.raises(HTTPException) as exc:
        verify_analysis_token(tampered, URL, "video:best")
    assert exc.value.status_code == 403


def test_server_side_sponsor_gate_blocks_early_download(monkeypatch):
    monkeypatch.setenv("SPONSOR_GATE_ENABLED", "true")
    monkeypatch.setenv("SPONSOR_GATE_SECONDS", "4")
    assert sponsor_gate_seconds() == 4
    token = issue_analysis_token(URL, ["video:best"])
    with pytest.raises(HTTPException) as exc:
        verify_analysis_token(token, URL, "video:best")
    assert exc.value.status_code == 429
