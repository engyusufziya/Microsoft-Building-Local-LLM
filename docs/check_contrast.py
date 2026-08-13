"""
DESIGN_SYSTEM.md'deki kontrast iddialarını doğrular.

Yeni bir renk token'ı eklendiğinde bu script'e de eklenmeli; dokümandaki
sayılar iddia değil, tekrar üretilebilir ölçüm olmalı.

    python docs/check_contrast.py

WCAG 2.1: normal metin AA için >= 4.5:1, büyük metin (>=18.66px/700 veya
>=24px) AA için >= 3.0:1.
"""

from __future__ import annotations

import sys

AA_NORMAL = 4.5

LIGHT = {
    "background": "#FFFFFF",
    "surface": "#F9FAFB",
    "surface-raised": "#FFFFFF",
    "text-primary": "#111827",
    "text-secondary": "#6B7280",
    "text-tertiary": "#6B7280",
    "primary": "#4F46E5",
    "accent": "#9333EA",
    "score-strong": "#047857",
    "score-medium": "#B45309",
    "score-weak": "#DC2626",
    "score-rejected": "#6B7280",
}

DARK = {
    "background": "#0A0A0B",
    "surface": "#141416",
    "surface-raised": "#1C1C1F",
    "text-primary": "#FAFAFA",
    "text-secondary": "#A1A1AA",
    "text-tertiary": "#8B8B93",
    "primary": "#818CF8",
    "accent": "#C084FC",
    "score-strong": "#34D399",
    "score-medium": "#FBBF24",
    "score-weak": "#F87171",
    "score-rejected": "#8B8B93",
}

# Zemin üzerinde okunması gereken ön plan token'ları.
FOREGROUNDS = [
    "text-primary", "text-secondary", "text-tertiary",
    "primary", "accent",
    "score-strong", "score-medium", "score-weak", "score-rejected",
]
BACKGROUNDS = ["background", "surface", "surface-raised"]


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(fg: str, bg: str) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def check(name: str, palette: dict[str, str]) -> list[str]:
    print(f"\n=== {name} ===")
    failures = []
    for bg_name in BACKGROUNDS:
        bg = palette[bg_name]
        for fg_name in FOREGROUNDS:
            ratio = contrast(palette[fg_name], bg)
            ok = ratio >= AA_NORMAL
            if not ok:
                failures.append(f"{name}: {fg_name} on {bg_name} = {ratio:.2f}:1")
            print(f"  {'PASS' if ok else 'FAIL'}  {fg_name:16s} on {bg_name:15s} {ratio:5.2f}:1")
    return failures


def main() -> int:
    failures = check("LIGHT", LIGHT) + check("DARK", DARK)
    print()
    if failures:
        print(f"{len(failures)} kombinasyon AA ({AA_NORMAL}:1) altında:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"Tüm kombinasyonlar WCAG AA ({AA_NORMAL}:1) üstünde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
