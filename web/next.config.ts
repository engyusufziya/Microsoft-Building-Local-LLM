import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Statik export: FastAPI bu çıktıyı servis eder. Çalışma anında tek süreç,
  // sıfır ağ isteği — offline garantisi bu satıra dayanıyor.
  // docs/FEATURE_SPEC.md ve PROJE_DURUMU.md'deki mimari kararla eşleşir.
  output: "export",

  // Next Image optimizasyonu statik export'ta çalışmaz (sunucu gerektirir).
  images: { unoptimized: true },
};

export default nextConfig;
