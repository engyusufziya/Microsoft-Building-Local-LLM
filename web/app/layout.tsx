import type { Metadata } from "next";
import { ThemeProvider } from "@/components/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { LanguageProvider } from "@/lib/i18n";
import { archivo, jetbrainsMono } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local RAG Assistant",
  description: "Offline document Q&A powered by Foundry Local",
};

/**
 * Provider sırası önemli:
 *  - ThemeProvider `<html>`'e `.dark` sınıfını ekler (globals.css onu okur).
 *  - LanguageProvider `useT()` kullanan HER bileşenin üstünde olmalı;
 *    tooltip içerikleri de çeviriden geldiği için TooltipProvider'ın da
 *    üstünde duruyor.
 *
 * `suppressHydrationWarning`: next-themes tema sınıfını yalnızca istemcide
 * ekler, sunucu HTML'iyle ilk render arasında fark oluşur; bu uyarı beklenen
 * farkı susturur (next-themes'in şart koştuğu kurulum).
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="tr"
      suppressHydrationWarning
      className={`${archivo.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <LanguageProvider>
            <TooltipProvider delay={200}>{children}</TooltipProvider>
          </LanguageProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
