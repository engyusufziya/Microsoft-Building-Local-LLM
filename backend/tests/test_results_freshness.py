"""`eval/results.json` ile motorun yapılandırması UYUŞMALI.

NEDEN VAR — bu deponun karakteristik arıza modu:
    Kod ilerlerken ÜRETİLMİŞ KANIT bayatlıyor. İki günde aynı sınıf hata dört
    kez görüldü: pytest kapısı "91/91" derken gerçek 93'tü; README 201 test /
    42 tarayıcı kontrolü derken gerçek 229 / 105'ti; `ui_proof`'un yazdırma
    kontrolü Faz 1'in değiştirdiği paleti fark etmedi; ve `results.json`
    26 Ağustos'ta kalmışken kod 31 Ağustos'a gelmişti.

    Kod tarafı disiplinli çünkü orada KAPI var. Kanıt tarafında kapı yoktu,
    hafıza vardı; hafıza tutmadı. Bu dosya oraya bir kapı koyar.

NE YAKALAR
    `rag/config.py` değişip eval yeniden koşulmadığı durumu. `MIN_SCORE`,
    `TOP_K` ya da chunk parametreleri kaydığında `results.json` artık BAŞKA
    bir sistemi anlatıyor demektir -- ve `/api/metrics` o dosyayı olduğu gibi
    servis ettiği için ürünün Metrics sayfası yanlış eşiği gösterir.

    Ayrıca eval setine soru eklenip koşum tekrarlanmadığı durumu: sonuçlar
    daha küçük bir seti tarif ediyor olur.

NE YAKALAMAZ -- ve bu bilinçli bir sınır
    "Kod değişti ama eval koşulmadı" durumunu GENEL OLARAK yakalamaz. Yakalamak
    için `results.json`'ın tarihini `rag/`'ın son commit tarihiyle kıyaslamak
    gerekirdi; CI `actions/checkout`'u varsayılan olarak `depth: 1` ile
    çalıştığı için o karşılaştırma CI'da güvenilmez, dosya mtime'ları da
    checkout anına eşitlendiği için işe yaramaz. Bu yüzden o kol ürünün kendi
    dürüstlük mekanizmasına bırakıldı: Metrics sayfası `generated_at` tarihini
    HER ZAMAN basar, yani bayat veri kendini ele verir.

Model YÜKLEMEZ: yalnızca iki JSON okur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag import config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS = PROJECT_ROOT / "eval" / "results.json"
EVAL_SET = PROJECT_ROOT / "eval" / "eval_set.json"

RERUN = ".venv/bin/python eval/run_eval.py --json"


@pytest.fixture(scope="module")
def results() -> dict:
    if not RESULTS.exists():
        pytest.skip(f"{RESULTS} yok -- `{RERUN}` ile üretilir")
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def test_results_config_motorunkiyle_ayni(results):
    """Eşik/topK/chunk kaydıysa sonuçlar BAŞKA bir sistemi anlatıyordur."""
    expected = {
        "min_score": config.MIN_SCORE,
        "top_k": config.TOP_K,
        "chunk_words": config.CHUNK_WORDS,
        "chunk_overlap_words": config.CHUNK_OVERLAP_WORDS,
    }
    drifted = {
        key: (results["config"].get(key), value)
        for key, value in expected.items()
        if results["config"].get(key) != value
    }
    assert not drifted, (
        "results.json motorun yapılandırmasıyla uyuşmuyor "
        f"(alan: (results.json, rag/config.py)): {drifted}. "
        f"Yapılandırma değişmiş ama eval yeniden koşulmamış -- `{RERUN}`. "
        "/api/metrics bu dosyayı olduğu gibi servis ediyor, yani Metrics "
        "sayfası şu an yanlış eşiği gösteriyor."
    )


def test_results_eval_setinin_TAMAMINI_kapsiyor(results):
    """Sete soru eklenip koşum tekrarlanmadıysa sonuçlar eksik settir."""
    eval_set = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    questions = eval_set if isinstance(eval_set, list) else eval_set["questions"]

    active = [model for model in results["models"] if model["is_active"]]
    assert active, "results.json'da aktif model yok"

    measured = len(active[0]["questions"])
    assert measured == len(questions), (
        f"results.json {measured} soru ölçmüş, eval_set.json'da {len(questions)} soru var. "
        f"Set büyümüş ama koşum tekrarlanmamış -- `{RERUN}`."
    )


def test_aktif_model_motorun_sohbet_modeli(results):
    """Model değişip eval koşulmadıysa sonuçlar başka bir modelin."""
    active = [model for model in results["models"] if model["is_active"]][0]
    assert active["alias"] == config.CHAT_MODEL, (
        f"results.json'daki aktif model {active['alias']}, "
        f"rag/config.py'de {config.CHAT_MODEL}. `{RERUN}`."
    )
