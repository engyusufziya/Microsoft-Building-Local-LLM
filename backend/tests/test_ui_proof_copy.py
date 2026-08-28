"""eval/ui_proof.py::_copy_db -- kopyanın KAYNAKTAKİ bekleyen WAL'i de taşıdığı.

Ölçüm aracının kendisinin doğruluğunu test etme deseni test_offline_proof.py
ile aynı: "koşum temiz geçti" ile "koşum yanlış veriye bakıyordu" ayrımını
ancak böyle bir test yapabilir.

Gerçek olay (PROJE_DURUMU.md): shutil.copyfile yalnızca ana dosyayı
kopyaladığı için, kaynakta bekleyen WAL'deki silmeler kopyaya girmiyordu ve
arayüz kanıtı 8 belgelik BAYAT bir korpus ölçüyordu; gerçek korpus 1 belgeydi.

MODEL YÜKLEMEZ, tarayıcı AÇMAZ -- yalnızca yardımcı fonksiyon.
"""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
ui_proof = importlib.import_module("ui_proof")


def _source_with_pending_wal(path: Path) -> sqlite3.Connection:
    """WAL modunda bir veritabanı kurar ve checkpoint ALMADAN açık bırakır."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE belgeler (id INTEGER PRIMARY KEY, ad TEXT)")
    conn.executemany("INSERT INTO belgeler (ad) VALUES (?)", [("a",), ("b",), ("c",)])
    conn.commit()
    # Bu silme WAL'de bekler; ana dosyaya henüz yazılmamıştır.
    conn.execute("DELETE FROM belgeler WHERE ad IN ('b', 'c')")
    conn.commit()
    return conn


def test_copy_db_bekleyen_wali_de_tasir(tmp_path):
    source = tmp_path / "kaynak.db"
    conn = _source_with_pending_wal(source)
    try:
        assert (tmp_path / "kaynak.db-wal").exists(), "kurulum: WAL bekliyor olmalı"

        target_dir = tmp_path / "hedef"
        target_dir.mkdir()
        target = ui_proof._copy_db(source, target_dir)

        copied = sqlite3.connect(target)
        try:
            rows = copied.execute("SELECT ad FROM belgeler").fetchall()
        finally:
            copied.close()
    finally:
        conn.close()

    # WAL'deki silme kopyaya GİRMİŞ olmalı: 3 değil 1 satır.
    assert [r[0] for r in rows] == ["a"]


def test_copy_db_kaynaga_dokunmaz(tmp_path):
    """Kopyalama üretim veritabanını checkpoint'lemez, değiştirmez."""
    source = tmp_path / "kaynak.db"
    conn = _source_with_pending_wal(source)
    try:
        wal = tmp_path / "kaynak.db-wal"
        before = (source.read_bytes(), wal.read_bytes())

        target_dir = tmp_path / "hedef"
        target_dir.mkdir()
        ui_proof._copy_db(source, target_dir)

        assert (source.read_bytes(), wal.read_bytes()) == before
    finally:
        conn.close()


def test_copy_db_hedefteki_bayat_sidecar_silinir(tmp_path):
    """Birinci tuzak (zaten kayıtlıydı) hâlâ kapalı: hedefte kalmış bir WAL
    replay edilip silinmiş satırları geri getirmemeli."""
    source = tmp_path / "kaynak.db"
    conn = _source_with_pending_wal(source)
    try:
        target_dir = tmp_path / "hedef"
        target_dir.mkdir()
        stale = target_dir / "ui_proof.db-wal"
        stale.write_bytes(b"bayat")

        ui_proof._copy_db(source, target_dir)
        assert not stale.exists() or stale.read_bytes() != b"bayat"
    finally:
        conn.close()
