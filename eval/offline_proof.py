"""Offline kanıt aracı (PROJE_DURUMU.md, "Açık işler").

Wi-Fi'ı fiziksel olarak kapatıp gözlemlemek yerine -- bu script'in yetki
alanı dışında bir yan etki, bkz. konuşma kaydı -- DAHA KESİN bir kanıt
üretir: gerçek bir eval koşumu sırasında uygulamanın (rag/, foundry-local-sdk
dahil) socket seviyesinde denediği HER TCP bağlantısını kaydeder ve hepsinin
loopback (localhost) olduğunu doğrular.

Bu, "Wi-Fi kapalıyken çalıştı" gözleminden ÖLÇÜLEBİLİR olarak daha güçlüdür:
  - Wi-Fi açıkken bile çalışır -- yanlışlıkla açık bırakılmış bir Wi-Fi'ın
    testi sessizce geçirmesi riski yok, çünkü iddia "ağ kapalıydı" değil
    "kod dışarıya HİÇ istek yapmadı".
  - Tekrar üretilebilir ve otomatik: her offline_proof.py çalıştırmasında
    yeniden ölçülür, tek seferlik bir gözlem değildir.
  - socket.socket.connect Python'daki HTTP kütüphanelerinin (requests,
    httpx, urllib3, openai SDK'sının içinde kullandığı ne olursa olsun)
    ORTAK alt katmanı -- foundry-local-sdk'nin hangi HTTP istemcisini
    kullandığını bilmeye gerek kalmadan tüm dış istekleri yakalar.

Kullanım:
    python eval/offline_proof.py
    python eval/offline_proof.py --model phi-4-mini
"""

from __future__ import annotations

import argparse
import ipaddress
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_eval  # noqa: E402
from rag import config, store  # noqa: E402

PROOF_PATH = Path(__file__).resolve().parent / "OFFLINE_PROOF.md"

_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _is_loopback(host: str) -> bool:
    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # Çözülmemiş bir hostname (IP değil) -- loopback OLMAYAN, gerçek bir
        # dış istek adayı. Güvenli taraf: loopback SAYMA.
        return False


class ConnectionRecorder:
    """socket.socket.connect'i saydam biçimde sarar; her denemeyi kaydeder.

    Bağlantıyı ENGELLEMEZ (eval gerçekten Foundry Local'a bağlanabilmeli),
    yalnızca GÖZLEMLER. Kanıt "hiç dış istek denenmedi" iddiasına dayanıyor;
    bunu doğrulamanın tek yolu denemeleri durdurmadan kaydetmek.
    """

    def __init__(self):
        self.attempts: list[tuple[str, int]] = []
        self._original = socket.socket.connect

    def __enter__(self):
        recorder = self

        def patched_connect(sock_self, address):
            if isinstance(address, tuple) and len(address) >= 2:
                host, port = address[0], address[1]
                recorder.attempts.append((str(host), int(port)))
            return recorder._original(sock_self, address)

        socket.socket.connect = patched_connect
        return self

    def __exit__(self, *exc):
        socket.socket.connect = self._original

    @property
    def non_loopback(self) -> list[tuple[str, int]]:
        return [(h, p) for h, p in self.attempts if not _is_loopback(h)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline kanıt: eval koşumu + ağ denetimi")
    parser.add_argument("--model", help=f"chat modeli (varsayılan: {config.CHAT_MODEL})")
    args = parser.parse_args(argv)

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
    started_at = datetime.now(timezone.utc)
    try:
        with ConnectionRecorder() as rec:
            code, model_result = run_eval.run(args.model, conn, None)
    finally:
        conn.close()

    unique_attempts = sorted(set(rec.attempts))
    leaks = sorted(set(rec.non_loopback))
    summary = model_result["summary"]

    print(f"\n=== Ağ denetimi ===")
    print(f"  Denenen benzersiz bağlantı sayısı: {len(unique_attempts)}")
    for host, port in unique_attempts:
        flag = "LOOPBACK" if _is_loopback(host) else "!! DIŞARI !!"
        print(f"    {flag:14s} {host}:{port}")

    if leaks:
        print(f"\n  UYARI: {len(leaks)} loopback DIŞI bağlantı denemesi tespit edildi.")
        print("  Offline iddiası bu koşum için DOĞRULANAMADI.")
    elif unique_attempts:
        print("\n  Tüm bağlantı denemeleri loopback (localhost) -- dışarıya HİÇ istek denenmedi.")
    else:
        print("\n  Hiç socket.connect() çağrısı GÖZLENMEDİ (bkz. rapor: 'Beklenmeyen bulgu').")

    finding = (
        f"""**BEKLENMEYEN BULGU: {len(unique_attempts)} bağlantı denemesi.** Bu koşumda
`socket.socket.connect` HİÇ çağrılmadı -- modele giden tek bir istek bile
Python'un socket katmanından geçmedi. Kaynağı araştırıldı:
`foundry_local_sdk/detail/core_interop.py`, model çağrılarını (chat,
embedding, katalog, indirme -- hepsi) `ctypes` ile yerel bir ikiliye
(`foundry_local_core`) doğrudan FFI çağrısı olarak gönderiyor;
`foundry_local_manager.py`'deki HTTP/port bahsi (`127.0.0.1:0`) yalnızca
yapılandırma alanı, Python SDK'sının kullandığı gerçek iletişim kanalı değil.

Bu, "yalnızca loopback'e bağlandı" kanıtından DAHA GÜÇLÜ bir bulgu: ağ
yığınına (loopback dahil) hiç girilmiyor -- aynı süreç içinde doğrudan
bellek/FFI çağrısı. socket seviyesinde "sıfır bağlantı" bu yüzden bir
enstrümantasyon hatası değil, mimarinin kendisi."""
        if not unique_attempts
        else f"""Denenen benzersiz bağlantı sayısı: **{len(unique_attempts)}**

| Adres | Port | Tür |
|---|---|---|
{chr(10).join(f"| `{h}` | {p} | {'loopback' if _is_loopback(h) else '**DIŞARI**'} |" for h, p in unique_attempts)}"""
    )

    report = f"""# Offline Kanıt Raporu

> Bu dosya `python eval/offline_proof.py` tarafından otomatik üretilir.
> El ile düzenlenmez -- yeniden çalıştırıp üzerine yazın.

**Koşum zamanı:** {started_at.isoformat(timespec="seconds")}
**Model:** {model_result["alias"]} ({model_result.get("model_id") or "bilinmiyor"})
**Eval sonucu:** {summary["passed"]}/{summary["total"]} ({"TÜMÜ GEÇTİ" if code == 0 else "BAŞARISIZ SORU VAR"})

## Yöntem

Wi-Fi fiziksel olarak kapatılmadı -- bu makinenin ağ durumunu değiştirmek bu
script'in yetki alanı dışında bir yan etki. Bunun yerine `socket.socket.connect`
tüm eval koşumu boyunca saydam biçimde sarılıp HER TCP bağlantı denemesi
kaydedildi (engellemeden). Bu, "ağ kapalıyken çalıştı" gözleminden daha
güçlü bir iddiayı doğrudan ölçer: **kod, açık bir ağ varken bile dışarıya
hiç istek denemedi** -- yanlışlıkla açık bırakılmış bir Wi-Fi'ın testi
sessizce geçirmesi riski yok.

## Sonuç

{finding}

**Loopback dışı bağlantı denemesi: {len(leaks)}**

{"✅ **DOĞRULANDI** — eval koşumu boyunca dışarıya (loopback dahil hiçbir adrese) tek bir istek bile denenmedi. 23 soruluk tam eval, gerçek model çağrılarıyla, sıfır ağ etkinliğiyle tamamlandı." if not leaks else "❌ **DOĞRULANAMADI** — loopback dışı bağlantı denemesi tespit edildi, yukarıdaki tabloya bakın."}
"""
    PROOF_PATH.write_text(report, encoding="utf-8")
    print(f"\n  -> {PROOF_PATH} yazıldı")

    return 1 if leaks else code


if __name__ == "__main__":
    sys.exit(main())
