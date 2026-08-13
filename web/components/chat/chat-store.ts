"use client"

import * as React from "react"

import { ApiRequestError, streamChat, type ChatCallbacks } from "@/lib/api"
import type { ApiErrorBody, ChatRetrievalEvent } from "@/lib/types"

/**
 * Sohbet + Inspector ortak durumu.
 *
 * NEDEN CONTEXT DEĞİL, MODÜL DÜZEYİNDE STORE?
 * `ChatPanel` ve `RetrievalInspector` ağacın iki ayrı dalında duruyor
 * (DESIGN_SYSTEM.md §4: masaüstünde iki ayrı kolon, mobilde biri drawer
 * içinde) ve ikisini saran kabuk (`components/shell/app-shell.tsx`,
 * `app/page.tsx`) BAŞKA bir agent'ın dosyası. Provider gerektiren bir tasarım,
 * o dosyaya yazma hakkım olmadığı için entegrasyonun "provider eklemeyi
 * unutması" halinde çalışmaz hale gelirdi. Modül düzeyinde store +
 * `useSyncExternalStore` ile iki bileşen de nereye monte edilirse edilsin
 * aynı durumu görür; sıfır entegrasyon yükü.
 *
 * İkinci fayda: SSE callback'leri React render döngüsünün dışından gelir.
 * Harici store'a yazmak, effect içinde setState çağırmayı gerektirmez —
 * bu projenin `react-hooks/set-state-in-effect` kuralıyla doğal uyum.
 * (Aynı desen `lib/i18n/index.ts` ve `components/theme-toggle.tsx` içinde de
 * kullanılıyor.)
 *
 * Tek kullanıcılı, tek sohbetli yerel bir uygulama olduğu için tekil (modül
 * düzeyinde) durum doğru soyutlama; çoklu sohbet gerekirse buradaki `state`
 * bir Map'e çevrilir, dışa açılan API aynı kalır.
 */

// --------------------------------------------------------------------------- tipler

/**
 * Bir asistan mesajının nihai durumu. İlk üçü FEATURE_SPEC §3.2'deki üç
 * `reason` dalına birebir karşılık gelir; son ikisi ağ/akış hataları.
 */
export type MessageOutcome =
  | "streaming"
  /** `reason: null` — akan metin korunur, kaynaklar gösterilir. */
  | "answered"
  /** `reason: "below_threshold"` — hiç token akmadı, yerelleştirilmiş metin basılır. */
  | "below_threshold"
  /** `reason: "llm_refused"` — token aktı, metin yerelleştirilmişle DEĞİŞTİRİLİR. */
  | "llm_refused"
  /** Akış ortasında koptu: kısmi metin korunur + "tamamlanamadı" satırı (§5). */
  | "incomplete"
  /** Hiç token akmadan hata: hata kartı + tekrar dene. */
  | "failed"

export interface UserMessage {
  id: string
  role: "user"
  text: string
}

export interface AssistantMessage {
  id: string
  role: "assistant"
  /** Modelin GERÇEK çıktısı. Ret dallarında ekranda gösterilmez ama saklanır. */
  text: string
  outcome: MessageOutcome
  sources: string[]
  /** Bu mesaja ait retrieval anlık görüntüsü — Inspector bunu gösterir. */
  retrieval: ChatRetrievalEvent | null
  elapsedMs: number | null
  error: ApiErrorBody | null
}

export type ChatMessage = UserMessage | AssistantMessage

/** FEATURE_SPEC §1.2: "aranıyor" -> "üretiliyor" aşamalı göstergesi. */
export type ChatPhase = "idle" | "searching" | "generating"

export interface ChunkHighlight {
  messageId: string
  chunkIndex: number
  /** Aynı chip'e tekrar tıklandığında vurgunun yeniden tetiklenmesi için. */
  nonce: number
}

export interface ChatState {
  messages: ChatMessage[]
  phase: ChatPhase
  /** Inspector'ın gösterdiği mesaj; varsayılan olarak en son asistan mesajı. */
  selectedMessageId: string | null
  highlight: ChunkHighlight | null
  /** "Tekrar dene" için son sorulan soru. */
  lastQuestion: string | null
}

const INITIAL_STATE: ChatState = {
  messages: [],
  phase: "idle",
  selectedMessageId: null,
  highlight: null,
  lastQuestion: null,
}

// --------------------------------------------------------------------------- store çekirdeği

let state: ChatState = INITIAL_STATE
let listeners: Array<() => void> = []

function emit() {
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners = [...listeners, listener]
  return () => {
    listeners = listeners.filter((l) => l !== listener)
  }
}

function setState(next: (prev: ChatState) => ChatState) {
  state = next(state)
  emit()
}

/** Aktif sohbet durumunu okur. Hem ChatPanel hem RetrievalInspector kullanır. */
export function useChatState(): ChatState {
  return React.useSyncExternalStore(
    subscribe,
    () => state,
    () => INITIAL_STATE
  )
}

// --------------------------------------------------------------------------- transport

/**
 * Akış kaynağı. Varsayılan `lib/api.ts::streamChat`; testte/önizlemede
 * (`app/dev-chat`) sahte bir olay dizisiyle değiştirilebilir. Bu seam
 * sayesinde üç `reason` dalı da backend çalıştırmadan doğrulanabiliyor.
 */
export type ChatTransport = (
  question: string,
  callbacks: ChatCallbacks
) => Promise<void>

const defaultTransport: ChatTransport = (question, callbacks) =>
  streamChat(question, callbacks)

let transport: ChatTransport = defaultTransport

export function setChatTransport(next: ChatTransport | null): void {
  transport = next ?? defaultTransport
}

// --------------------------------------------------------------------------- yardımcılar

let idCounter = 0
function nextId(prefix: string): string {
  idCounter += 1
  return `${prefix}-${idCounter}`
}

function toErrorBody(error: unknown): ApiErrorBody {
  if (error instanceof ApiRequestError) {
    return { code: error.code, message: error.message }
  }
  return {
    code: "INTERNAL",
    message: error instanceof Error ? error.message : String(error),
  }
}

function mapAssistant(
  messages: ChatMessage[],
  id: string,
  update: (message: AssistantMessage) => AssistantMessage
): ChatMessage[] {
  return messages.map((message) =>
    message.role === "assistant" && message.id === id ? update(message) : message
  )
}

/** Inspector'ın göstereceği asistan mesajı (seçili yoksa en sonuncusu). */
export function selectedAssistant(current: ChatState): AssistantMessage | null {
  const assistants = current.messages.filter(
    (message): message is AssistantMessage => message.role === "assistant"
  )
  if (assistants.length === 0) return null
  if (current.selectedMessageId) {
    const match = assistants.find((m) => m.id === current.selectedMessageId)
    if (match) return match
  }
  return assistants[assistants.length - 1]
}

// --------------------------------------------------------------------------- vurgulama

/** FEATURE_SPEC §4.1: Vurgulu -> Dolu geçişi 1.5 sn sonra. */
export const HIGHLIGHT_DURATION_MS = 1500

let highlightTimer: ReturnType<typeof setTimeout> | null = null
let highlightNonce = 0

function clearHighlightTimer() {
  if (highlightTimer !== null) {
    clearTimeout(highlightTimer)
    highlightTimer = null
  }
}

// --------------------------------------------------------------------------- akış

/** Geç gelen callback'lerin eski bir isteğe yazmasını engeller. */
let activeRequest = 0

function runStream(question: string, assistantId: string) {
  const requestId = ++activeRequest
  const isStale = () => requestId !== activeRequest

  const callbacks: ChatCallbacks = {
    onRetrieval(event) {
      if (isStale()) return
      // Inspector cevaptan ÖNCE dolar (§1.2 kritik zamanlama): done beklenmez.
      setState((prev) => ({
        ...prev,
        phase: "generating",
        messages: mapAssistant(prev.messages, assistantId, (message) => ({
          ...message,
          retrieval: event,
        })),
      }))
    },
    onToken(event) {
      if (isStale()) return
      setState((prev) => ({
        ...prev,
        messages: mapAssistant(prev.messages, assistantId, (message) => ({
          ...message,
          text: message.text + event.text,
        })),
      }))
    },
    onDone(event) {
      if (isStale()) return
      setState((prev) => ({
        ...prev,
        phase: "idle",
        messages: mapAssistant(prev.messages, assistantId, (message) => ({
          ...message,
          // Üç dal, üç farklı UI davranışı — FEATURE_SPEC §3.2.
          outcome:
            event.reason === "below_threshold"
              ? "below_threshold"
              : event.reason === "llm_refused"
                ? "llm_refused"
                : "answered",
          // `llm_refused`/`below_threshold` kaynak GÖSTERMEZ; backend zaten boş
          // dizi yolluyor ama niyeti burada da açık tutuyoruz.
          sources: event.reason === null ? event.sources : [],
          elapsedMs: event.elapsed_ms,
        })),
      }))
    },
    onError(error) {
      if (isStale()) return
      finishWithError(assistantId, error)
    },
  }

  transport(question, callbacks)
    .then(() => {
      if (isStale()) return
      // `done` gelmeden akış kapandıysa (bağlantı koptu) kısmi metni koru.
      setState((prev) => ({
        ...prev,
        phase: "idle",
        messages: mapAssistant(prev.messages, assistantId, (message) =>
          message.outcome === "streaming"
            ? { ...message, outcome: message.text ? "incomplete" : "failed" }
            : message
        ),
      }))
    })
    .catch((error: unknown) => {
      if (isStale()) return
      finishWithError(assistantId, toErrorBody(error))
    })
}

function finishWithError(assistantId: string, error: ApiErrorBody) {
  setState((prev) => ({
    ...prev,
    phase: "idle",
    messages: mapAssistant(prev.messages, assistantId, (message) => ({
      ...message,
      // §5 [!tip]: 2. saniyede kopan bir akışta üretilen metin SİLİNMEZ.
      outcome: message.text ? "incomplete" : "failed",
      error,
    })),
  }))
}

function startTurn(question: string, replaceLastAssistant: boolean) {
  const assistantId = nextId("assistant")
  clearHighlightTimer()

  setState((prev) => {
    const base = replaceLastAssistant
      ? prev.messages.filter(
          (message, index) =>
            !(message.role === "assistant" && index === prev.messages.length - 1)
        )
      : [...prev.messages, { id: nextId("user"), role: "user", text: question } as UserMessage]

    const assistant: AssistantMessage = {
      id: assistantId,
      role: "assistant",
      text: "",
      outcome: "streaming",
      sources: [],
      retrieval: null,
      elapsedMs: null,
      error: null,
    }

    return {
      ...prev,
      messages: [...base, assistant],
      phase: "searching",
      selectedMessageId: assistantId,
      highlight: null,
      lastQuestion: question,
    }
  })

  runStream(question, assistantId)
}

// --------------------------------------------------------------------------- dışa açılan eylemler

export const chatActions = {
  /** Soru sorar. Akış sürerken gelen çağrılar yok sayılır (tek kilit, §7). */
  ask(question: string): void {
    const trimmed = question.trim()
    if (!trimmed || state.phase !== "idle") return
    startTurn(trimmed, false)
  },

  /**
   * Son soruyu tekrar sorar. Kullanıcı balonu korunur, başarısız asistan
   * mesajı yerine yenisi konur — sohbet geçmişinde tekrar eden soru olmaz.
   */
  retry(): void {
    if (state.phase !== "idle" || !state.lastQuestion) return
    startTurn(state.lastQuestion, true)
  },

  /** Inspector'ın hangi mesajın retrieval'ını gösterdiğini değiştirir. */
  selectMessage(messageId: string): void {
    setState((prev) => ({ ...prev, selectedMessageId: messageId, highlight: null }))
  },

  /**
   * FEATURE_SPEC §1.3: SourceChip tıklandığında Inspector ilgili ChunkCard'a
   * kayar ve kart 1.5 sn vurgulanır (Dolu -> Vurgulu -> Dolu).
   */
  focusSource(messageId: string, citation: string): void {
    const message = state.messages.find(
      (m): m is AssistantMessage => m.role === "assistant" && m.id === messageId
    )
    const chunkIndex =
      message?.retrieval?.hits.findIndex((hit) => hit.citation === citation) ?? -1
    if (chunkIndex < 0) {
      setState((prev) => ({ ...prev, selectedMessageId: messageId }))
      return
    }

    clearHighlightTimer()
    highlightNonce += 1
    setState((prev) => ({
      ...prev,
      selectedMessageId: messageId,
      highlight: { messageId, chunkIndex, nonce: highlightNonce },
    }))

    highlightTimer = setTimeout(() => {
      highlightTimer = null
      setState((prev) => (prev.highlight ? { ...prev, highlight: null } : prev))
    }, HIGHLIGHT_DURATION_MS)
  },

  /** Sohbeti sıfırlar (belge silindiğinde / önizleme sayfasında kullanılır). */
  reset(): void {
    activeRequest += 1
    clearHighlightTimer()
    state = INITIAL_STATE
    emit()
  },
}
