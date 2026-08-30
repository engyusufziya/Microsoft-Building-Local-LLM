"""ESKİ external-content `chunks_fts` şemasından göç — rag/store.py.

Bu bir teorik senaryo DEĞİL: depodaki `rag.db` bu eski şemayla yaşıyordu ve
`ui_proof`'un Faz 5 boş-korpus geçişi (belge yükle, sonra sil) onu
`database disk image is malformed` ile patlattı.

Kök neden: `CREATE VIRTUAL TABLE IF NOT EXISTS` ve `CREATE TRIGGER IF NOT
EXISTS` var olan bir veritabanında hiçbir şey yapmaz, yani şema kararı
değiştiğinde mevcut veritabanları göç etmedi.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from rag import store

# Şema değişikliğinden ÖNCEKİ tanım, birebir.
_OLD_TABLES = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY, filename TEXT UNIQUE NOT NULL,
    page_count INTEGER, chunk_count INTEGER, ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source TEXT NOT NULL, page INTEGER, content TEXT NOT NULL,
    via_ocr INTEGER NOT NULL DEFAULT 0, embedding BLOB NOT NULL
);
"""

_OLD_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content, content='chunks', content_rowid='id', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


def _legacy_db(tmp_path, *, preloaded: int = 0):
    """Eski şemalı veritabanı.

    `preloaded` > 0 ise chunk satırları TETİKLEYİCİLER KURULMADAN ÖNCE
    yazılır. Bu, depodaki `rag.db`'nin gerçek durumu: satırlar indeks
    tetikleyicileri var olmadan yazılmış, sonra `_backfill_fts`'in "boş mu?"
    kontrolü external-content modda yanıltıcı olduğu için (COUNT(*) chunks'ı
    sayıyor) doldurma ATLANMIŞ. Yani indeks boş, satırlar dolu.
    """
    path = tmp_path / "eski.db"
    raw = sqlite3.connect(str(path))
    raw.executescript(_OLD_TABLES)
    if preloaded:
        raw.execute(
            "INSERT INTO documents (filename, page_count, chunk_count, ingested_at)"
            " VALUES ('eski.pdf', 1, ?, '2026-01-01T00:00:00')",
            (preloaded,),
        )
        raw.executemany(
            "INSERT INTO chunks (document_id, source, page, content, via_ocr, embedding)"
            " VALUES (1, 'eski.pdf', 1, ?, 0, X'00000000')",
            [(f"eski içerik {i}",) for i in range(preloaded)],
        )
    raw.executescript(_OLD_FTS)
    raw.commit()
    raw.close()
    return path


def _chunks(name: str, n: int):
    return [
        SimpleNamespace(source=name, page=1, content=f"{name} içerik {i}", via_ocr=False)
        for i in range(n)
    ]


def test_eski_sema_bagimsiz_fts_e_gocurulur(tmp_path):
    conn = store.connect(_legacy_db(tmp_path))
    try:
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='chunks_fts'"
        ).fetchone()[0]
        assert "content='chunks'" not in sql, "external-content tanımı kalmış"

        delete_trigger = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='chunks_ad'"
        ).fetchone()[0]
        assert "DELETE FROM chunks_fts" in delete_trigger
        assert "'delete'" not in delete_trigger
    finally:
        conn.close()


def test_goc_OLMADAN_silme_malformed_ile_patliyor(tmp_path):
    """Hatanın kendisi: göç devre dışıyken silme veritabanını bozuk sayıyor.

    Bu test göçün GEREKLİ olduğunu kanıtlar -- göç kaldırılırsa kırmızıya
    döner. `_migrate_fts_schema` doğrudan atlanarak eski davranış canlandırılır.
    """
    path = _legacy_db(tmp_path, preloaded=3)
    raw = sqlite3.connect(str(path))
    raw.execute("PRAGMA foreign_keys = ON")
    try:
        with pytest.raises(sqlite3.DatabaseError, match="malformed"):
            with raw:
                raw.execute("DELETE FROM documents WHERE filename = 'eski.pdf'")
    finally:
        raw.close()


def test_gocten_sonra_INDEKSLENMEMIS_belge_silinebiliyor(tmp_path):
    """Asıl hata buydu ve tam olarak burada ayrışıyor.

    Silinen belge, tetikleyiciler kurulmadan ÖNCE yazılmış -- yani FTS
    indeksinde hiç karşılığı yok. Eski `'delete'` komutu geri saracak bir
    şey bulamıyor ve `malformed` atıyor (üstteki test bunu gösteriyor).
    Göçten sonra indeks yeniden dolduğu için silme temiz geçiyor.

    Göç kaldırılırsa BU TEST KIRMIZIYA döner.
    """
    conn = store.connect(_legacy_db(tmp_path, preloaded=3))
    try:
        store.upsert_document(conn, "b.pdf", 1, _chunks("b", 2), [[0.4, 0.5, 0.6]] * 2)

        assert store.delete_document(conn, "eski.pdf") is True

        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 2
        # FTS chunks ile SENKRON: göç indeksi yeniden doldurdu, silme
        # tetikleyicisi de gerçekten düşürdü.
        assert conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == 2
    finally:
        conn.close()


def test_goc_idempotent(tmp_path):
    """Zaten yeni şemadaki bir veritabanına dokunulmaz."""
    path = tmp_path / "yeni.db"
    first = store.connect(path)
    store.upsert_document(first, "a.pdf", 1, _chunks("a", 2), [[0.1, 0.2, 0.3]] * 2)
    first.close()

    second = store.connect(path)
    try:
        assert second.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == 2
    finally:
        second.close()


def test_bm25_goc_sonrasi_GERCEKTEN_calisiyor(tmp_path):
    """Şema yorumundaki sessiz bozulma: external-content modda BM25 boş
    dönüyordu ve hibrit retrieval fark edilmeden dense-only'ye düşüyordu."""
    conn = store.connect(_legacy_db(tmp_path))
    try:
        store.upsert_document(
            conn, "a.pdf", 1,
            [SimpleNamespace(source="a.pdf", page=1,
                             content="embedding vektörleri sqlite icinde saklanir",
                             via_ocr=False)],
            [[0.1, 0.2, 0.3]],
        )
        assert store.bm25_candidates(conn, "sqlite", limit=5), "BM25 hiç aday dönmedi"
    finally:
        conn.close()
