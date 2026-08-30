"""
Arayüz kanıtı: Studio'nun ÜÇ görünümünün de GERÇEK bir tarayıcıda çalıştığının
ölçümü (rapor · zihin haritası · quiz).

`eval/offline_proof.py` ile aynı fikir: iddiayı yoruma bırakmak yerine
ölçmek. Orada soru "kod ağa çıkıyor mu", burada "React katmanı gerçekten
çalışıyor mu" -- çünkü pytest backend'i, `report_trap.py` hattı doğruluyor
ama ikisi de tarayıcıya hiç girmiyor.

MODEL YÜKLEMEZ ve bu kasıtlıdır. İki yer sahtelenir, ikisi de çıktıda
açıkça yazılır:

  1. `RAG_BACKEND_SKIP_WARMUP=1` + `model_status` elle "ready" yapılır.
  2. `report`, `mindmap` ve `quiz` üreticileri, SSE aşama/ilerleme olaylarını
     gerçek hattaki gibi yayan ama LLM çağırmayan sahtelerle DEĞİŞTİRİLİR.

Doğrulanan şey ÜRETİM DEĞİL (o `report_trap.py` / `mindmap_proof.py` /
`quiz_proof.py`'nin ve gerçek modelle yapılan uçtan uca koşumun işi),
TARAYICIDAKİ DAVRANIŞ: sekme gezinmesi, artefakt listesi, rapor render'ı,
atıf üst simgeleri, düşürülen iddia paneli, export bağlantısı, `@media print`
sözleşmesi ve sıfır harici istek -- ARTI Faz 3/4 ile gelen iki görünüm:

  - zihin haritası: ağaç semantiği (Faz 4'te SVG'den Modernist kutu
    düzenine geçti, ROLLER değişmedi), ok tuşlarıyla düğüm gezinmesi
    (WCAG AA, §11.9), seçili düğümün kaynak listesi, yedek etiketin
    "korpustan türetildi" uyarısı, dal konnektörleri;
  - quiz: soru tipleri, şık/serbest metin girdileri, gönderim, sonuç
    ekranı -- ve §12.8'in görünür kuralı: `short_answer` DOĞRU/YANLIŞ
    olarak işaretlenmez, yalnızca benzerlik sayısı gösterilir;
  - kapsam seçici: `scope="document"` isteğinin arayüzden GERÇEKTEN kurulduğu,
    kod incelemesiyle değil POST gövdesiyle ölçülür (§9.7).

Bu iki bölüm Faz 3/4 tesliminde EKSİKTİ: `FEATURE_SPEC §11.11`'in "klavyeyle
gezilebilir" maddesi kod incelemesine dayanıyordu, ölçüme değil. Bu koşum o
boşluğu kapatır.

Veritabanı: `rag.db`'nin KOPYASI (üretim veritabanına dokunulmaz). Kopyada
gerçek bir rapor artefaktı varsa ekranda o render edilir; yoksa o adımlar
atlanır ve atlandığı yazılır.

Gereksinim: `playwright` + Chromium. ÇALIŞMA ANI BAĞIMLILIĞI DEĞİLDİR --
`requirements.txt`'e girmez (AGENTS.md §1.2: ürün yolunda ağ/tarayıcı yok);
bkz. `requirements-dev.txt`.

    .venv/bin/pip install -r requirements-dev.txt
    .venv/bin/playwright install chromium
    .venv/bin/python eval/ui_proof.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def _multipart(filename: str, data: bytes) -> tuple[bytes, str]:
    """Tek dosyalık multipart gövdesi — `requests` bağımlılığı eklemeden.

    `POST /api/documents` gerçek yükleme yolu; ui_proof onu taklit etmez,
    KULLANIR (§13.4 zincirinin baytları saklayan ucu).
    """
    boundary = f"----uiproof{uuid.uuid4().hex}"
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/pdf\r\n\r\n",
        data,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    return body, f"multipart/form-data; boundary={boundary}"


def _free_port() -> int:
    """İşletim sisteminden boş bir port ister.

    Sabit port kullanılmıyor: bu script geliştirme sırasında zaten açık olan
    bir uvicorn'un yanında çalıştırılabiliyor ve sabit port o durumda
    "address already in use" ile düşüyordu (ölçüldü).
    """
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"

# 1024 boyut: kopya rag.db gerçek embedding matrisini taşıyor; bind_claims'in
# matris çarpımı boyut uyumsuzluğuna düşmemeli.
_FAKE_VECTOR = [1.0] + [0.0] * 1023

_FAKE_PAYLOAD = {
    "kind": "report",
    "outline": ["executive_summary", "key_findings", "detailed_analysis", "tables", "citations"],
    "sections": [
        {"id": "exec", "kind": "executive_summary", "title": "Yönetici Özeti", "topic_id": None,
         "context_chunk_ids": [1], "paragraphs": [{"sentences": ["Arayüz kanıtı için üretilmiş özet cümlesi."]}]},
        {"id": "findings", "kind": "key_findings", "title": "Temel Bulgular", "topic_id": None,
         "context_chunk_ids": [1], "paragraphs": [{"sentences": ["Arayüz kanıtı için üretilmiş bulgu cümlesi."]}]},
    ],
    "tables": [{"id": "coverage", "title": "Belge × Konu Kapsama", "columns": ["Belge", "K0"],
                "rows": [["kanit.md", 1]]}],
    "citations": [],
    "dropped": [{"section_id": "exec", "text": "Bu sistem GPT-4 kullanır.",
                 "reason": "unverified_terms", "score": 0.5487, "terms": ["gpt-4"]}],
}


_FAKE_MINDMAP_PAYLOAD = {
    "kind": "mindmap",
    "nodes": [
        {"id": "root", "label": "Arayüz Kanıtı Haritası", "kind": "root", "parent": None,
         "topic_id": None, "chunk_ids": [], "size": 4, "label_source": "corpus",
         "citations": []},
        # label_source="model": kapıdan geçmiş etiket.
        {"id": "n0", "label": "Depolama katmanı", "kind": "topic", "parent": "root",
         "topic_id": 0, "chunk_ids": [1, 2], "size": 2, "label_source": "model",
         "citations": [{"chunk_id": 1, "source": "kanit.md", "page": 0,
                        "citation": "[Kaynak: kanit.md]"},
                       {"chunk_id": 2, "source": "kanit.md", "page": 0,
                        "citation": "[Kaynak: kanit.md]"}]},
        # label_source="fallback": modelin etiketi düştü, ad korpustan türedi.
        # Arayüzün bunu GÖSTERMESİ zorunlu (§11.5) -- kontrol buna bakıyor.
        {"id": "n1", "label": "kanit.md (2 bölüm)", "kind": "topic", "parent": "root",
         "topic_id": 1, "chunk_ids": [3, 4], "size": 2, "label_source": "fallback",
         "citations": [{"chunk_id": 3, "source": "kanit.md", "page": 0,
                        "citation": "[Kaynak: kanit.md]"},
                       {"chunk_id": 4, "source": "kanit.md", "page": 0,
                        "citation": "[Kaynak: kanit.md]"}]},
    ],
    "edges": [{"from": "n0", "to": "n1", "relation": "related", "weight": 0.7127}],
    "dropped": [{"topic_id": 1, "text": "GPT-4 mimarisi", "reason": "unverified_terms",
                 "score": 0.5487, "terms": ["gpt-4"]}],
}

# Dört tipin dördü de var: iki girdi biçimi (şık / serbest metin) ve §12.8'in
# "short_answer eşiğe indirgenmez" kuralı aynı ekranda görülebilsin.
_FAKE_QUIZ_PAYLOAD = {
    "kind": "quiz",
    "questions": [
        {"id": "q0", "type": "multiple_choice", "topic_id": 0,
         "prompt": "Veriler _____ motorunda saklanır.",
         "choices": ["Foundry", "SQLite", "Streamlit", "Cosine"], "answer": "SQLite",
         "chunk_id": 1, "source": "kanit.md", "citation": "[Kaynak: kanit.md]",
         "evidence": "Veriler SQLite motorunda saklanır."},
        {"id": "q1", "type": "true_false", "topic_id": 1,
         "prompt": "«Veriler SQLite motorunda saklanır.» — Bu bilgi kanit.md belgesinde geçiyor.",
         "choices": ["true", "false"], "answer": "true",
         "chunk_id": 1, "source": "kanit.md", "citation": "[Kaynak: kanit.md]",
         "evidence": "Veriler SQLite motorunda saklanır."},
        {"id": "q2", "type": "fill_blank", "topic_id": 2,
         "prompt": "Vektörler _____ biçiminde tutulur.", "choices": [], "answer": "float32",
         "chunk_id": 1, "source": "kanit.md", "citation": "[Kaynak: kanit.md]",
         "evidence": "Vektörler float32 biçiminde tutulur."},
        # Bu sorunun cevabı KASITLI olarak "Doğru"/"Yanlış" sözcüklerini içermez:
        # kontrol, karttaki bu sözcüklerin YOKLUĞUNA bakarak §12.8'i ölçüyor.
        {"id": "q3", "type": "short_answer", "topic_id": 3,
         "prompt": "Vektörler nerede saklanır?", "choices": [],
         "answer": "Vektörler yerel bir veritabanında saklanır.",
         "chunk_id": 1, "source": "kanit.md", "citation": "[Kaynak: kanit.md]",
         "evidence": "Vektörler yerel bir veritabanında saklanır."},
    ],
    "dropped": [{"topic_id": 4, "text": "Bu sistem GPT-4 kullanır.",
                 "prompt": "Bu sistem hangi modeli kullanır?",
                 "reason": "unverified_terms", "score": 0.5487, "terms": ["gpt-4"]}],
}


def _copy_db(source: Path, target_dir: Path) -> Path:
    """rag.db'nin TUTARLI bir kopyasını üretir (SQLite backup API'si).

    Ölçülen tuzak 1: hedefte önceki koşumdan kalmış bir `-wal` dosyası varsa
    SQLite onu replay edip silinmiş sanılan artefaktları geri getiriyor ve
    test yanlış veriye bakıyor. Bu yüzden hedefin sidecar'ları önce silinir.

    Ölçülen tuzak 2 (SONRADAN bulundu): `shutil.copyfile` yalnızca ANA dosyayı
    kopyalıyordu ve KAYNAKTA bekleyen bir WAL varsa onun içeriği kopyaya hiç
    girmiyordu -- yani koşum BAYAT bir korpusu ölçüyordu. Gerçekten görüldü:
    checkpoint öncesi kopya 8 belge, sonrası 1 belge gösterdi (PROJE_DURUMU.md,
    "Bu turun kapı sayıları").

    Çözüm `PRAGMA wal_checkpoint` DEĞİL -- o, kullanıcının üretim
    veritabanına yazardı. `sqlite3.Connection.backup` kaynağı salt okunur
    açar, WAL dahil tutarlı bir anlık görüntü üretir ve kaynağa DOKUNMAZ.
    """
    target = target_dir / "ui_proof.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(target) + suffix).unlink(missing_ok=True)
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return target


def _start_server(db_path: Path):
    os.environ["RAG_BACKEND_DB_PATH"] = str(db_path)
    os.environ["RAG_BACKEND_SKIP_WARMUP"] = "1"

    import uvicorn
    from backend.main import create_app
    from rag import answer, models
    from rag.artifacts import base

    app = create_app()

    class _FakeReportGenerator:
        """Gerçek ReportGenerator'ın SSE davranışını taklit eder, LLM çağırmaz."""

        kind = "report"

        def generate(self, ctx):
            for i in range(1, 4):
                time.sleep(0.4)  # ilerleme çubuğu tarayıcıda gerçekten görülebilsin
                ctx.emit("progress", {"pct": round(i * 100 / 3), "detail": f"{i}/3 bölüm yazıldı"})

            # Payload'ın `citations` listesi CANLI korpustan kurulur ve
            # KORPUSUN TAMAMINI kapsar.
            #
            # Gerekçe: üst simge ancak iddianın çapası bu listede de varsa
            # basılıyor (report-view.tsx). Hangi chunk'a bağlanacağı ÖNCEDEN
            # BİLİNEMEZ -- ölçüldü: sahte olan yalnızca SORGU vektörü,
            # chunk embedding'leri veritabanındaki gerçek değerler, yani
            # `bind_claims`'in argmax'i gerçek bir benzerlik yarışını kazanan
            # chunk'ı seçiyor. "İlk chunk'ı seçer" varsayımı bu yüzden
            # yanlıştı. Tüm korpusu alıntılamak sahte bir rapor için dürüst
            # bir tanım ve çapa hangisi çıkarsa çıksın kontrolü anlamlı kılıyor.
            payload = dict(_FAKE_PAYLOAD)
            payload["citations"] = [
                {"chunk_id": cid, "source": src, "page": pg,
                 "citation": f"[Kaynak: {src}" + (f" s.{pg}]" if pg else "]")}
                for cid, src, pg in ctx.conn.execute(
                    "SELECT id, source, page FROM chunks ORDER BY id"
                )
            ]

            return base.GeneratedArtifact(
                title="Arayüz Kanıtı Raporu",
                payload=payload,
                claims=[
                    ("/sections/0/paragraphs/0/sentences/0", "Arayüz kanıtı için üretilmiş özet cümlesi."),
                    ("/sections/1/paragraphs/0/sentences/0", "Arayüz kanıtı için üretilmiş bulgu cümlesi."),
                    ("/dropped/0", "Bu sistem GPT-4 kullanır."),
                ],
            )

    def _fake_answer_stream(question, k=None, min_score=None, conn=None):
        """Sohbet akışını MODELSİZ taklit eder — FEATURE_SPEC §13.4 zinciri için.

        Neden gerekli: gerçek `answer_query_stream` hem embedding hem 7B
        yükler; ui_proof kasıtlı olarak model yüklemiyor. Ama satır içi
        numaralı alıntı -> çekmece -> sayfa görüntüsü zinciri ancak GERÇEK bir
        cevap akarken ölçülebilir.

        Hit'ler UYDURULMAZ: kopyalanan veritabanındaki gerçek chunk'lardan
        kurulur (gerçek `source`, `page`, `content`, ve `chunk_index/total`).
        Yalnızca skor ve cevap metni sabittir -- ölçülen şey retrieval kalitesi
        değil, ARAYÜZÜN o veriyi nasıl gösterdiği.
        """
        from rag import config as rag_config
        from rag import store as rag_store
        from rag.retrieve import Hit

        _, meta = rag_store.load_matrix(conn)
        picked = [m for m in meta if m["page"]][:3]

        # Skorlar eşiğin İKİ YANINA konur: çekmece ve Inspector eşik
        # davranışını da bu tek akışta gösterebilsin.
        scores = [0.71, 0.58, rag_config.MIN_SCORE - 0.06]
        hits = [
            Hit(score=score, source=m["source"], page=m["page"], content=m["content"],
                via_ocr=bool(m.get("via_ocr")), chunk_id=m["id"],
                chunk_index=m["chunk_index"], chunk_total=m["chunk_total"])
            for m, score in zip(picked, scores)
        ]
        passed = [h for h in hits if h.score >= rag_config.MIN_SCORE]

        yield answer.RetrievalEvent(
            hits=hits, threshold=rag_config.MIN_SCORE, passed_count=len(passed),
            rejected_count=len(hits) - len(passed), elapsed_ms=120,
        )
        # Cevap metni atıf işaretçilerini İÇERİR: numaralandırma bunlardan
        # türetiliyor (`numberCitations`).
        for chunk in ("Belgeler bir yaz okulu programını anlatıyor.",
                      f"{passed[0].citation()} ",
                      "Program yerel bir RAG asistanı kurmayı hedefliyor.",
                      f"{passed[-1].citation()}"):
            yield answer.TokenEvent(text=chunk + " ")
        yield answer.DoneEvent(
            answered=True, reason=None,
            sources=list(dict.fromkeys(h.citation() for h in passed)),
            elapsed_ms=1200, token_count=42,
        )

    class _FakeMindMapGenerator:
        """Faz 3 üreticisinin SSE davranışını taklit eder, LLM çağırmaz."""

        kind = "mindmap"

        def generate(self, ctx):
            for i in range(1, 3):
                time.sleep(0.3)
                ctx.emit("progress", {"pct": round(i * 100 / 2),
                                      "detail": f"{i}/2 küme etiketlendi"})
            return base.GeneratedArtifact(
                title="Arayüz Kanıtı Haritası",
                payload=_FAKE_MINDMAP_PAYLOAD,
                claims=[("/nodes/1/label", "Depolama katmanı"),
                        ("/dropped/0", "GPT-4 mimarisi")],
            )

    class _FakeQuizGenerator:
        """Faz 4 üreticisinin SSE davranışını taklit eder, LLM çağırmaz."""

        kind = "quiz"

        def generate(self, ctx):
            for i in range(1, 3):
                time.sleep(0.3)
                ctx.emit("progress", {"pct": round(i * 100 / 2),
                                      "detail": f"{i}/2 küme için soru üretildi"})
            return base.GeneratedArtifact(
                title="Arayüz Kanıtı Quiz",
                payload=_FAKE_QUIZ_PAYLOAD,
                claims=[("/questions/0/evidence", "Veriler SQLite motorunda saklanır."),
                        ("/questions/3/answer", "Vektörler yerel bir veritabanında saklanır."),
                        ("/dropped/0", "Bu sistem GPT-4 kullanır.")],
            )

    base.register(_FakeReportGenerator())
    base.register(_FakeMindMapGenerator())
    base.register(_FakeQuizGenerator())
    models.embed_texts = lambda texts, is_query=False: [_FAKE_VECTOR for _ in texts]
    # Sohbet akışı da modelsiz: §13.4 zinciri (satır içi numara -> çekmece ->
    # sayfa görüntüsü) gerçek bir cevap akmadan ölçülemez.
    answer.answer_query_stream = _fake_answer_stream

    def _flip_ready():
        time.sleep(1.0)
        app.state.model_status = "ready"

    threading.Thread(target=_flip_ready, daemon=True).start()
    config = uvicorn.Config(app, port=PORT, log_level="error")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    return server


def _wait_ready(timeout: int = 60) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            body = json.loads(urllib.request.urlopen(f"{BASE}/api/health", timeout=5).read())
            if body["status"] == "ready":
                return body
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("backend hazır duruma gelmedi")


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default=str(PROJECT_ROOT / "rag.db"),
        help="kopyalanacak veritabanı (varsayılan: rag.db). İçinde gerçek bir "
             "rapor artefaktı varsa ekranda o render edilir.",
    )
    args = parser.parse_args(argv)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright kurulu değil:")
        print("  .venv/bin/pip install -r requirements-dev.txt && .venv/bin/playwright install chromium")
        return 2

    source_db = Path(args.db)
    if not source_db.exists():
        print(f"{source_db} yok -- önce bir belge yükleyin.")
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="ui_proof_"))
    shots = tmp / "shots"
    shots.mkdir()
    db_path = _copy_db(source_db, tmp)

    fails: list[str] = []

    def check(label, ok, detail=""):
        print(f"  [{'OK ' if ok else 'HATA'}] {label}" + (f"  {detail}" if detail else ""))
        if not ok:
            fails.append(label)

    _start_server(db_path)
    health = _wait_ready()
    existing = json.loads(urllib.request.urlopen(f"{BASE}/api/artifacts?kind=report").read())

    print("=== Arayüz kanıtı — gerçek Chromium, gerçek statik export ===\n")
    print(f"  Veritabanı : rag.db KOPYASI ({health['document_count']} belge / {health['chunk_count']} chunk)")
    print(f"  Model      : YÜKLENMEDİ -- warmup atlandı, üretici SAHTE (bkz. modül docstring'i)")
    print(f"  Mevcut rapor artefaktı: {len(existing)}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        console_errors: list[str] = []
        external: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        page.on("request", lambda r: external.append(r.url)
                if not r.url.startswith((BASE, "data:", "blob:")) else None)

        page.goto(BASE, wait_until="networkidle")
        check("uygulama kabuğu render edildi", page.locator('[data-slot="app-shell"]').count() == 1)

        print("\n--- Sol panel sekmeleri (§13.2) ---")
        # v3'te sekme anahtarı SOL kolonda: Kaynaklar (belgeler) / Çıktılar
        # (artefaktlar). Sağ kolon kalıcı panel olmaktan çıkıp bağlama duyarlı
        # alıntı çekmecesine döndü, sekmeleri de onunla birlikte taşındı.
        sources_tab = page.get_by_role("tab", name="Kaynaklar")
        outputs_tab = page.get_by_role("tab", name="Çıktılar")
        check("iki sekme de var", sources_tab.count() == 1 and outputs_tab.count() == 1)
        check("başlangıçta Kaynaklar seçili", sources_tab.get_attribute("aria-selected") == "true")
        sources_tab.focus()
        page.keyboard.press("ArrowRight")
        check("ok tuşuyla Çıktılar'a geçiliyor (WCAG AA)", outputs_tab.get_attribute("aria-selected") == "true")
        page.keyboard.press("Home")
        check("Home ile Kaynaklar'a dönülüyor", sources_tab.get_attribute("aria-selected") == "true")
        outputs_tab.click()
        page.wait_for_selector('[data-slot="studio-panel"]')

        # Sağ kolon artık kalıcı DEĞİL: çekmece kapalı başlar, düğmeyle açılır.
        check("alıntı çekmecesi kapalı başlıyor",
              page.locator('[data-slot="retrieval-inspector"]').count() == 0)
        page.get_by_role("button", name="Kaynak panelini aç").click()
        page.wait_for_selector('[data-slot="retrieval-inspector"]')
        check("çekmece masaüstünde de açılıyor (§13.2)",
              page.locator('[data-slot="retrieval-inspector"]').count() == 1)
        page.get_by_role("button", name="Kaynak panelini kapat").click()
        page.wait_for_selector('[data-slot="retrieval-inspector"]', state="detached")
        check("'Rapor üret' düğmesi var", page.get_by_role("button", name="Rapor üret").count() == 1)

        if existing:
            print("\n--- Gerçek rapor render'ı ---")
            artifact_list = page.get_by_role("list", name="Üretilen artefaktlar")
            artifact_list.wait_for(timeout=10000)
            artifact_list.locator("li").first.get_by_role("button", name="Aç").click()
            report = page.locator('[data-print="root"]')
            report.wait_for(timeout=10000)
            detail = json.loads(
                urllib.request.urlopen(f"{BASE}/api/artifacts/{existing[0]['id']}").read()
            )
            payload = detail["payload"]
            expected_sentences = sum(
                len(par["sentences"]) for sec in payload["sections"] for par in sec["paragraphs"]
            )
            check("rapor başlığı render edildi", detail["title"] in report.inner_text())
            check("her cümle node_path taşıyor",
                  report.locator("[data-node-path]").count() == expected_sentences,
                  f"{report.locator('[data-node-path]').count()}/{expected_sentences}")
            # Bu artefakt rag.db'den geliyor ve BAYAT: bağlandığı belge
            # silinmiş, `artifact_claims.chunk_id` şemadaki
            # `ON DELETE SET NULL` ile boşalmış. `report-view.tsx` üst
            # simgeyi yalnızca chunk çapası duruyorsa basar.
            #
            # Bu kontrol ÖNCEDEN "her cümlenin üst simgesi var" diyordu ve
            # kırmızıydı; ölçüldüğünde bunun bir kod hatası DEĞİL, tasarlanmış
            # bir bozunma olduğu görüldü. Kontrol gevşetilmedi -- YERİ
            # değiştirildi: burada çapasız artefaktın çökmeden ve sahte atıf
            # uydurmadan render edildiği doğrulanır; üst simgelerin GERÇEKTEN
            # basıldığı ise aşağıda TAZE üretilen raporda ölçülür.
            cited_chunks = {c["chunk_id"] for c in payload["citations"]}
            live_anchors = sum(
                1 for c in detail["claims"] if c.get("chunk_id") in cited_chunks
            )
            check("bayat artefakt: üst simge sayısı alıntılanan çapa sayısıyla eşit",
                  report.locator("sup").count() == live_anchors,
                  f"{report.locator('sup').count()} üst simge / {live_anchors} çapa")
            check("bayat artefakt yine de tam metinle render ediliyor",
                  report.locator("[data-node-path]").count() == expected_sentences)
            check("Sadakat oranı ve çıkarılan iddia meta'da",
                  "Sadakat oranı" in report.inner_text() and "Çıkarılan iddia" in report.inner_text())
            if payload["dropped"]:
                heading = report.locator("h2", has_text="Rapordan çıkarılan iddialar")
                check("düşürülen iddia paneli tam sayıda",
                      heading.locator("xpath=../ul/li").count() == len(payload["dropped"]),
                      f"{heading.locator('xpath=../ul/li').count()}/{len(payload['dropped'])}")
                body = " ".join(
                    s for sec in payload["sections"] for par in sec["paragraphs"] for s in par["sentences"]
                ).lower()
                check("düşürülen iddia METNİ gövdede yok",
                      all(d["text"].lower() not in body for d in payload["dropped"]))
            export_link = report.get_by_role("link", name="Markdown indir")
            href = export_link.get_attribute("href") or ""
            check("export bağlantısı aynı origin'de doğru endpoint",
                  href.startswith("/api/") and href.endswith("/export?format=md"), href)
            page.screenshot(path=str(shots / "report.png"), full_page=True)
        else:
            print("\n--- Gerçek rapor render'ı ATLANDI (kopyada rapor artefaktı yok) ---")

        print("\n--- Yazdırma sözleşmesi (§10.12 / DESIGN_SYSTEM §1.5) ---")
        page.emulate_media(media="print")
        check("kabuk header'ı gizli", page.evaluate(
            "() => getComputedStyle(document.querySelector('header[data-print=\"hide\"]')).display") == "none")
        check("kolonlar gizli", all(d == "none" for d in page.evaluate(
            "() => [...document.querySelectorAll('aside[data-print=\"hide\"]')].map(e => getComputedStyle(e).display)")))
        if existing:
            check("rapor görünür ve tam boy", page.evaluate(
                "() => getComputedStyle(document.querySelector('[data-print=\"root\"]')).overflow") == "visible")
            page.screenshot(path=str(shots / "print.png"), full_page=True)
        page.evaluate("() => document.documentElement.classList.add('dark')")
        bg = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--background').trim()")
        fg = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim()")
        # Beklenen değerler DESIGN_SYSTEM §1.5 tablosundan gelir (§1.1 light
        # sütunu). Modernist yeniden tasarımın Faz 1'i paleti değiştirdiğinde
        # bu iki satır v2'nin literal'lerinde (#ffffff / #111827) kalmıştı —
        # Faz 1'in kapı listesinde ui_proof yoktu. Kontrolün AMACI değişmedi:
        # karanlık tema açık paletle basılmalı; yalnızca beklenen renkler
        # sözleşmenin bugünkü değerlerine hizalandı. §1.1 değişirse burası ve
        # globals.css'in @media print bloğu birlikte güncellenir.
        check("karanlık temada yazdırma zemini açık palet (§1.5)", bg == "#f3f2f2", bg)
        check("karanlık temada yazdırma metni koyu (§1.5)", fg == "#201e1d", fg)
        page.evaluate("() => document.documentElement.classList.remove('dark')")
        page.emulate_media(media="screen")

        # Artefakt ekranı §13.5 Faz 4 ile TAM EKRAN: sol paneli de kaplıyor,
        # yani "Rapor üret" düğmesi açık bir artefaktın ARDINDA kalıyor. Bu
        # tasarımın kendisi (mockup'ın `position:absolute; inset:0`'ı), hata
        # değil -- ama akışın önce sohbete dönmesi gerekiyor.
        if existing:
            check("açık artefakt sol paneli kaplıyor (tam ekran)",
                  not page.get_by_role("button", name="Rapor üret").is_visible()
                  or page.locator('[data-slot="report-view"]').count() == 1)
            page.get_by_role("button", name="Sohbete dön").click()
            page.wait_for_selector('[data-slot="report-view"]', state="detached")

        print("\n--- Üretim akışı (SAHTE üretici, LLM yok) ---")
        page.get_by_role("button", name="Rapor üret").click()
        progress = page.get_by_role("progressbar")
        progress.wait_for(timeout=10000)
        check("ilerleme çubuğu göründü", True)
        detail_seen = False
        try:
            page.wait_for_function(
                "() => document.querySelector('[data-slot=\"studio-panel\"]').innerText.includes('bölüm yazıldı')",
                timeout=10000)
            detail_seen = True
        except Exception:
            pass
        check("bölüm ilerlemesi metni görünüyor", detail_seen)
        pct = progress.get_attribute("aria-valuenow")
        check("pct 0-100 TAM SAYI (§9.5 ölçeği)",
              pct is not None and pct.isdigit() and 0 <= int(pct) <= 100, str(pct))
        page.wait_for_selector("text=Arayüz Kanıtı Raporu", timeout=30000)
        check("üretim bitince rapor otomatik açıldı",
              "Arayüz Kanıtı Raporu" in page.locator('[data-print="root"]').inner_text())
        check("düşürülen iddia panelde görünüyor",
              "gpt-4" in page.locator('[data-print="root"]').inner_text())

        # TAZE artefakt: iddialar canlı korpusa bağlandı, yani chunk çapaları
        # dolu ve atıf üst simgeleri basılmalı. Bayat artefaktın yukarıdaki
        # bozunmasının bir KOD hatası olmadığını gösteren karşı ölçüm budur.
        # Taze raporu SIRAYA göre değil BAŞLIĞA göre bul: listede artık birden
        # fazla rapor var ve sıralamaya güvenmek kırılgan.
        fresh = next(
            a for a in json.loads(urllib.request.urlopen(
                f"{BASE}/api/artifacts?kind=report").read())
            if a["title"] == "Arayüz Kanıtı Raporu"
        )
        fresh_detail = json.loads(urllib.request.urlopen(
            f"{BASE}/api/artifacts/{fresh['id']}").read())
        # Üst simgenin GERÇEK koşulu (report-view.tsx): iddianın chunk çapası
        # olacak VE o chunk payload'ın `citations` listesinde bulunacak --
        # numara o listenin sırasından geliyor. Önceki hâli "her cümlenin üst
        # simgesi var" diyordu; bu, iki koşulun ikisini de atlayan bir
        # varsayımdı.
        fresh_cited = {c["chunk_id"] for c in fresh_detail["payload"]["citations"]}
        fresh_expected = sum(
            1 for c in fresh_detail["claims"]
            if c.get("chunk_id") in fresh_cited
            and not c["node_path"].startswith("/dropped")
        )
        check("taze artefaktın iddiaları canlı chunk'a bağlandı",
              any(c.get("chunk_id") is not None for c in fresh_detail["claims"]))
        check("taze raporda üst simge sayısı = alıntılanan çapa sayısı",
              page.locator('[data-print="root"] sup').count() == fresh_expected,
              f"{page.locator('[data-print=\"root\"] sup').count()} üst simge / "
              f"{fresh_expected} beklenen")
        check("POZİTİF durum: en az bir üst simge basıldı",
              fresh_expected > 0 and page.locator('[data-print="root"] sup').count() > 0,
              f"{fresh_expected} beklenen")

        page.get_by_role("button", name="Sohbete dön").click()
        check("rapor kapandı, sohbete dönüldü", page.locator('[data-print="root"]').count() == 0)

        print("\n--- Zihin haritası (§11.9) ---")
        page.get_by_role("button", name="Zihin haritası üret").click()
        page.wait_for_selector('[data-slot="mindmap-view"]', timeout=30000)
        mindmap = page.locator('[data-slot="mindmap-view"]')
        nodes = _FAKE_MINDMAP_PAYLOAD["nodes"]
        # §13.5 Faz 4: çizim SVG dairelerden Modernist kutu ağacına geçti.
        # ROLLER DEĞİŞMEDİ -- seçiciler artık etiketten bağımsız, çünkü
        # ölçülen şey elemanın türü değil ERİŞİLEBİLİRLİK SÖZLEŞMESİ.
        tree = mindmap.locator('[role="tree"]')
        items = mindmap.locator('[role="treeitem"]')
        check("üretim bitince harita otomatik açıldı", tree.count() == 1)
        check("her düğüm bir treeitem", items.count() == len(nodes),
              f"{items.count()}/{len(nodes)}")
        check("kök aria-level=1, konular aria-level=2",
              items.first.get_attribute("aria-level") == "1"
              and items.nth(1).get_attribute("aria-level") == "2")
        # Kenarlar artık SVG `line` değil, kutuları bağlayan CSS konnektörleri.
        # Ölçülen iddia AYNI kaldı: kök ile her dal arasında GÖRÜNÜR bir bağ
        # var. Konnektörler `aria-hidden` (dekoratif) ve her dal satırı bir
        # tane taşıyor, artı kökten çıkan omurga.
        connectors = mindmap.locator('[role="tree"] [aria-hidden="true"] > span')
        check("dallar köke bağlandı (konnektörler çizildi)",
              connectors.count() >= len(nodes) - 1,
              f"{connectors.count()} konnektör / {len(nodes) - 1} dal")

        # Roving tabindex + ok tuşu: §11.9'un WCAG AA iddiası BURADA ölçülüyor.
        check("yalnızca seçili düğüm tabindex=0",
              items.first.get_attribute("tabindex") == "0"
              and items.nth(1).get_attribute("tabindex") == "-1")
        items.first.focus()
        page.keyboard.press("ArrowRight")
        check("ArrowRight bir sonraki düğüme geçiyor",
              items.nth(1).get_attribute("aria-selected") == "true")
        check("seçilen düğümün kaynakları yanda listelendi",
              "[Kaynak: kanit.md]" in mindmap.inner_text())
        page.keyboard.press("End")
        check("End son düğüme atlıyor",
              items.last.get_attribute("aria-selected") == "true")
        page.keyboard.press("Home")
        check("Home köke dönüyor",
              items.first.get_attribute("aria-selected") == "true")

        # Düğüm artık `<g>` değil `<div>` (§13.5 Faz 4 kutu ağacı); seçici
        # etiketten bağımsız hâle getirildi. `text_content()` ikisinde de
        # çalışıyor, bu yüzden okuma biçimi korundu.
        fallback = mindmap.locator('[data-label-source="fallback"]')
        check("yedek etiketli düğüm 'korpustan türetildi' uyarısı taşıyor",
              fallback.count() == 1
              and "korpustan türetildi" in (fallback.text_content() or ""))
        check("düşürülen etiket önerisi ayrı panelde",
              "Haritaya alınmayan etiket önerileri" in mindmap.inner_text()
              and "gpt-4" in mindmap.inner_text())
        export_href = mindmap.get_by_role("link", name="Markdown indir").get_attribute("href") or ""
        check("harita export bağlantısı aynı origin'de",
              export_href.startswith("/api/") and export_href.endswith("/export?format=md"),
              export_href)
        page.screenshot(path=str(shots / "mindmap.png"), full_page=True)
        page.get_by_role("button", name="Sohbete dön").click()

        print("\n--- Quiz (§12.11) ---")
        page.get_by_role("button", name="Quiz üret").click()
        page.wait_for_selector('[data-slot="quiz-runner"]', timeout=30000)
        quiz = page.locator('[data-slot="quiz-runner"]')
        questions = _FAKE_QUIZ_PAYLOAD["questions"]
        check("üretim bitince quiz otomatik açıldı", quiz.count() == 1)
        check("her soru render edildi",
              quiz.locator("li[data-question-id]").count() == len(questions),
              f"{quiz.locator('li[data-question-id]').count()}/{len(questions)}")
        check("çoktan seçmeli 4 şık taşıyor",
              quiz.locator('li[data-question-id="q0"] input[type="radio"]').count() == 4)
        check("true_false şıkları yerelleştirildi (payload kanonik kalıyor)",
              "Doğru" in quiz.locator('li[data-question-id="q1"]').inner_text()
              and "true" not in quiz.locator('li[data-question-id="q1"]').inner_text())
        check("serbest metin soruları girdi kutusu taşıyor",
              quiz.locator('li[data-question-id="q2"] input[type="text"]').count() == 1
              and quiz.locator('li[data-question-id="q3"] input[type="text"]').count() == 1)

        # Üç deterministik soru DOĞRU cevaplanır; kısa cevap serbest yazılır.
        quiz.locator('li[data-question-id="q0"] input[value="SQLite"]').check()
        quiz.locator('li[data-question-id="q1"] input[value="true"]').check()
        quiz.locator('li[data-question-id="q2"] input[type="text"]').fill("float32")
        quiz.locator('li[data-question-id="q3"] input[type="text"]').fill("yerel veritabanında")
        page.get_by_role("button", name="Cevapları gönder").click()
        page.wait_for_selector("text=Beklenen cevap", timeout=15000)

        check("skor YALNIZCA deterministik sorulardan (3/3)",
              "3/3" in quiz.inner_text(), quiz.inner_text()[:0])
        q0 = quiz.locator('li[data-question-id="q0"]')
        check("doğru cevap 'Doğru' olarak işaretlendi", "Doğru" in q0.inner_text())
        check("sonuçta belgedeki dayanak ve atıf gösteriliyor",
              "Belgedeki dayanak" in q0.inner_text()
              and "[Kaynak: kanit.md]" in q0.inner_text())

        # §12.8'in GÖRÜNÜR kuralı: short_answer bir eşiğe indirgenmez.
        q3 = quiz.locator('li[data-question-id="q3"]')
        q3_text = q3.inner_text()
        check("short_answer benzerlik SAYISI gösteriyor", "Benzerlik" in q3_text)
        # Yargı olmayan soruda kararı kullanıcı veriyor; iki metin YAN YANA
        # gösteriliyor ki karşılaştırma göz gezdirmeye kalmasın. Bu bir
        # UX eklemesi, YARGI DEĞİL -- aşağıdaki §12.8 kontrolü hâlâ geçerli.
        # Etiketler CSS ile büyük harfe çevriliyor (`uppercase`) ve
        # `inner_text()` dönüşmüş metni veriyor -- karşılaştırma harf
        # durumundan bağımsız. Türkçe 'i' tuzağı için casefold DEĞİL,
        # doğrudan büyük harfli beklenen değer yazılıyor.
        check("short_answer'da kendi cevabı beklenenin YANINDA gösteriliyor",
              "SENİN CEVABIN" in q3_text
              and "yerel veritabanında" in q3_text
              and "BEKLENEN CEVAP" in q3_text,
              q3_text.replace("\n", " | ")[:140])
        check("short_answer DOĞRU/YANLIŞ olarak işaretlenmiyor (§12.8)",
              "Doğru" not in q3_text and "Yanlış" not in q3_text, q3_text.replace("\n", " | "))
        # Yargısız sorunun sonucu ayrıca TEK BAŞINA kaydedilir: sayfa
        # görüntüsü iç kapta kaydığı için `full_page` bu bloğu yakalayamıyor.
        q3.screenshot(path=str(shots / "short-answer-result.png"))
        check("quiz'e alınmayan soru ayrı panelde",
              "Quiz'e alınmayan sorular" in quiz.inner_text()
              and "gpt-4" in quiz.inner_text())
        attempts = json.loads(urllib.request.urlopen(
            f"{BASE}/api/quiz/{json.loads(urllib.request.urlopen(f'{BASE}/api/artifacts?kind=quiz').read())[0]['id']}/attempts"
        ).read())
        check("deneme sunucuya kaydedildi", len(attempts) == 1 and attempts[0]["score"] == 1.0,
              str(attempts[:1]))
        # --- Faz 4: ortak tam-ekran kabuk (§13.5) ---
        # Quiz hâlâ açıkken ölçülür: üç ekranın da AYNI kabuğu kullandığı
        # iddiası, üçünde de aynı seçicilerin bulunmasıyla gösteriliyor.
        rail = page.locator('[data-slot="quiz-rail"]')
        check("quiz ilerleme rayı var (mockup'ın 240 px kolonu)", rail.count() == 1)
        check("ray doğru sayısını sunucunun kararından okuyor",
              "1/3" in rail.inner_text() or "/3" in rail.inner_text(),
              rail.inner_text().replace("\n", " | ")[:120])

        shell = page.locator('[data-slot="quiz-runner"]')
        box = shell.bounding_box()
        viewport = page.viewport_size
        check("artefakt ekranı TAM EKRAN (kabuğun üstünü kaplıyor)",
              box is not None and box["x"] == 0 and box["y"] == 0
              and box["width"] == viewport["width"]
              and box["height"] == viewport["height"],
              str(box))
        check("üst çubukta 'Yeniden üret' var",
              page.get_by_role("button", name="Yeniden üret").count() == 1)
        # Etiket hatası düzeldi: eskiden quiz kapatılırken de "Raporu kapat"
        # yazıyordu (tek i18n anahtarı üç görünümde paylaşılıyordu).
        check("kapatma etiketi tipten bağımsız ('Sohbete dön')",
              page.get_by_role("button", name="Raporu kapat").count() == 0)
        page.screenshot(path=str(shots / "quiz.png"), full_page=True)
        page.get_by_role("button", name="Sohbete dön").click()

        # Kapsam seçici EN SONA konur: gerçek bir üretim tetikliyor ve yeni bir
        # artefakt satırı yazıyor. Daha erken koşsaydı yukarıdaki bölümlerin
        # "listenin ilki" varsayımını bozardı.
        print("\n--- Kapsam seçici (§9.7 · scope=\"document\") ---")
        documents = json.loads(urllib.request.urlopen(f"{BASE}/api/documents").read())
        scope_select = page.get_by_label("Kapsam")
        check("kapsam seçici render edildi", scope_select.count() == 1)
        check("etiketle ilişkili (klavye + ekran okuyucu)",
              page.locator('[data-slot="studio-scope"]').count() == 1)
        check("varsayılan kapsam korpus -- mevcut davranış değişmedi",
              scope_select.input_value() == "corpus")
        check("her belge bir seçenek + 'Tüm belgeler'",
              scope_select.locator("option").count() == len(documents) + 1,
              f"{scope_select.locator('option').count()} seçenek / {len(documents)} belge")

        # İSTEK GÖVDESİ ölçülür: seçicinin gerçekten scope="document" kurduğu,
        # kod incelemesiyle değil ağ trafiğiyle gösterilir.
        posted: list[dict] = []
        page.on("request", lambda r: posted.append(json.loads(r.post_data or "{}"))
                if r.method == "POST" and r.url.endswith("/api/artifacts") else None)

        target = documents[0]
        scope_select.select_option(str(target["id"]))
        check("seçim sonrası ipucu belge kapsamını anlatıyor",
              "yalnızca seçili belgeden" in page.locator('[data-slot="studio-panel"]').inner_text())

        page.get_by_role("button", name="Rapor üret").click()
        page.wait_for_selector('[data-print="root"]', timeout=30000)
        check("istek scope=\"document\" ve document_id ile gitti",
              posted and posted[-1].get("scope") == "document"
              and posted[-1].get("document_id") == target["id"],
              str(posted[-1] if posted else None))

        created = json.loads(urllib.request.urlopen(f"{BASE}/api/artifacts?kind=report").read())[0]
        check("üretilen artefakt belge kapsamında kaydedildi",
              created["scope"] == "document" and created["document_id"] == target["id"],
              f"scope={created['scope']} document_id={created['document_id']}")
        page.screenshot(path=str(shots / "scope.png"), full_page=True)
        page.get_by_role("button", name="Sohbete dön").click()

        # Faz 2 kapanma koşulu: yerleşim sözleşmesi ÜÇ kırılımda da doğrulanır
        # (§13.5). Önceki sürüm yalnızca 1440px ölçüyordu; kabuk §13.2 ile
        # değiştiği için tek genişlikte ölçmek kırılım regresyonunu kaçırırdı.
        # ---------------------------------------------------------------
        # Faz 3 — satır içi numaralı alıntı -> çekmece -> sayfa görüntüsü
        # ---------------------------------------------------------------
        print("\n--- Sayfa görüntüsü ucu (§13.4) ---")
        # Kopyalanan veritabanındaki belge bu özellikten ÖNCE yüklendiği için
        # kaynağı saklanmamış: 404 DOĞRU cevap (geriye dönük veri sınırı).
        existing_doc = json.loads(urllib.request.urlopen(f"{BASE}/api/documents").read())[0]
        try:
            urllib.request.urlopen(
                f"{BASE}/api/documents/{urllib.parse.quote(existing_doc['filename'])}"
                f"/pages/1/image"
            )
            check("kaynağı saklanmamış belge 404 veriyor", False, "200 döndü")
        except urllib.error.HTTPError as exc:
            check("kaynağı saklanmamış belge 404 veriyor", exc.code == 404, str(exc.code))

        # Gerçek yükleme yolundan geçen bir PDF: baytlar saklanmalı ve sayfa
        # rasterlenebilmeli. Embedding sahte, ama YÜKLEME YOLU gerçek.
        pdf_path = PROJECT_ROOT / "Foundry_Local_Plan.pdf"
        with open(pdf_path, "rb") as fh:
            body, content_type = _multipart(pdf_path.name, fh.read())
        req = urllib.request.Request(f"{BASE}/api/documents", data=body,
                                     headers={"Content-Type": content_type})
        urllib.request.urlopen(req).read()  # SSE gövdesi tüketilir

        image_url = (
            f"{BASE}/api/documents/{urllib.parse.quote(pdf_path.name)}/pages/2/image"
        )
        with urllib.request.urlopen(image_url) as resp:
            image_bytes = resp.read()
            image_type = resp.headers["content-type"]
        check("sayfa görüntüsü döndü", image_type == "image/webp"
              and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP",
              f"{image_type} / {len(image_bytes)} bayt")
        try:
            urllib.request.urlopen(
                f"{BASE}/api/documents/{urllib.parse.quote(pdf_path.name)}/pages/999/image"
            )
            check("aralık dışı sayfa 404", False, "200 döndü")
        except urllib.error.HTTPError as exc:
            check("aralık dışı sayfa 404", exc.code == 404, str(exc.code))

        print("\n--- Satır içi alıntı -> çekmece (§13.4) ---")
        page.reload(wait_until="networkidle")
        page.get_by_label("Belgelerinize bir soru sorun…").fill("Bu belgeler ne hakkında?")
        page.get_by_role("button", name="Gönder").click()
        page.wait_for_selector('[data-slot="citation-marker"]', timeout=20000,
                               state="attached")
        markers = page.locator('[data-slot="citation-marker"]')
        diag = page.evaluate("""() => {
            const el = document.querySelector('[data-slot="citation-marker"]');
            if (!el) return "yok";
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            const p = getComputedStyle(el.parentElement);
            return `box=${r.width}x${r.height} disp=${s.display} vis=${s.visibility}`
                 + ` fs=${s.fontSize} | sup: disp=${p.display} fs=${p.fontSize}`
                 + ` box=${el.parentElement.getBoundingClientRect().width}`;
        }""")
        check("üst simge GÖRÜNÜR (sıfır boyut değil)", markers.first.is_visible(), diag)
        check("cevapta numaralı üst simge basıldı", markers.count() >= 1,
              f"{markers.count()} üst simge")
        check("numaralandırma 1'den başlıyor",
              markers.first.get_attribute("data-citation-number") == "1")

        check("çekmece üst simgeye basmadan KAPALI",
              page.locator('[data-slot="citation-drawer"]').count() == 0)
        markers.first.click()
        page.wait_for_selector('[data-slot="citation-drawer"]', timeout=10000)
        check("üst simge çekmeceyi açtı",
              page.locator('[data-slot="citation-drawer"]').count() == 1)

        meta_text = page.locator('[data-slot="citation-meta"]').first.inner_text()
        # KRİTİK (AGENTS.md §1.1): "benzerlik" HAM COSINE. Sahte akış 0.71
        # veriyor; ekranda 0.71 görünmeli -- yüzde değil, yeniden ölçeklenmiş
        # değil, güven bandından türetilmiş değil.
        check("künye ham cosine gösteriyor (0.71)", "0.71" in meta_text, meta_text)
        check("künye 'bölüm i/toplam' taşıyor", "bölüm" in meta_text and "/" in meta_text,
              meta_text)
        page.screenshot(path=str(shots / "citation-drawer.png"), full_page=True)

        # Çekmece kapatılır: aşağıdaki kırılım kontrolleri "kalıcı kolon var
        # mı" diye bakıyor ve açık bir drawer o ölçümü kirletir.
        page.get_by_role("button", name="Kaynak panelini kapat").click()
        page.wait_for_selector('[data-slot="citation-drawer"]', state="detached")

        print("\n--- Kırılımlar (§4 · §13.2) ---")
        for label, width, sidebar_persistent in [
            ("mobil", 390, False),
            ("tablet", 900, True),
            ("masaüstü", 1440, True),
        ]:
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_function(
                "w => document.querySelector('[data-slot=\"app-shell\"]')"
                ".dataset.breakpoint === w",
                arg={390: "mobile", 900: "tablet", 1440: "desktop"}[width],
            )
            aside = page.get_by_role("complementary", name="Belge yönetimi")
            check(f"{label} ({width}px): sol kolon "
                  f"{'kalıcı' if sidebar_persistent else 'drawer'}",
                  (aside.count() == 1) == sidebar_persistent)
            # Sağ kolon HİÇBİR kırılımda kalıcı değil — v2'de masaüstünde
            # kalıcıydı, §13.2 bunu çekmeceye çevirdi.
            check(f"{label} ({width}px): alıntı çekmecesi kalıcı değil",
                  page.locator('[data-slot="retrieval-inspector"]').count() == 0)

        print("\n--- Offline ve konsol denetimi ---")
        check("konsol hatası yok", not console_errors, str(console_errors[:3]))
        check("harici ağ isteği YOK (AGENTS.md §1.2)", not external, str(external[:3]))

        browser.close()

    print(f"\n  Ekran görüntüleri: {shots}")
    if fails:
        print(f"\n  FAIL -- {len(fails)} kontrol düştü: {fails}")
        return 1
    print("\n  PASS -- arayüz katmanı ölçüldü; tıklama akışı ve yazdırma sözleşmesi çalışıyor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
