"use client"

import * as React from "react"

import type { DocumentInfo, HealthResponse } from "@/lib/types"

import { toFailure, type Failure } from "./error-messages"
import { defaultKnowledgeSource, type KnowledgeSource } from "./knowledge-source"

/**
 * Model warmup'ı beklerken `/api/health` yoklama aralığı.
 * FEATURE_SPEC §7: warmup ~6.4 GB model yüklüyor, dakikalar sürebilir;
 * `status: "ready"` görülür görülmez yoklama durur.
 */
const HEALTH_POLL_MS = 5000

export interface KnowledgeSnapshot {
  /** `null` = ilk istek henüz bitmedi ya da başarısız oldu. */
  documents: DocumentInfo[] | null
  documentsLoading: boolean
  documentsFailure: Failure | null
  health: HealthResponse | null
  healthFailure: Failure | null
  deletingFilename: string | null
  /** Hangi belgenin silinemediği de taşınır — hata doğru karta gider. */
  deleteFailure: { filename: string; failure: Failure } | null
}

export interface KnowledgeState extends KnowledgeSnapshot {
  refreshDocuments: () => Promise<void>
  /** Yükleme/silme sonrası: liste + sistem durumu birlikte tazelenir. */
  refreshAll: () => Promise<void>
  /** Başarılıysa `true` — onay diyaloğu buna göre kapanır. */
  removeDocument: (filename: string) => Promise<boolean>
}

const INITIAL_SNAPSHOT: KnowledgeSnapshot = {
  documents: null,
  documentsLoading: true,
  documentsFailure: null,
  health: null,
  healthFailure: null,
  deletingFilename: null,
  deleteFailure: null,
}

/**
 * Belge listesi + sistem durumu için React DIŞI bir store.
 *
 * Neden `useState` + `useEffect` değil: bu projede
 * `react-hooks/set-state-in-effect` açık ve kural interprocedural —
 * effect'ten çağrılan bir fonksiyon (async olsa bile) setState yapıyorsa
 * hata veriyor. Kuralın kendi önerdiği çıkış yolu harici store +
 * `useSyncExternalStore`; aynı desen `lib/i18n/index.ts` ve
 * `components/theme-toggle.tsx` içinde de kullanılıyor. Burada durum
 * React'in dışında tutulduğu için effect yalnızca abone olur/başlatır,
 * hiçbir setState çağırmaz.
 */
class KnowledgeStore {
  private snapshot: KnowledgeSnapshot = INITIAL_SNAPSHOT
  private listeners = new Set<() => void>()
  private activeSubscribers = 0
  private healthTimer: number | null = null
  private stopped = true

  constructor(private readonly source: KnowledgeSource) {}

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  getSnapshot = (): KnowledgeSnapshot => this.snapshot

  /** Statik export'ta sunucuda veri yok; ilk anlık görüntü sabittir. */
  getServerSnapshot = (): KnowledgeSnapshot => INITIAL_SNAPSHOT

  private update(changes: Partial<KnowledgeSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...changes }
    for (const listener of this.listeners) listener()
  }

  /**
   * Bileşen bağlandığında çağrılır; ilk yüklemeyi yapar ve modeller hazır
   * olana kadar health yoklamasını sürdürür. Dönen fonksiyon zamanlayıcıyı
   * durdurur (StrictMode'un çift mount'u için sayaçla korunur).
   */
  start = (): (() => void) => {
    this.activeSubscribers += 1
    if (this.activeSubscribers === 1) {
      this.stopped = false
      void this.loadDocuments()
      void this.loadHealth()
    }
    return () => {
      this.activeSubscribers -= 1
      if (this.activeSubscribers === 0) {
        this.stopped = true
        if (this.healthTimer !== null) {
          window.clearTimeout(this.healthTimer)
          this.healthTimer = null
        }
      }
    }
  }

  private loadDocuments = async (): Promise<void> => {
    try {
      const documents = await this.source.listDocuments()
      this.update({ documents, documentsFailure: null, documentsLoading: false })
    } catch (error) {
      this.update({
        documentsFailure: toFailure(error),
        documentsLoading: false,
      })
    }
  }

  private loadHealth = async (): Promise<void> => {
    try {
      const health = await this.source.getHealth()
      this.update({ health, healthFailure: null })
    } catch (error) {
      this.update({ healthFailure: toFailure(error) })
    } finally {
      this.scheduleHealthPoll()
    }
  }

  private scheduleHealthPoll(): void {
    if (this.stopped) return
    if (this.snapshot.health?.status === "ready") return
    if (this.healthTimer !== null) window.clearTimeout(this.healthTimer)
    this.healthTimer = window.setTimeout(() => {
      this.healthTimer = null
      void this.loadHealth()
    }, HEALTH_POLL_MS)
  }

  refreshDocuments = async (): Promise<void> => {
    this.update({ documentsLoading: true })
    await this.loadDocuments()
  }

  refreshAll = async (): Promise<void> => {
    await Promise.all([this.loadDocuments(), this.loadHealth()])
  }

  removeDocument = async (filename: string): Promise<boolean> => {
    this.update({ deletingFilename: filename, deleteFailure: null })
    try {
      await this.source.deleteDocument(filename)
      // FEATURE_SPEC §1.4: silme sonrası liste tazelenir (chunk'lar CASCADE
      // ile gittiği için korpus sayaçları da değişir).
      await this.refreshAll()
      this.update({ deletingFilename: null })
      return true
    } catch (error) {
      this.update({
        deletingFilename: null,
        deleteFailure: { filename, failure: toFailure(error) },
      })
      return false
    }
  }
}

/**
 * Kaynak başına TEK store — bileşen ağacındaki her tüketici aynı örneği
 * paylaşır.
 *
 * Neden önemli: mobilde sidebar bir `Sheet` drawer'ı ve drawer kapalıyken
 * mount EDİLMEZ. Belge sayısı ise sohbetin girdi kilidi için gerekiyor
 * (FEATURE_SPEC §5: "Belge yok → girdi kilitli"). Entegrasyon `page.tsx`
 * içinde `useKnowledge()` çağırdığında aynı store'a bağlanır: veri drawer
 * açılmasa da yüklenir, drawer açıldığında sidebar hazır listeyi bulur ve
 * ikinci bir istek atılmaz.
 */
const STORES = new WeakMap<KnowledgeSource, KnowledgeStore>()

function getStore(source: KnowledgeSource): KnowledgeStore {
  let store = STORES.get(source)
  if (store === undefined) {
    store = new KnowledgeStore(source)
    STORES.set(source, store)
  }
  return store
}

/**
 * Sidebar'ın tek durum sahibi.
 *
 * `source` KARARLI bir referans olmalı (modül sabiti ya da `useMemo`);
 * her render'da yeni bir nesne geçilirse yeni bir store kurulur.
 */
export function useKnowledge(
  source: KnowledgeSource = defaultKnowledgeSource
): KnowledgeState {
  const store = React.useMemo(() => getStore(source), [source])

  const snapshot = React.useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot
  )

  React.useEffect(() => store.start(), [store])

  return {
    ...snapshot,
    refreshDocuments: store.refreshDocuments,
    refreshAll: store.refreshAll,
    removeDocument: store.removeDocument,
  }
}
