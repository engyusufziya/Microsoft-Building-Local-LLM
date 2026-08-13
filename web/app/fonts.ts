import localFont from "next/font/local";

// docs/DESIGN_SYSTEM.md § 2.1: CDN kullanılmaz, offline garantisi bozulur.
// Font dosyaları @fontsource/inter ve @fontsource/jetbrains-mono npm
// paketlerinden (SIL Open Font License) çıkarılıp app/fonts/*.woff2 olarak
// depoya gömüldü — lisans dosyaları da yanlarında duruyor.
// Yalnızca kullanılan ağırlıklar (400/500/600) paketleniyor.

export const inter = localFont({
  src: [
    { path: "./fonts/inter-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/inter-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/inter-600.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-inter",
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
