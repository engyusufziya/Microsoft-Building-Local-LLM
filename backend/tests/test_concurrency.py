"""FEATURE_SPEC §7: tüm model çağıran endpoint'ler tek bir asyncio.Lock
arkasında serileşmeli. İki paralel /api/retrieve isteği çakışmamalı."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import rag.retrieve as retrieve_module


def test_parallel_retrieve_requests_are_serialized(ready_client, monkeypatch):
    intervals = []

    def fake_get_top_chunks(query, k, min_score, conn):
        start = time.monotonic()
        time.sleep(0.15)
        intervals.append((start, time.monotonic()))
        return []

    monkeypatch.setattr(retrieve_module, "get_top_chunks", fake_get_top_chunks)

    def call():
        return ready_client.post("/api/retrieve", json={"question": "eşzamanlılık testi"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(call) for _ in range(2)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    assert len(intervals) == 2
    (s1, e1), (s2, e2) = sorted(intervals)
    assert s2 >= e1, f"asyncio.Lock çakışmayı engellemedi, aralıklar örtüşüyor: {intervals}"
