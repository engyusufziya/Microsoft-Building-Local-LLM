"use client"

import type { ArtifactDetail } from "@/lib/types"

import { MindMapView } from "./mindmap/mindmap-view"
import { QuizRunner } from "./quiz/quiz-runner"
import { ReportView } from "./report/report-view"

/**
 * Açık artefaktı `kind`'ına göre doğru görüntüleyiciye yönlendirir
 * (docs/FEATURE_SPEC.md §11.9 / §12.11).
 *
 * Neden `web/app/page.tsx`'te DEĞİL: `kind -> görüntüleyici` eşlemesi Studio'nun
 * kendi bilgisidir ve her yeni artefakt tipinde büyür; `page.tsx`
 * `frontend-muhendisi`'nin dosyası (AGENTS.md sahiplik haritası) ve Faz 2'den
 * beri orada tek satır duruyor. Bu bileşen o satırı sabit tutar.
 *
 * `switch` üç `kind` üzerinde TAMDIR (`ArtifactSummary.kind` kapalı bir birlik);
 * `default` dalı yazılmadı -- imkânsız senaryo için savunma kodu (AGENTS.md §2.2).
 */
export function ArtifactViewer({
  artifact,
  onClose,
}: {
  artifact: ArtifactDetail
  onClose: () => void
}) {
  switch (artifact.kind) {
    case "report":
      return <ReportView artifact={artifact} onClose={onClose} />
    case "mindmap":
      return <MindMapView artifact={artifact} onClose={onClose} />
    case "quiz":
      return <QuizRunner artifact={artifact} onClose={onClose} />
  }
}
