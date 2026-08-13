"use client"

import {
  ThemeProvider as NextThemesProvider,
  type ThemeProviderProps,
} from "next-themes"

/**
 * DESIGN_SYSTEM.md'nin light/dark temasını `next-themes` üzerinden yönetir.
 *
 * `attribute="class"` — `.dark` sınıfı `<html>`'e eklenir; app/globals.css
 * bu sınıfı `@custom-variant dark (&:is(.dark *))` ile okur.
 * `defaultTheme="system"` — ilk ziyarette işletim sistemi tercihi izlenir.
 *
 * `<html suppressHydrationWarning>` zaten app/layout.tsx'te kurulu (next-themes
 * bunu şart koşar, çünkü tema class'ı yalnızca istemci tarafında, ilk
 * render'dan sonra eklenir). Bu bileşen sadece Provider'ı sarar; layout.tsx'e
 * bağlamak entegrasyonun sorumluluğunda.
 */
function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  )
}

export { ThemeProvider }
