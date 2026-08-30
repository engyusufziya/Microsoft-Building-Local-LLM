import localFont from "next/font/local";

// docs/DESIGN_SYSTEM.md § 2.1: CDN kullanılmaz, offline garantisi bozulur.
// Font dosyaları @fontsource/* npm paketlerinden (SIL Open Font License)
// çıkarılıp app/fonts/*.woff2 olarak depoya gömüldü — lisans dosyaları da
// yanlarında duruyor. Yalnızca kullanılan ağırlıklar paketleniyor.
//
// Archivo (Modernist v3, §13): mockup'ın başlık+gövde ailesi. @fontsource'un
// `latin` (ASCII + Latin-1) ve `latin-ext` (Latin Genişletilmiş-A: ş ğ ı İ …)
// altkümeleri ağırlık başına TEK woff2'de birleştirildi; tek dosya Türkçe'yi
// tam kapsıyor. AYNI birleştirme JetBrains Mono'ya da uygulandı -- Faz 1'de
// atlanmıştı ve mono metinlerde ş/ğ/İ sistem fontuna düşüyordu (Faz 5'te
// ölçüldü, backend/tests/test_font_coverage.py artık nöbet tutuyor).
//
// Inter Faz 6'da KALDIRILDI: yalnızca geçici /onizleme prototipi
// kullanıyordu, prototiple birlikte gitti.

export const archivo = localFont({
  src: [
    { path: "./fonts/archivo-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/archivo-600.woff2", weight: "600", style: "normal" },
    { path: "./fonts/archivo-800.woff2", weight: "800", style: "normal" },
  ],
  variable: "--font-archivo",
  display: "swap",
});

export const jetbrainsMono = localFont({
  src: [
    { path: "./fonts/jetbrains-mono-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/jetbrains-mono-500.woff2", weight: "500", style: "normal" },
  ],
  variable: "--font-mono",
  display: "swap",
});
