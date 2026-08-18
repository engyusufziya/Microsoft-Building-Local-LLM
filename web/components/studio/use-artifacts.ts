"use client"

import * as React from "react"

import {
  ApiRequestError,
  createArtifact,
  getArtifact,
  listArtifacts,
} from "@/lib/api"
import type {
  ApiErrorBody,
  ArtifactCreateRequest,
  ArtifactDetail,
  ArtifactSummary,
} from "@/lib/types"

/** Üretilebilir artefakt tipleri — üçünün de kayıtlı üreticisi var (§12.1). */
export type ArtifactKind = ArtifactCreateRequest["kind"]

/**
 * Studio'nun tek durum sahibi — docs/FEATURE_SPEC.md §10.11/§10.12, §11.9,
 * §12.11.
 *
 * `use-knowledge.ts` ile AYNI desen (React DIŞI store + useSyncExternalStore):
 * bu projede `react-hooks/set-state-in-effect` açık ve kural
 * interprocedural — effect'ten çağrılan bir async fonksiyon setState
 * yapamıyor.
 *
 * Neden PAYLAŞILAN bir store: üretim düğmesi sağ paneldeki `StudioPanel`'de,
 * raporun kendisi ise `<main>`'de render ediliyor (§10.12). İkisi kardeş
 * bileşen; ortak durum ya köke prop olarak taşınacaktı ya da buraya. Ayrıca
 * sağ panel mobilde bir drawer ve kapalıyken UNMOUNT oluyor — üretim akışı
 * drawer kapanınca kesilmemeli.
 */

export interface ArtifactsSnapshot {
  /** `null` = ilk istek henüz bitmedi. */
  artifacts: ArtifactSummary[] | null
  listError: ApiErrorBody["code"] | null
  /** Üretimi süren tip; `null` = üretim yok. Tek seferde tek üretim (§12.11). */
  generatingKind: ArtifactKind | null
  /** 0–100 TAM SAYI — /api/documents'ın 0.0–1.0 ölçeğiyle KARIŞTIRILMAZ (§9.5). */
  pct: number
  /** `stage` olayının etiketi ya da `progress` olayının detayı. */
  progressDetail: string | null
  generateError: ApiErrorBody["code"] | null
  /** Açık rapor; `null` = sohbet görünümü. */
  open: ArtifactDetail | null
  openLoading: boolean
  openError: ApiErrorBody["code"] | null
}

const INITIAL: ArtifactsSnapshot = {
  artifacts: null,
  listError: null,
  generatingKind: null,
  pct: 0,
  progressDetail: null,
  generateError: null,
  open: null,
  openLoading: false,
  openError: null,
}

function errorCode(error: unknown): ApiErrorBody["code"] {
  return error instanceof ApiRequestError ? error.code : "INTERNAL"
}

class ArtifactsStore {
  private snapshot: ArtifactsSnapshot = INITIAL
  private listeners = new Set<() => void>()
  private started = false

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  getSnapshot = (): ArtifactsSnapshot => this.snapshot

  /** Statik export'ta sunucuda veri yok; ilk anlık görüntü sabittir. */
  getServerSnapshot = (): ArtifactsSnapshot => INITIAL

  private update(changes: Partial<ArtifactsSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...changes }
    for (const listener of this.listeners) listener()
  }

  /** İlk bağlanan tüketici listeyi bir kez yükler (Faz 1'in aksine liste artık dolabilir). */
  start = (): void => {
    if (this.started) return
    this.started = true
    void this.refresh()
  }

  refresh = async (): Promise<void> => {
    try {
      // `kind` süzgeci YOK: Faz 3/4'ten sonra liste üç tipi birden taşır.
      this.update({ artifacts: await listArtifacts(), listError: null })
    } catch (error) {
      this.update({ listError: errorCode(error) })
    }
  }

  /**
   * Tek seferde TEK üretim: backend zaten model kilidini üretim boyunca
   * tutuyor (§9.8), ikinci bir istek kilidin arkasında bekler ve kullanıcıya
   * donmuş gibi görünürdü.
   */
  generate = async (kind: ArtifactKind): Promise<void> => {
    if (this.snapshot.generatingKind !== null) return
    this.update({ generatingKind: kind, pct: 0, progressDetail: null, generateError: null })

    let failed = false
    try {
      await createArtifact(
        { kind, scope: "corpus" },
        {
          onStage: (event) => this.update({ progressDetail: event.label }),
          onProgress: (event) =>
            this.update({ pct: event.pct, progressDetail: event.detail }),
          onComplete: (event) => {
            void this.openArtifact(event.artifact_id)
          },
          onError: (error) => {
            failed = true
            this.update({ generateError: error.code })
          },
        }
      )
    } catch (error) {
      failed = true
      this.update({ generateError: errorCode(error) })
    }

    this.update({ generatingKind: null, progressDetail: null, pct: failed ? 0 : 100 })
    await this.refresh()
  }

  openArtifact = async (artifactId: number): Promise<void> => {
    this.update({ openLoading: true, openError: null })
    try {
      this.update({ open: await getArtifact(artifactId), openLoading: false })
    } catch (error) {
      this.update({ openLoading: false, openError: errorCode(error) })
    }
  }

  close = (): void => {
    this.update({ open: null, openError: null })
  }
}

const store = new ArtifactsStore()

export function useArtifacts() {
  const snapshot = React.useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot
  )

  React.useEffect(() => {
    store.start()
  }, [])

  return {
    ...snapshot,
    refresh: store.refresh,
    generate: store.generate,
    openArtifact: store.openArtifact,
    close: store.close,
  }
}
