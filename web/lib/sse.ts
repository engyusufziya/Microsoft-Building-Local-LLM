/**
 * Genel amaçlı SSE (Server-Sent Events) çerçeve ayrıştırıcı.
 *
 * Not: docs/DESIGN_SYSTEM.md §6'nın dosya sahipliği matrisinde bu dosya
 * frontend-chat'e ayrılmıştı. Entegrasyon sırasında (Wave 2 başlamadan önce)
 * bana taşındı çünkü hem sohbet akışı (POST /api/chat) hem belge yükleme
 * ilerlemesi (POST /api/documents) AYNI wire format'ı kullanıyor
 * (backend/sse.py) -- iki agent'ın aynı düşük seviye ayrıştırıcıyı ayrı ayrı
 * yazması gereksiz tekrar ve olası tutarsızlık riski taşırdı. frontend-chat
 * ve frontend-kb bunun üzerine kendi ÖZELLİĞE ÖZGÜ tüketim mantıklarını
 * (useChatStream, useUploadStream gibi) kurar.
 *
 * Wire format (backend/sse.py::sse_event, dondurulmuş):
 *
 *     event: <isim>
 *     data: <JSON>
 *     <boş satır>
 *
 * `data:` alanı SSE spesifikasyonunda birden çok satıra yayılabilir (satırlar
 * \n ile birleştirilir); backend'imiz her zaman tek satır JSON gönderir ama
 * ayrıştırıcı spesifikasyona sadık kalır.
 */

export interface SSEFrame {
  event: string
  /** Ham JSON string; çağıran taraf kendi olay tipine göre parse eder. */
  data: string
}

function parseFrame(raw: string): SSEFrame | null {
  const dataLines: string[] = []
  let event = "message" // SSE varsayılanı; backend'imiz her zaman event: gönderir.

  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim()
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart())
    }
    // Diğer alanlar (id:, retry:, yorum satırı `:`) backend'imizde kullanılmıyor.
  }

  if (dataLines.length === 0) return null
  return { event, data: dataLines.join("\n") }
}

/**
 * Bir `fetch()` yanıtının gövdesini SSE çerçevelerine ayrıştırır.
 *
 * Kullanım:
 *   const res = await fetch("/api/chat", { method: "POST", ... })
 *   for await (const frame of parseSSEStream(res)) {
 *     if (frame.event === "token") { const { text } = JSON.parse(frame.data) }
 *   }
 */
export async function* parseSSEStream(response: Response): AsyncGenerator<SSEFrame> {
  if (!response.body) {
    throw new Error("Yanıt gövdesi yok -- SSE akışı okunamıyor.")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Çerçeveler boş satırla ayrılır. Son (tamamlanmamış) parçayı buffer'da
      // bırak -- bir sonraki chunk'la birleşecek.
      let separatorIndex: number
      while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawFrame = buffer.slice(0, separatorIndex)
        buffer = buffer.slice(separatorIndex + 2)
        const frame = parseFrame(rawFrame)
        if (frame) yield frame
      }
    }

    // Akış bitti ama buffer'da boş satırla bitmeyen bir çerçeve kaldıysa
    // (bağlantı düzgün kapandıysa nadir, ama savunmacı davran).
    const trailing = parseFrame(buffer)
    if (trailing) yield trailing
  } finally {
    reader.releaseLock()
  }
}
