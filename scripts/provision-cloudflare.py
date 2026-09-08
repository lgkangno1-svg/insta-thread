#!/usr/bin/env python3
"""Provision the dedicated AVOCADOSS Cloudflare Tunnel and DNS records.

Required environment:
  CLOUDFLARE_API_TOKEN

The API token should be scoped to avocadoss.co.kr and include:
  - Account / Cloudflare Tunnel / Edit
  - Zone / DNS / Edit
  - Zone / Zone / Read (used to discover zone + account IDs)

The script never prints the API token or Tunnel token. The Tunnel token is written
into .env with mode 0600 so Docker Compose can start only this project's connector.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.cloudflare.com/client/v4"
ZONE_NAME = "avocadoss.co.kr"
TUNNEL_NAME = "avocadoss-download"
HOSTNAMES = [
    "download.avocadoss.co.kr",
    "youtube.avocadoss.co.kr",
    "insta.avocadoss.co.kr",
    "thread.avocadoss.co.kr",
    "douyin.avocadoss.co.kr",
    "xiaohongshu.avocadoss.co.kr",
]
SERVICE = "http://web:80"
ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"


def fail(message: str) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
if not TOKEN:
    fail("CLOUDFLARE_API_TOKEN is required")


def request(method: str, path: str, body: dict | None = None, query: dict | None = None):
    url = API + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "insta-thread-cloudflare-provision/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1200]
        fail(f"Cloudflare API {method} {path} returned HTTP {exc.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        fail(f"Cloudflare API request failed for {method} {path}: {exc}")
    if not payload.get("success"):
        fail(f"Cloudflare API rejected {method} {path}: {payload.get('errors')}")
    return payload.get("result")


def discover_zone() -> tuple[str, str]:
    zones = request("GET", "/zones", query={"name": ZONE_NAME, "status": "active", "per_page": 50})
    if not isinstance(zones, list) or len(zones) != 1:
        fail(f"Expected exactly one active Cloudflare zone named {ZONE_NAME}; found {len(zones or [])}")
    zone = zones[0]
    zone_id = zone.get("id")
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip() or (zone.get("account") or {}).get("id")
    if not zone_id or not account_id:
        fail("Could not determine Cloudflare zone/account ID")
    return zone_id, account_id


def get_or_create_tunnel(account_id: str) -> str:
    tunnels = request(
        "GET",
        f"/accounts/{account_id}/cfd_tunnel",
        query={"name": TUNNEL_NAME, "is_deleted": "false", "per_page": 100},
    )
    exact = [item for item in (tunnels or []) if item.get("name") == TUNNEL_NAME and not item.get("deleted_at")]
    if len(exact) > 1:
        fail(f"Multiple active tunnels named {TUNNEL_NAME}; refusing to guess")
    if exact:
        tunnel_id = exact[0].get("id")
        if not tunnel_id:
            fail("Existing tunnel has no ID")
        return tunnel_id

    created = request(
        "POST",
        f"/accounts/{account_id}/cfd_tunnel",
        body={"name": TUNNEL_NAME, "config_src": "cloudflare"},
    )
    tunnel_id = (created or {}).get("id")
    if not tunnel_id:
        fail("Cloudflare created a tunnel without returning its ID")
    return tunnel_id


def protect_existing_tunnel_config(account_id: str, tunnel_id: str) -> None:
    try:
        existing = request("GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations")
    except SystemExit:
        raise
    config = (existing or {}).get("config") if isinstance(existing, dict) else None
    ingress = (config or {}).get("ingress") if isinstance(config, dict) else None
    if not isinstance(ingress, list):
        return
    foreign = []
    allowed = set(HOSTNAMES)
    for rule in ingress:
        hostname = rule.get("hostname") if isinstance(rule, dict) else None
        if hostname and hostname not in allowed:
            foreign.append(hostname)
    if foreign and not truthy("CLOUDFLARE_FORCE_TUNNEL_CONFIG"):
        fail(
            f"Tunnel {TUNNEL_NAME} already contains unrelated hostnames {foreign}. "
            "Use a different tunnel or set CLOUDFLARE_FORCE_TUNNEL_CONFIG=true explicitly."
        )


def configure_tunnel(account_id: str, tunnel_id: str) -> None:
    protect_existing_tunnel_config(account_id, tunnel_id)
    ingress = [{"hostname": hostname, "service": SERVICE, "originRequest": {}} for hostname in HOSTNAMES]
    ingress.append({"service": "http_status:404"})
    request(
        "PUT",
        f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
        body={"config": {"ingress": ingress}},
    )


def upsert_dns(zone_id: str, tunnel_id: str) -> None:
    target = f"{tunnel_id}.cfargotunnel.com"
    force = truthy("CLOUDFLARE_FORCE_DNS")
    for hostname in HOSTNAMES:
        records = request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            query={"name": hostname, "per_page": 100},
        )
        records = records or []
        if len(records) > 1:
            fail(f"Multiple DNS records exist at {hostname}; refusing to guess")
        desired = {
            "type": "CNAME",
            "name": hostname,
            "content": target,
            "ttl": 1,
            "proxied": True,
            "comment": "insta-thread dedicated Cloudflare Tunnel",
        }
        if not records:
            request("POST", f"/zones/{zone_id}/dns_records", body=desired)
            print(f"DNS created: {hostname}")
            continue
        record = records[0]
        if record.get("type") != "CNAME" and not force:
            fail(
                f"Existing {record.get('type')} record at {hostname} will not be overwritten. "
                "Set CLOUDFLARE_FORCE_DNS=true only after confirming it is safe."
            )
        if (
            record.get("type") == "CNAME"
            and str(record.get("content", "")).rstrip(".") == target
            and record.get("proxied") is True
        ):
            print(f"DNS already correct: {hostname}")
            continue
        request("PATCH", f"/zones/{zone_id}/dns_records/{record['id']}", body=desired)
        print(f"DNS updated: {hostname}")


def fetch_tunnel_token(account_id: str, tunnel_id: str) -> str:
    token = request("GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token")
    if not isinstance(token, str) or len(token) < 20:
        fail("Cloudflare did not return a valid Tunnel token")
    return token


def write_env_tunnel_token(tunnel_token: str) -> None:
    if ENV_FILE.exists():
        text = ENV_FILE.read_text(encoding="utf-8")
    elif ENV_EXAMPLE.exists():
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
    else:
        text = ""
    lines = text.splitlines()
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.startswith("CLOUDFLARE_TUNNEL_TOKEN="):
            output.append(f"CLOUDFLARE_TUNNEL_TOKEN={tunnel_token}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.insert(0, f"CLOUDFLARE_TUNNEL_TOKEN={tunnel_token}")
    ENV_FILE.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.chmod(ENV_FILE, 0o600)


def main() -> None:
    zone_id, account_id = discover_zone()
    tunnel_id = get_or_create_tunnel(account_id)
    configure_tunnel(account_id, tunnel_id)
    upsert_dns(zone_id, tunnel_id)
    tunnel_token = fetch_tunnel_token(account_id, tunnel_id)
    write_env_tunnel_token(tunnel_token)
    print(f"Cloudflare provisioned dedicated tunnel: {TUNNEL_NAME} ({tunnel_id})")
    print(f"Tunnel token written securely to: {ENV_FILE}")
    print("No existing unrelated tunnel service was modified.")


if __name__ == "__main__":
    main()
