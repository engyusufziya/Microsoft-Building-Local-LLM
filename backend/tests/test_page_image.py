"""`GET /api/documents/{filename}/pages/{page}/image` — sayfa görüntülü alıntı.

FEATURE_SPEC §13.4. Uç ADDITIVE'dir: mevcut yedi uca ve §9.7 studio uçlarına
dokunmaz, §2.2 hata listesine yeni kod açmaz (yalnızca 404 kullanır).

Depolama kararı ölçümle (ii) seçildi: kaynak PDF saklanır, sayfa İSTEK ANINDA
rasterlenir. Bu testler o sözleşmenin üç kenarını tutar — mutlu yol, kaynağı
saklanmamış belge, ve aralık dışı sayfa.
"""

from __future__ import annotations

from types import SimpleNamespace

import pypdfium2 as pdfium

from rag import config, store


def _pdf_bytes(pages: int = 3) -> bytes:
    """Testin kendi PDF'ini üretir — depoya ikili fixture eklemeden."""
    document = pdfium.PdfDocument.new()
    for _ in range(pages):
        document.new_page(200, 280)
    import io

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _seed(conn, filename: str, *, pdf: bytes | None) -> None:
    chunk = SimpleNamespace(source=filename, page=1, content="içerik", via_ocr=False)
    store.upsert_document(
        conn, filename, page_count=3, chunks=[chunk], embeddings=[[0.1, 0.2, 0.3]],
        pdf_bytes=pdf,
    )


def test_sayfa_goruntusu_dondurulur(app, client):
    _seed(app.state.conn, "belge.pdf", pdf=_pdf_bytes())

    r = client.get("/api/documents/belge.pdf/pages/2/image")

    assert r.status_code == 200
    assert r.headers["content-type"] == f"image/{config.PAGE_IMAGE_FORMAT.lower()}"
    # RIFF....WEBP — gerçekten görüntü döndüğü baytlardan doğrulanır.
    assert r.content[:4] == b"RIFF" and r.content[8:12] == b"WEBP"


def test_kaynagi_saklanmamis_belge_404(app, client):
    """§13.4 geriye dönük veri sınırı: değişiklikten önce yüklenmiş belgeler.

    Sahte görüntü ÜRETİLMEZ; 404 doğru cevaptır.
    """
    _seed(app.state.conn, "eski.pdf", pdf=None)

    r = client.get("/api/documents/eski.pdf/pages/1/image")

    assert r.status_code == 404
    assert r.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_olmayan_belge_404(client):
    r = client.get("/api/documents/yok.pdf/pages/1/image")
    assert r.status_code == 404
    assert r.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_aralik_disi_sayfa_404(app, client):
    """Aralık dışı sayfa da `DOCUMENT_NOT_FOUND` döner — YENİ KOD AÇILMAZ.

    §13.4 hata listesini additive tutmayı şart koşuyor. Ayrı bir
    `PAGE_NOT_FOUND` gerekçesiz olurdu: alıntı zaten o belgenin bir
    chunk'ından geliyor, yani normal akışta aralık dışı sayfa ulaşılamaz bir
    savunma dalı ve arayüz iki durumu da aynı şekilde ele alıyor (görüntü yok).
    """
    _seed(app.state.conn, "belge.pdf", pdf=_pdf_bytes(pages=3))

    r = client.get("/api/documents/belge.pdf/pages/9/image")

    assert r.status_code == 404
    assert r.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_belge_silinince_kaynak_pdf_de_gider(app, client):
    """CASCADE: document_files.document_id -> documents(id) ON DELETE CASCADE."""
    conn = app.state.conn
    _seed(conn, "gidecek.pdf", pdf=_pdf_bytes())
    assert store.load_pdf(conn, "gidecek.pdf") is not None

    assert client.delete("/api/documents/gidecek.pdf").status_code == 200

    assert store.load_pdf(conn, "gidecek.pdf") is None
    assert (
        conn.execute("SELECT COUNT(*) FROM document_files").fetchone()[0] == 0
    )


def test_liste_sayfa_goruntusu_tasiyip_tasimadigini_bildirir(app, client):
    """`has_page_images` — arayüz 404 üretmeden bilsin diye (§13.4).

    Ölçüldü: alan olmadan tarayıcı her alıntıda 404'ü konsola hata yazıyordu.
    """
    conn = app.state.conn
    _seed(conn, "kaynakli.pdf", pdf=_pdf_bytes())
    _seed(conn, "kaynaksiz.pdf", pdf=None)

    by_name = {d["filename"]: d for d in client.get("/api/documents").json()}

    assert by_name["kaynakli.pdf"]["has_page_images"] is True
    assert by_name["kaynaksiz.pdf"]["has_page_images"] is False
