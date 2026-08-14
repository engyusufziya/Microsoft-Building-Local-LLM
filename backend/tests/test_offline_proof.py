"""eval/offline_proof.py -- Görev 6: offline kanıt aracının kendisinin doğruluğu.

offline_proof.py'nin gerçek eval koşumunda GÖZLEMLENEN 0 bağlantı denemesi
"doğru şekilde hiçbir şey bulunmadı" mı, yoksa "dedektör bozuk, hiçbir şeyi
tespit edemiyor" mu ayrımını bu testler yapıyor -- sentetik bir loopback-dışı
bağlantı denemesi üreterek dedektörün onu GERÇEKTEN yakaladığını kanıtlıyor.
"""

from __future__ import annotations

import importlib
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
offline_proof = importlib.import_module("offline_proof")


# --------------------------------------------------------------------------- _is_loopback


def test_loopback_adresleri_tanir():
    for host in ("127.0.0.1", "localhost", "::1", "0.0.0.0", "127.5.5.5"):
        assert offline_proof._is_loopback(host) is True


def test_disari_adresleri_tanir():
    for host in ("8.8.8.8", "1.1.1.1", "example.com", "93.184.216.34"):
        assert offline_proof._is_loopback(host) is False


# --------------------------------------------------------------------------- ConnectionRecorder


def test_recorder_loopback_denemesini_kaydeder():
    """Dedektörün GERÇEKTEN çalıştığını kanıtlar: sentetik bir bağlantı
    denemesi üretir (gerçek bir sunucuya değil, hemen reddedilecek bir
    porta) ve recorder'ın onu yakaladığını doğrular.
    """
    with offline_proof.ConnectionRecorder() as rec:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", 1))  # port 1: kapalı olması neredeyse kesin
        except OSError:
            pass  # bağlantı reddedilmesi beklenir -- yalnızca DENEME kaydı önemli
        finally:
            s.close()

    assert ("127.0.0.1", 1) in rec.attempts
    assert rec.non_loopback == []


def test_recorder_disari_denemesini_yakalar_ve_isaretler():
    """KRİTİK regresyon testi: dedektör bir loopback-dışı deneme karşısında
    SESSİZ KALMAMALI. Gerçek bir ağ isteği YAPMADAN (offline ilkesine sadık
    kalarak) -- yalnızca .connect() çağrısını tetikleyip hemen kapatarak --
    recorder'ın bunu 'DIŞARI' olarak işaretlediğini doğrular.
    """
    with offline_proof.ConnectionRecorder() as rec:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.05)
        try:
            # TEST-NET-1 (RFC 5737): yönlendirilemez, hiçbir gerçek isteğe
            # ULAŞMAZ, yalnızca .connect() çağrısının kendisini tetikler.
            s.connect(("192.0.2.1", 80))
        except OSError:
            pass
        finally:
            s.close()

    assert ("192.0.2.1", 80) in rec.attempts
    assert ("192.0.2.1", 80) in rec.non_loopback


def test_recorder_baglanti_denemedigi_seyi_engellemez():
    """Recorder yalnızca GÖZLEMLER, engellemez -- offline_proof.py'nin
    yorumundaki iddiayla tutarlı ('Bağlantıyı ENGELLEMEZ')."""
    with offline_proof.ConnectionRecorder():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", 1))
        except OSError as e:
            # Bağlantı REDDEDİLDİ (ECONNREFUSED) -- recorder tarafından değil,
            # o portta dinleyen bir şey olmadığı için. Recorder kendisi hata
            # üretmiyor.
            assert e.errno is not None
        finally:
            s.close()


def test_patch_cikista_geri_alinir():
    original = socket.socket.connect
    with offline_proof.ConnectionRecorder():
        assert socket.socket.connect is not original
    assert socket.socket.connect is original
