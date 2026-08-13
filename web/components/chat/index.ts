/**
 * `frontend-chat`'in dışa açtığı yüzey. Entegrasyon (app-shell / page)
 * yalnızca buradan import eder; iç dosyalar (markdown-content, code-block,
 * empty-state …) uygulama detayıdır.
 *
 * Provider GEREKMEZ: durum modül düzeyinde bir store'da tutulur
 * (bkz. chat-store.ts başındaki gerekçe), `ChatPanel` ve
 * `RetrievalInspector` ağacın herhangi iki yerine monte edilebilir.
 */
export { ChatPanel, type ChatPanelProps, type ChatLockReason } from "./chat-panel"
export { ChatInput, type ChatInputProps } from "./chat-input"
export { MessageList, type MessageListProps } from "./message-list"
export { StreamingText, type StreamingTextProps } from "./streaming-text"
export { SourceChips, type SourceChipsProps } from "./source-chips"
export { ThinkingIndicator, type ThinkingIndicatorProps } from "./thinking-indicator"
export { ChatEmptyState, type ChatEmptyStateProps } from "./empty-state"
export {
  chatActions,
  useChatState,
  setChatTransport,
  type ChatTransport,
  type ChatMessage,
  type ChatPhase,
  type AssistantMessage,
  type UserMessage,
  type MessageOutcome,
} from "./chat-store"
