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

  - zihin haritası: SVG ağaç semantiği, ok tuşlarıyla düğüm gezinmesi
    (WCAG AA, §11.9), seçili düğümün kaynak listesi, yedek etiketin
    "korpustan türetildi" uyarısı, kenarların çizilmesi;
  - quiz: soru tipleri, şık/serbest metin girdileri, gönderim, sonuç
    ekranı -- ve §12.8'in görünür kuralı: `short_answer` DOĞRU/YANLIŞ
    olarak işaretlenmez, yalnızca benzerlik sayısı gösterilir.

Bu iki bölüm Faz 3/4 tesliminde EKSİKTİ: `FEATURE_SPEC §11.11`'in "klavyeyle
gezilebilir" maddesi kod incelemesine dayanıyordu, ölçüme değil. Bu koşum o
boşluğu kapatır.

Veritabanı: `rag.db`'nin KOPYASI (üretim veritabanına dokunulmaz). Kopyada
gerçek bir rapor artefaktı varsa ekranda o render edilir; yoksa o adımlar
atlanır ve atlandığı yazılır.

Gereksinim: `playwright` + Chromium. ÇALIŞMA ANI BAĞIMLILIĞI DEĞİLDİR --
`requirements.txt`'e girmez (CLAUDE.md §1.2: ürün yolunda ağ/tarayıcı yok);
bkz. `requirements-dev.txt`.

    .venv/bin/pip install -r requirements-dev.txt
    .venv/bin/playwright install chromium
    .venv/bin/python eval/ui_proof.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
    """rag.db'yi kopyalar. WAL sidecar'ları KOPYALANMAZ ve varsa silinir.

    Ölçülen tuzak: yalnızca ana dosyayı kopyalamak yetmiyor -- hedefte önceki
    koşumdan kalmış bir `-wal` dosyası varsa SQLite onu replay edip silinmiş
    sanılan artefaktları geri getiriyor ve test yanlış veriye bakıyor.
    """
    target = target_dir / "ui_proof.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(target) + suffix).unlink(missing_ok=True)
    shutil.copyfile(source, target)
    return target


def _start_server(db_path: Path):
    os.environ["RAG_BACKEND_DB_PATH"] = str(db_path)
    os.environ["RAG_BACKEND_SKIP_WARMUP"] = "1"

    import uvicorn
    from backend.main import create_app
    from rag import models
    from rag.artifacts import base

    app = create_app()

    class _FakeReportGenerator:
        """Gerçek ReportGenerator'ın SSE davranışını taklit eder, LLM çağırmaz."""

        kind = "report"

        def generate(self, ctx):
            for i in range(1, 4):
                time.sleep(0.4)  # ilerleme çubuğu tarayıcıda gerçekten görülebilsin
                ctx.emit("progress", {"pct": round(i * 100 / 3), "detail": f"{i}/3 bölüm yazıldı"})
            return base.GeneratedArtifact(
                title="Arayüz Kanıtı Raporu",
                payload=_FAKE_PAYLOAD,
                claims=[
                    ("/sections/0/paragraphs/0/sentences/0", "Arayüz kanıtı için üretilmiş özet cümlesi."),
                    ("/sections/1/paragraphs/0/sentences/0", "Arayüz kanıtı için üretilmiş bulgu cümlesi."),
                    ("/dropped/0", "Bu sistem GPT-4 kullanır."),
                ],
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

        print("\n--- Sağ panel sekmeleri (§9.9.3) ---")
        sources_tab = page.get_by_role("tab", name="Kaynaklar")
        studio_tab = page.get_by_role("tab", name="Studio")
        check("iki sekme de var", sources_tab.count() == 1 and studio_tab.count() == 1)
        check("başlangıçta Kaynaklar seçili", sources_tab.get_attribute("aria-selected") == "true")
        sources_tab.focus()
        page.keyboard.press("ArrowRight")
        check("ok tuşuyla Studio'ya geçiliyor (WCAG AA)", studio_tab.get_attribute("aria-selected") == "true")
        page.keyboard.press("Home")
        check("Home ile Kaynaklar'a dönülüyor", sources_tab.get_attribute("aria-selected") == "true")
        studio_tab.click()
        page.wait_for_selector('[data-slot="studio-panel"]')
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
            check("her cümlenin atıf üst simgesi var",
                  report.locator("sup").count() == expected_sentences,
                  f"{report.locator('sup').count()} atıf")
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
        # CSS minifier #ffffff -> #fff kısaltabiliyor; ikisi de aynı renk.
        check("karanlık temada yazdırma zemini beyaz", bg in ("#ffffff", "#fff"), bg)
        check("karanlık temada yazdırma metni koyu", fg == "#111827", fg)
        page.evaluate("() => document.documentElement.classList.remove('dark')")
        page.emulate_media(media="screen")

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
        page.get_by_role("button", name="Raporu kapat").click()
        check("rapor kapandı, sohbete dönüldü", page.locator('[data-print="root"]').count() == 0)

        print("\n--- Zihin haritası (§11.9) ---")
        page.get_by_role("button", name="Zihin haritası üret").click()
        page.wait_for_selector('[data-slot="mindmap-view"]', timeout=30000)
        mindmap = page.locator('[data-slot="mindmap-view"]')
        nodes = _FAKE_MINDMAP_PAYLOAD["nodes"]
        tree = mindmap.locator('svg[role="tree"]')
        items = mindmap.locator('g[role="treeitem"]')
        check("üretim bitince harita otomatik açıldı", tree.count() == 1)
        check("her düğüm bir treeitem", items.count() == len(nodes),
              f"{items.count()}/{len(nodes)}")
        check("kök aria-level=1, konular aria-level=2",
              items.first.get_attribute("aria-level") == "1"
              and items.nth(1).get_attribute("aria-level") == "2")
        # Kenarlar: 1 "related" + kök->konu bağlantıları.
        check("kenarlar çizildi",
              mindmap.locator("svg line").count()
              == len(_FAKE_MINDMAP_PAYLOAD["edges"]) + len(nodes) - 1,
              f"{mindmap.locator('svg line').count()} çizgi")

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

        fallback = mindmap.locator('g[data-label-source="fallback"]')
        # SVG düğümünde inner_text() çalışmaz ("Node is not an HTMLElement",
        # ölçüldü) -- SVG metni text_content() ile okunur.
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
        page.get_by_role("button", name="Raporu kapat").click()

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
        check("short_answer DOĞRU/YANLIŞ olarak işaretlenmiyor (§12.8)",
              "Doğru" not in q3_text and "Yanlış" not in q3_text, q3_text.replace("\n", " | "))
        check("quiz'e alınmayan soru ayrı panelde",
              "Quiz'e alınmayan sorular" in quiz.inner_text()
              and "gpt-4" in quiz.inner_text())
        attempts = json.loads(urllib.request.urlopen(
            f"{BASE}/api/quiz/{json.loads(urllib.request.urlopen(f'{BASE}/api/artifacts?kind=quiz').read())[0]['id']}/attempts"
        ).read())
        check("deneme sunucuya kaydedildi", len(attempts) == 1 and attempts[0]["score"] == 1.0,
              str(attempts[:1]))
        page.screenshot(path=str(shots / "quiz.png"), full_page=True)
        page.get_by_role("button", name="Raporu kapat").click()

        print("\n--- Offline ve konsol denetimi ---")
        check("konsol hatası yok", not console_errors, str(console_errors[:3]))
        check("harici ağ isteği YOK (CLAUDE.md §1.2)", not external, str(external[:3]))

        browser.close()

    print(f"\n  Ekran görüntüleri: {shots}")
    if fails:
        print(f"\n  FAIL -- {len(fails)} kontrol düştü: {fails}")
        return 1
    print("\n  PASS -- arayüz katmanı ölçüldü; tıklama akışı ve yazdırma sözleşmesi çalışıyor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
