"use client"

import * as React from "react"

/**
 * i18n altyapısı — DESIGN_SYSTEM.md §7.
 *
 * Namespace başına bir dosya: common.ts (design-system), sidebar.ts
 * (frontend-kb), chat.ts (frontend-chat), metrics.ts (metrics-ui). Her
 * dosya `{ tr, en }` çiftleri içeren düz bir `as const` obje export eder.
 *
 * Bilinçli tasarım kararı: bu dosya sidebar/chat/metrics namespace'lerini
 * İMPORT ETMEZ ve tek bir dev merge nesnesi üretmez. Bunun yerine `useT()`
 * herhangi bir Namespace şekliyle çalışan generic bir çözümleyicidir — her
 * feature alanı kendi namespace dosyasını kendi bileşeninde import edip
 * `useT(sidebar)` gibi çağırır. Aksi halde index.ts, dört ayrı agent'ın
 * aynı anda düzenlemesi gereken paylaşımlı bir dosyaya dönüşür; bu da
 * §7'nin "çakışmayı yapısal olarak imkânsız kılar" hedefiyle çelişir.
 */

export type Locale = "tr" | "en"

/**
 * Bir çeviri girdisi: sabit metin ya da parametre alan bir fonksiyon.
 * Çoğul/sayı içeren metinler string birleştirme ile değil, fonksiyonla
 * kurulur (DESIGN_SYSTEM.md §7 adlandırma kuralı).
 */
export type TranslationEntry = string | ((...args: never[]) => string)

/** Bir namespace dosyasının şekli: anahtar başına iki dil yan yana. */
export type Namespace = Record<string, Record<Locale, TranslationEntry>>

/** Bir namespace'in aktif dile çözümlenmiş hali (örn. useT(common).retry). */
export type ResolvedNamespace<N extends Namespace> = {
  [K in keyof N]: N[K][Locale]
}

/**
 * Örnek — boş bir namespace ile deseni göstermek için:
 *
 *   const example = {
 *     placeholder: { tr: "", en: "" },
 *   } satisfies Namespace
 *
 * `useT(example)` bu şekle uyan HERHANGİ bir namespace objesiyle çalışır;
 * sidebar.ts/chat.ts/metrics.ts eklendiğinde bu dosyaya dokunmadan aynı
 * şekilde kullanılabilirler.
 */

function resolveNamespace<N extends Namespace>(
  namespace: N,
  locale: Locale
): ResolvedNamespace<N> {
  const resolved = {} as ResolvedNamespace<N>
  for (const key of Object.keys(namespace) as (keyof N)[]) {
    resolved[key] = namespace[key][locale] as ResolvedNamespace<N>[keyof N]
  }
  return resolved
}

const STORAGE_KEY = "rag-assistant:locale"
const DEFAULT_LOCALE: Locale = "tr"

interface LanguageContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
}

const LanguageContext = React.createContext<LanguageContextValue | null>(null)

function readStoredLocale(): Locale | null {
  if (typeof window === "undefined") return null
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === "tr" || stored === "en" ? stored : null
}

// localStorage senkronizasyonu useSyncExternalStore ile yapılır (modül
// düzeyinde küçük bir store). Bunun tercih edilme nedeni: klasik
// useState+useEffect+setState deseni SSR/hydration'da bir render'lık
// gecikmeye ve bu projenin eslint kuralının (react-hooks/set-state-in-effect)
// reddettiği "effect içinde setState" çağrısına yol açardı.
// `currentLocale` provider örnekleri arasında paylaşılır; pratikte tek bir
// kök LanguageProvider olacağı için bu sorun yaratmaz.
let currentLocale: Locale | null = null
let listeners: Array<() => void> = []

function emitChange() {
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners = [...listeners, listener]
  return () => {
    listeners = listeners.filter((l) => l !== listener)
  }
}

function writeLocale(next: Locale) {
  currentLocale = next
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, next)
  }
  emitChange()
}

export interface LanguageProviderProps {
  children: React.ReactNode
  /** Başlangıç dili — localStorage'da tercih yoksa (veya SSR'da) kullanılır. */
  defaultLocale?: Locale
}

/**
 * Aktif dili React context'inde tutar ve localStorage'a yazar. `useT()` ve
 * `useLocale()` bu Provider'ın altında kullanılmalı — layout.tsx'e bağlamak
 * entegrasyonun sorumluluğunda (bkz. ThemeProvider ile aynı desen).
 */
function LanguageProvider({
  children,
  defaultLocale = DEFAULT_LOCALE,
}: LanguageProviderProps) {
  const getSnapshot = React.useCallback((): Locale => {
    if (currentLocale === null) {
      currentLocale = readStoredLocale() ?? defaultLocale
    }
    return currentLocale
  }, [defaultLocale])

  const getServerSnapshot = React.useCallback(
    (): Locale => defaultLocale,
    [defaultLocale]
  )

  const locale = React.useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  )

  const setLocale = React.useCallback((next: Locale) => {
    writeLocale(next)
  }, [])

  const value = React.useMemo(
    () => ({ locale, setLocale }),
    [locale, setLocale]
  )

  return React.createElement(LanguageContext.Provider, { value }, children)
}

/** Aktif dili ve değiştirme fonksiyonunu döndürür (örn. bir dil seçici için). */
function useLocale(): LanguageContextValue {
  const ctx = React.useContext(LanguageContext)
  if (!ctx) {
    throw new Error("useLocale()/useT() bir LanguageProvider içinde kullanılmalı.")
  }
  return ctx
}

/**
 * Bir namespace objesini aktif dile çözümler.
 *
 * Kullanım:
 *   import { common } from "@/lib/i18n/common"
 *   const t = useT(common)
 *   t.retry            // "Tekrar dene" | "Retry"
 *   t.pagesSkipped(3)  // örnek: sayı alan bir fonksiyon girdisi
 */
function useT<N extends Namespace>(namespace: N): ResolvedNamespace<N> {
  const { locale } = useLocale()
  return React.useMemo(
    () => resolveNamespace(namespace, locale),
    [namespace, locale]
  )
}

export { LanguageProvider, useLocale, useT }
