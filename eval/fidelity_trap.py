"""
Sadakat kapısının bilinen sınırını sabitleyen regresyon ölçümü.

Arka plan (PROJE_DURUMU.md "Studio Katmanı -- Faz 1" / docs/FEATURE_SPEC.md
§9.6 "BİLİNEN SINIR"): `rag/artifacts/fidelity.py::bind_claims` *grounding*
ölçer, *entailment* ölçmez -- ham cosine "bu konuda bir chunk var mı"
sorusunu cevaplar, "bu chunk bu iddiayı destekliyor mu" sorusunu cevaplamaz.
Bu yüzden ürünle DOĞRUDAN ÇELİŞEN ama konuya yakın bir iddia ("Bu sistem
varsayılan olarak GPT-4 kullanır ve verileri OpenAI sunucularına gönderir" --
ürün tamamen offline, bkz. CLAUDE.md §1.2) `grounded` işaretlenir.

Bu script o boşluğu bir yorum satırı olmaktan çıkarıp ÖLÇÜLEBİLİR yapar:
bilinen davranışı (skor + verdict) SABİTLER, böylece ileride sessizce
değişmez -- ne kötüleşir (fark edilmeden) ne de düzelir (fark edilmeden
Faz 2'nin kapanma koşulu atlanarak "iyileşti" sayılır). Skor/verdict pinden
SAPARSA script FAIL döner; bu, kodun bozulduğu anlamına gelmez, yalnızca
kaydedilmiş sayının artık doğru olmadığı ve urun-mimari onayıyla (PROJE_DURUMU.md,
FEATURE_SPEC.md §9.6, bu dosya) güncellenmesi gerektiği anlamına gelir.

DİKKAT (CLAUDE.md §1.4): bu script'in FAIL dönmesi FIDELITY_MIN_SCORE'u
yükseltme gerekçesi DEĞİLDİR -- o alternatif zaten değerlendirilip
reddedildi (FEATURE_SPEC.md §9.6, MIN_SCORE'un 0.55->0.45 inişiyle aynı
örtüşme problemi). Telafi Faz 2'nin ikinci katmanına bırakıldı
(docs/STUDIO_PLAN.md §9).

`eval_set.json`'a EKLENMEDİ (bilinçli): eval_set tek bir hattı
(query_router -> retrieve -> answer) ölçüyor; bind_claims'e elle metin veren
bir giriş şemayı zorlayıp "23/23"ün ne ölçtüğünü sessizce genişletirdi.

Kullanım:
    python eval/fidelity_trap.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_eval  # noqa: E402
from rag import store  # noqa: E402
from rag.artifacts import fidelity  # noqa: E402

TRAP_NODE_PATH = "/eval/fidelity_trap"
TRAP_CLAIM = (
    "Bu sistem varsayılan olarak GPT-4 kullanır ve verileri OpenAI "
    "sunucularına gönderir."
)

# Faz 1 doğrulamasında ölçülen ve PROJE_DURUMU.md / FEATURE_SPEC.md §9.6'da
# kayıtlı değer. Tolerans, ölçümün tekrarlanabilirliğinin (embed
# deterministik -- topics.py'deki iki ardışık çağrı testiyle aynı gerekçe)
# ötesinde, chunk sınırlarında donanım/kütüphane sürümünden kaynaklanabilecek
# ondalık gürültüyü yutacak kadar sıkı tutuldu; bunun ötesindeki bir sapma
# gerçek bir davranış değişikliğidir ve sessizce görmezden gelinmemelidir.
PINNED_SCORE = 0.5487
SCORE_TOLERANCE = 0.0005
PINNED_VERDICT = "grounded"


def main(argv=None) -> int:
    if not run_eval.EVAL_DB.exists():
        print("=== eval.db kuruluyor (data/*.md) ===")
        conn = store.connect(run_eval.EVAL_DB)
        try:
            for r in run_eval.ingest.ingest_markdown_dir(conn=conn):
                print(f"  {r.summary()}")
        finally:
            conn.close()
        print()

    conn = store.connect(run_eval.EVAL_DB)
    try:
        bindings = fidelity.bind_claims(conn, [(TRAP_NODE_PATH, TRAP_CLAIM)])
    finally:
        conn.close()

    binding = bindings[0]
    score = binding.score
    verdict = binding.verdict

    print("=== Sadakat kapısı tuzağı: konuya yakın ama korpusla çelişen iddia ===\n")
    print(f'  İddia   : "{TRAP_CLAIM}"')
    print(f"  Chunk   : id={binding.chunk_id}")
    print(f"  Skor    : {score:.4f}  (pin: {PINNED_SCORE:.4f} ± {SCORE_TOLERANCE})")
    print(f"  Verdict : {verdict}  (pin: {PINNED_VERDICT})")

    score_ok = score is not None and abs(score - PINNED_SCORE) <= SCORE_TOLERANCE
    verdict_ok = verdict == PINNED_VERDICT

    if score_ok and verdict_ok:
        print(
            "\n  PASS -- bilinen sınır (kapı yanlış-ama-yakın iddiayı 'grounded' "
            "sayıyor) sabit kaldı; sessiz bir değişiklik YOK."
        )
        return 0

    print(
        "\n  FAIL -- ölçüm kayıtlı pinden SAPTI. Bu, FIDELITY_MIN_SCORE'u "
        "değiştirme gerekçesi DEĞİL (CLAUDE.md §1.4, §9.6 -- alternatif zaten "
        "reddedildi). PROJE_DURUMU.md ve docs/FEATURE_SPEC.md §9.6'daki kayıtlı "
        "sayı ile urun-mimari onayıyla güncellenmeli; kök neden araştırılmalı "
        "(embed modeli mi değişti, korpus mu, yoksa Faz 2'nin entailment "
        "katmanı mı devreye girdi)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
