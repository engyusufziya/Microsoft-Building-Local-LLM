"""Gömülü fontların TÜRKÇE kapsamı — DESIGN_SYSTEM §2 (tipografi).

Neden bu testin var olması gerekiyor, bir ölçümle: Modernist Faz 1 Archivo'yu
`latin` + `latin-ext` altkümelerini BİRLEŞTİREREK gömdü ve Türkçe glifleri
tam kapsadı. Aynı işlem **JetBrains Mono'ya yapılmadı**; mono font yalnızca
`latin` altkümesiyle kaldı ve `ş Ş İ ğ Ğ` HİÇ YOKTU.

Sonuç sessizdi çünkü tarayıcı eksik glifi sistem fontundan getiriyor: metin
okunuyor ama yanlış yüzle basılıyor. Faz 5'in boş durum ekranındaki
"çevrimdışı" satırında gözle görüldü, sonra `fontTools` ile ölçüldü.

Bu test, aynı hatanın üçüncü bir fontta tekrarlanmasını engeller: depoya
gömülen HER woff2, Türkçe alfabenin tamamını taşımak zorunda.

`fontTools` bir GELİŞTİRME bağımlılığıdır (requirements-dev.txt); ürün
yolunda hiç import edilmez.
"""

from __future__ import annotations

from pathlib import Path

import pytest

fontTools = pytest.importorskip("fontTools.ttLib", reason="fontTools kurulu değil")

FONT_DIR = Path(__file__).resolve().parents[2] / "web" / "app" / "fonts"

# Türkçe'nin ASCII dışındaki harfleri, büyük ve küçük.
TURKISH = {
    "ç": 0x00E7, "Ç": 0x00C7,
    "ğ": 0x011F, "Ğ": 0x011E,
    "ı": 0x0131, "İ": 0x0130,
    "ö": 0x00F6, "Ö": 0x00D6,
    "ş": 0x015F, "Ş": 0x015E,
    "ü": 0x00FC, "Ü": 0x00DC,
}

def _active_fonts() -> list[Path]:
    """Depoya gömülü TÜM woff2'ler.

    Faz 5'te burada bir istisna listesi vardı (Inter yalnızca geçici
    /onizleme prototipinde kullanılıyordu). Faz 6 prototipi ve Inter'i
    kaldırdı; istisna da onunla birlikte gitti. Artık gömülü her font
    ürün yolunda, yani hepsi Türkçe'yi tam kapsamak zorunda.
    """
    return sorted(FONT_DIR.glob("*.woff2"))


def test_font_dizini_bos_degil():
    assert _active_fonts(), f"{FONT_DIR} altında gömülü woff2 yok"


@pytest.mark.parametrize("font_path", _active_fonts(), ids=lambda p: p.name)
def test_gomulu_font_turkce_alfabeyi_TAM_kapsiyor(font_path):
    cmap = set(fontTools.TTFont(str(font_path)).getBestCmap())
    missing = sorted(ch for ch, cp in TURKISH.items() if cp not in cmap)
    assert not missing, (
        f"{font_path.name} Türkçe harfleri kapsamıyor: {missing}. "
        f"latin + latin-ext altkümeleri birleştirilmeli (Faz 1'in Archivo'ya "
        f"uyguladığı işlemin aynısı)."
    )
