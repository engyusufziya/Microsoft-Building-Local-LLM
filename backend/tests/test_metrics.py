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


def test_metrics_serves_real_results_file_matching_spec_schema(client):
    """Gerçek `eval/results.json`'ı mock'suz doğrular (docs/FEATURE_SPEC.md §6.2).

    Bu test yazıldığında dosya henüz üretilmemişti ve "gerçek projede 503
    döner" diye assert ediyordu; M3/M4 ile dosya üretilince kırıldı. Geçici
    bir dosya sistemi durumuna bağlanmak yerine artık ŞEMAYI doğruluyor --
    run_eval.py'nin ürettiği yapı ile frontend'in beklediği (web/lib/types.ts)
    yapı arasındaki sözleşmeyi korur.

    Dosya yoksa test atlanır: üretmek Foundry Local modellerini gerektirir
    (~100 sn), bu testin sorumluluğu değil.
    """
    if not metrics_module.RESULTS_PATH.exists():
        import pytest

        pytest.skip("eval/results.json üretilmemiş (python eval/run_eval.py --json)")

    r = client.get("/api/metrics")
    assert r.status_code == 200
    data = r.json()

    assert set(data) >= {"generated_at", "config", "corpus", "models", "threshold_sweep"}
    assert {"min_score", "top_k"} <= set(data["config"])
    assert data["models"], "en az bir model sonucu bulunmalı"

    for model in data["models"]:
        assert {"alias", "model_id", "is_active", "summary", "questions"} <= set(model)
        summary = model["summary"]
        assert {"passed", "total", "by_category", "retrieval_hits", "avg_seconds"} <= set(summary)
        assert summary["total"] == len(model["questions"])

    # Tam olarak bir model aktif olmalı (rag.config.CHAT_MODEL).
    assert sum(m["is_active"] for m in data["models"]) == 1

    sweep = data["threshold_sweep"]
    assert {"answerable_scores", "other_scores", "table"} <= set(sweep)
