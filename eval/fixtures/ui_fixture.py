"""`ui_proof` için DETERMİNİSTİK veritabanı — istendiğinde üretilir.

NEDEN VAR: `ui_proof` eskiden kullanıcının gerçek `rag.db`'sini kopyalıyordu
ve kanıt, o veritabanı değiştikçe kırılıyordu. İki kez ÖLÇÜLDÜ:

  1. Kullanıcı bir zihin haritası üretti; artefakt listesinin başı değişti ve
     "listenin ilki aradığım rapordur" varsayan bölüm YANLIŞ artefaktı ölçmeye
     başladı.
  2. Kullanıcı PDF'i yeniden yükledi; "kaynağı saklanmamış belge 404 verir"
     kolu, öyle bir belge kalmadığı için düştü.

Her kırılış 3-4 dakikalık bir tarayıcı koşumu yakıyor ve hata mesajı insanı
kodun yanlış yerine götürüyor. Sabit fixture bu bağı koparır.

Depoya İŞLENMEZ, `eval/eval.db` ile aynı desen: `.gitignore`'da, ilk
koşumda üretilir. İkili dosya git'e girmez, üretimi burada okunur.

KAPSADIĞI DURUMLAR (hepsi kasıtlı):
  - kaynak PDF'i SAKLANMIŞ belge  -> sayfa görüntüsü ucu gerçekten render eder
  - kaynak PDF'i SAKLANMAMIŞ belge -> §13.4'ün geriye dönük sınırı; bu kol
    gerçek rag.db ile artık kurulamıyordu ve kanıtta ATLANIYORDU
  - iddiaları CANLI chunk'lara bağlı bir rapor artefaktı -> atıf üst
    simgelerinin gerçekten basıldığı POZİTİF durum
"""

from __future__ import annotations

import io
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from rag import store  # noqa: E402
from rag.artifacts import store as artifact_store  # noqa: E402
from rag.artifacts.fidelity import ClaimBinding  # noqa: E402

EMBED_DIM = 1024  # qwen3-embedding-0.6b; ui_proof'un sahte vektörüyle aynı

WITH_PDF = "kilavuz.pdf"
WITHOUT_PDF = "eski_notlar.pdf"

_WITH_PDF_CHUNKS = [
    ("RAG üç adımdan oluşur: retrieval, augmentation ve generation.", 1),
    ("Retrieval adımında soruyla ilgili metin parçaları veritabanından bulunur.", 1),
    ("Augmentation adımında bulunan parçalar modelin girdisine eklenir.", 2),
    ("Generation adımında model bağlamı kullanarak cevabı üretir.", 3),
]

_WITHOUT_PDF_CHUNKS = [
    ("Bu belge sayfa görüntüsü özelliğinden önce yüklendi.", 1),
    ("Kaynağı saklanmadığı için sayfa görüntüsü isteği 404 döner.", 2),
]


def _embedding(index: int) -> list[float]:
    """Deterministik, birbirinden ayrık vektörler.

    İlk bileşen kasıtlı olarak azalan: `ui_proof` sorgu vektörünü
    `[1, 0, 0, ...]` yaptığı için cosine sıralaması bu bileşenden çıkar ve
    hangi chunk'ın önce geleceği ÖNCEDEN BİLİNİR. Rastgelelik yok.
    """
    vector = [0.0] * EMBED_DIM
    vector[0] = 1.0 - index * 0.05
    vector[1 + index] = 0.3
    return vector


def pdf_bytes(pages: int) -> bytes:
    """METİN TAŞIYAN minimal bir PDF üretir — depoya ikili dosya eklemeden.

    DIŞA AÇIK: `ui_proof` ve `offline_proof` de bunu kullanır. Eskiden ikisi
    de depo kökündeki `Foundry_Local_Plan.pdf`'i okuyordu -- o dosya
    `.gitignore`'da, yani geliştiricinin kendi belgesi. CI'da yoktu ve
    `ui_proof`'un yükleme adımı orada düştü ("yerelde çalışıyordu"nun ikinci
    ölçülmüş örneği).

    Neden `pypdfium2.new_page()` DEĞİL: o boş sayfa üretiyor, `pdf_loader`
    hiç metin bulamıyor ve ingest `NO_CONTENT` ile düşüyor (ölçüldü). Yükleme
    yolunun gerçekten çalıştığını göstermek için sayfaların metni olmalı.

    PDF elle kuruluyor: yeni bir bağımlılık (reportlab vb.) eklemek, tek
    kullanımlık bir yardımcı için ürün dışı bir paket demek olurdu.
    """
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: list[int] = []
    content_ids: list[int] = []
    for index in range(pages):
        lines = [
            f"Sayfa {index + 1} - yerel RAG asistani kanit belgesi.",
            "Bu sayfa ui_proof ve offline_proof icin uretildi.",
            f"Belge {pages} sayfadan olusuyor ve her sayfada metin var.",
        ]
        stream = "BT /F1 12 Tf 60 760 Td 16 TL\n"
        stream += "".join(f"({line}) Tj T*\n" for line in lines)
        stream += "ET"
        encoded = stream.encode("latin-1")
        content_ids.append(
            add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(encoded), encoded))
        )
        page_ids.append(0)  # yer tutucu; Pages nesnesi kurulduktan sonra dolar

    pages_obj = len(objects) + pages + 1
    for index in range(pages):
        page_ids[index] = add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_obj, font, content_ids[index])
        )
    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, pages))
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, catalog, xref_at
    )
    return bytes(out)


def _chunks(filename: str, rows: list[tuple[str, int]]):
    return [
        SimpleNamespace(source=filename, page=page, content=content, via_ocr=False)
        for content, page in rows
    ]


def build(path: Path) -> Path:
    """Fixture'ı SIFIRDAN kurar. Varsa siler: koşumlar birikmemeli."""
    path = Path(path)
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = store.connect(path)
    try:
        store.upsert_document(
            conn, WITH_PDF, page_count=3,
            chunks=_chunks(WITH_PDF, _WITH_PDF_CHUNKS),
            embeddings=[_embedding(i) for i in range(len(_WITH_PDF_CHUNKS))],
            pdf_bytes=pdf_bytes(3),
        )
        store.upsert_document(
            conn, WITHOUT_PDF, page_count=2,
            chunks=_chunks(WITHOUT_PDF, _WITHOUT_PDF_CHUNKS),
            embeddings=[
                _embedding(len(_WITH_PDF_CHUNKS) + i)
                for i in range(len(_WITHOUT_PDF_CHUNKS))
            ],
            pdf_bytes=None,  # kasıtlı: §13.4 geriye dönük sınırı
        )
        _create_report(conn)
    finally:
        conn.close()
    return path


def _create_report(conn: sqlite3.Connection) -> None:
    """Rapor artefaktı: iddiaları CANLI chunk'lara bağlı.

    Payload'ın `citations` listesi ile iddiaların `chunk_id`'leri BİLEREK
    örtüşür -- atıf üst simgesi ancak iki koşul birden sağlanınca basılıyor
    (report-view.tsx). Gerçek `rag.db`'de bu örtüşme yoktu ve kanıt
    "0 üst simge = 0 beklenen" ölçüyordu; yani hiçbir şey kanıtlamıyordu.
    """
    rows = conn.execute(
        "SELECT c.id, c.source, c.page, c.content FROM chunks c "
        "JOIN documents d ON d.id = c.document_id WHERE d.filename = ? "
        "ORDER BY c.id",
        (WITH_PDF,),
    ).fetchall()

    sentences = [row["content"] for row in rows]
    payload = {
        "kind": "report",
        "outline": ["executive_summary", "key_findings"],
        "sections": [
            {
                "id": "executive_summary",
                "title": "Yönetici Özeti",
                "context_chunk_ids": [row["id"] for row in rows[:2]],
                "paragraphs": [{"sentences": sentences[:2]}],
            },
            {
                "id": "key_findings",
                "title": "Bulgular",
                "context_chunk_ids": [row["id"] for row in rows[2:]],
                "paragraphs": [{"sentences": sentences[2:]}],
            },
        ],
        "tables": [],
        "citations": [
            {
                "chunk_id": row["id"],
                "source": row["source"],
                "page": row["page"],
                "citation": f"[Kaynak: {row['source']} s.{row['page']}]",
            }
            for row in rows
        ],
        "dropped": [
            {
                "node_path": "/dropped/0",
                "text": "Bu sistem GPT-4 kullanır ve verileri buluta gönderir.",
                "reason": "unsupported",
                "score": 0.2814,
                "terms": ["gpt-4"],
            }
        ],
    }

    claims = [
        ClaimBinding(
            node_path=f"/sections/{section}/paragraphs/0/sentences/{index}",
            claim_text=sentences[section * 2 + index],
            chunk_id=rows[section * 2 + index]["id"],
            score=0.72 - index * 0.03,
            verdict="grounded",
        )
        for section in (0, 1)
        for index in (0, 1)
    ]
    claims.append(
        ClaimBinding("/dropped/0", payload["dropped"][0]["text"], None, 0.2814, "unsupported")
    )

    artifact_store.create_artifact(
        conn,
        kind="report",
        scope="corpus",
        document_id=None,
        title="Korpus Raporu",
        params={"scope": "corpus"},
        payload=payload,
        corpus_fingerprint=store.corpus_fingerprint(conn),
        fidelity_score=1.0,
        generation_ms=4200,
        claims=claims,
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "ui.db"
    print(f"kuruldu: {build(target)}")
