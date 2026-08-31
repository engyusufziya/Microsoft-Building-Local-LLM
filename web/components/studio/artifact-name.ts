"use client"

import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import type { ArtifactSummary } from "@/lib/types"
import { useKnowledge } from "@/components/sidebar"

/**
 * Artefaktın KULLANICIYA GÖSTERİLEN adı — arayüzde türetilir, backend'den
 * gelmez.
 *
 * NEDEN: `artifacts.title` alanı motorda TÜRKÇE LİTERAL olarak üretiliyor
 * (`rag/artifacts/report.py` → "Korpus Raporu" vb.) ve doğrudan basılıyordu.
 * İki ayrı sorun:
 *
 *  1. **i18n ihlali.** `DESIGN_SYSTEM §7`'nin [!warning] kuralı, backend'den
 *     gelen ham Türkçe metnin basılmasını YASAKLIYOR; `stage` ve hata
 *     `message` alanları bu kurala uyuyor (upload-stage.ts / error-messages.ts)
 *     ama artefakt başlıkları kaçmıştı. Arayüz İngilizce'ye alındığında
 *     "Korpus Raporu" yazmaya devam ediyordu.
 *  2. **Jargon.** "Korpus" bir mühendislik terimi; kullanıcı "tüm belgeler"
 *     der. Kapsam zaten `scope` alanında yapısal olarak duruyor, dolayısıyla
 *     adı ondan türetmek hem doğru hem yerelleştirilebilir.
 *
 * Motor tarafına DOKUNULMADI (§9–12 donduruldu): `title` alanı yerinde
 * duruyor ve dışa aktarımda kullanılmaya devam ediyor; değişen yalnızca
 * arayüzün ne bastığı.
 */
export function useArtifactName(artifact: ArtifactSummary): string {
  const t = useT(studio)
  const { documents } = useKnowledge()

  const kind = {
    report: t.kindReport,
    mindmap: t.kindMindMap,
    quiz: t.kindQuiz,
  }[artifact.kind]

  if (artifact.scope === "corpus") return `${kind} · ${t.scopeCorpus}`

  // Belge kapsamı: adı listeden çözülür. Belge silinmişse (ya da liste henüz
  // yüklenmediyse) kapsam adı yerine yalnızca tip yazılır -- silinmiş bir
  // belgenin adını uydurmaktansa eksik bırakmak dürüst olan.
  const filename =
    documents?.find((document) => document.id === artifact.document_id)?.filename
  return filename === undefined ? kind : `${kind} · ${filename}`
}
