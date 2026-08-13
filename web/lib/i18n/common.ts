import type { Namespace } from "./index"

/**
 * Ortak buton/hata/eylem metinleri — DESIGN_SYSTEM.md §7.
 * Sadece feature'a özel olmayan, birden çok yerde tekrar edecek metinler
 * burada durur. Sidebar/chat/metrics'e özel metinler kendi namespace
 * dosyalarına gider.
 */
export const common = {
  // --- Butonlar / eylemler ---
  retry: { tr: "Tekrar dene", en: "Retry" },
  cancel: { tr: "İptal", en: "Cancel" },
  close: { tr: "Kapat", en: "Close" },
  confirm: { tr: "Onayla", en: "Confirm" },
  save: { tr: "Kaydet", en: "Save" },
  delete: { tr: "Sil", en: "Delete" },
  copy: { tr: "Kopyala", en: "Copy" },
  copied: { tr: "Kopyalandı", en: "Copied" },
  back: { tr: "Geri", en: "Back" },
  next: { tr: "İleri", en: "Next" },
  dismiss: { tr: "Kapat", en: "Dismiss" },
  yes: { tr: "Evet", en: "Yes" },
  no: { tr: "Hayır", en: "No" },

  // --- Durumlar ---
  loading: { tr: "Yükleniyor…", en: "Loading…" },
  errorGeneric: { tr: "Bir şeyler ters gitti.", en: "Something went wrong." },
  errorNetwork: {
    tr: "Sunucuya ulaşılamadı.",
    en: "Could not reach the server.",
  },

  // --- Tema / dil seçici (theme-toggle.tsx bu anahtarları opsiyonel
  // `labels` prop'u ile alabilir; bkz. components/theme-toggle.tsx) ---
  themeLight: { tr: "Açık", en: "Light" },
  themeDark: { tr: "Koyu", en: "Dark" },
  themeSystem: { tr: "Sistem", en: "System" },
  languageLabel: { tr: "Dil", en: "Language" },

  // --- Sayı içeren örnek: çoğul string birleştirme ile değil, fonksiyonla
  // kurulur (DESIGN_SYSTEM.md §7 adlandırma kuralı). ---
  itemCount: {
    tr: (n: number) => `${n} öğe`,
    en: (n: number) => `${n} item${n === 1 ? "" : "s"}`,
  },
} as const satisfies Namespace
