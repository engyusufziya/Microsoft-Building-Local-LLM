"""`/api/metrics` -- dosya yoksa 503 METRICS_NOT_GENERATED, varsa doğrudan servis."""

from __future__ import annotations

import json

import backend.routes.metrics as metrics_module


def test_metrics_returns_503_when_results_file_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(metrics_module, "RESULTS_PATH", tmp_path / "does-not-exist.json")
    r = client.get("/api/metrics")
    assert r.status_code == 503
    assert r.json()["code"] == "METRICS_NOT_GENERATED"


def test_metrics_serves_results_file_when_present(client, monkeypatch, tmp_path):
    payload = {
        "generated_at": "2026-08-13T15:00:00+03:00",
        "config": {"min_score": 0.45, "top_k": 4},
        "models": [{"alias": "qwen2.5-7b", "summary": {"passed": 15, "total": 15}}],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(metrics_module, "RESULTS_PATH", results_path)

    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert r.json() == payload


def test_metrics_real_project_has_no_results_yet(client):
    """Gerçek proje yolu: eval/results.json henüz üretilmedi (M3/M4 backend-api
    görevi DEĞİL). Bu, mock kullanmadan üretim davranışını doğrular."""
    r = client.get("/api/metrics")
    assert r.status_code == 503
    assert r.json()["code"] == "METRICS_NOT_GENERATED"
