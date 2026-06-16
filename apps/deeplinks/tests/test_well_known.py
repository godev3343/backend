"""well-known эндпоинты: assetlinks.json (Android) и AASA (iOS-заглушка)."""

from __future__ import annotations

import json


def test_assetlinks_returns_valid_payload(client, settings):
    settings.ANDROID_PACKAGE_NAME = "com.go.app.go_app"
    settings.ANDROID_CERT_FINGERPRINTS = ["AA:BB:CC", "DD:EE:FF"]

    resp = client.get("/.well-known/assetlinks.json")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/json"
    assert resp["Cache-Control"] == "public, max-age=3600"

    body = json.loads(resp.content)
    assert isinstance(body, list) and len(body) == 1
    entry = body[0]
    assert entry["relation"] == ["delegate_permission/common.handle_all_urls"]
    target = entry["target"]
    assert target["namespace"] == "android_app"
    assert target["package_name"] == "com.go.app.go_app"
    assert target["sha256_cert_fingerprints"] == ["AA:BB:CC", "DD:EE:FF"]


def test_assetlinks_404_when_not_configured(client, settings):
    settings.ANDROID_PACKAGE_NAME = ""
    settings.ANDROID_CERT_FINGERPRINTS = []

    resp = client.get("/.well-known/assetlinks.json")

    assert resp.status_code == 404


def test_aasa_returns_empty_stub(client):
    resp = client.get("/.well-known/apple-app-site-association")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/json"
    assert json.loads(resp.content) == {"applinks": {"details": []}}
