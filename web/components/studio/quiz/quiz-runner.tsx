"use client"

import * as React from "react"
import { CheckIcon, DownloadIcon, PrinterIcon, XIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import { ApiRequestError, artifactExportUrl, submitQuizAttempt } from "@/lib/api"
import type {
  ApiErrorBody,
  ArtifactDetail,
  AttemptResult,
  QuizAnswerResult,
  QuizDroppedQuestion,
  QuizQuestion,
} from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import { asQuizPayload, choiceLabel, typeLabel } from "./quiz-payload"

/**
 * Quiz çalıştırıcı — docs/FEATURE_SPEC.md §12.11.
 *
 * Puanlama İSTEMCİDE YAPILMAZ: cevap anahtarı payload'da gelse bile
 * `short_answer` benzerliği embedding modeli gerektirir ve iki ayrı puanlama
 * yolu iki doğruluk kaynağı olurdu (§12.10). Sonuç `POST /api/quiz/{id}/attempt`
 * ile gelir.
 *
 * İki kural bu bileşende görünür:
 *  1. `short_answer` DOĞRU/YANLIŞ olarak işaretlenmez — benzerlik skoru ve
 *     kaynak gösterilir, kullanıcı kendi değerlendirmesini yapar (§12.8).
 *  2. Toplam puan yalnızca kesin puanlanabilen sorulardan hesaplanır ve bu
 *     etiketle açıkça söylenir.
 */

export interface QuizRunnerProps {
  artifact: ArtifactDetail
  onClose: () => void
  className?: string
}

export function QuizRunner({ artifact, onClose, className }: QuizRunnerProps) {
  const t = useT(studio)
  const payload = asQuizPayload(artifact.payload)

  const [answers, setAnswers] = React.useState<Record<string, string>>({})
  const [result, setResult] = React.useState<AttemptResult | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<ApiErrorBody["code"] | null>(null)
  const startedAt = React.useRef(new Date().toISOString())

  if (payload === null) return null

  const resultById = new Map((result?.results ?? []).map((r) => [r.question_id, r]))

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      setResult(
        await submitQuizAttempt(artifact.id, {
          answers,
          started_at: startedAt.current,
        })
      )
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.code : "INTERNAL")
    }
    setSubmitting(false)
  }

  const retry = () => {
    setAnswers({})
    setResult(null)
    setError(null)
    startedAt.current = new Date().toISOString()
  }

  const errorText = (code: ApiErrorBody["code"] | null): string | null => {
    if (code === null) return null
    if (code === "MODEL_WARMING") return t.errorModelWarming
    return t.errorGeneric
  }

  return (
    <div
      data-print="root"
      data-slot="quiz-runner"
      className={cn("flex h-full min-h-0 flex-col overflow-y-auto", className)}
    >
      <header className="flex flex-col gap-3 border-b border-border px-5 py-4">
        <div className="flex items-start gap-2">
          <h1 className="flex-1 text-h1 font-semibold text-text-primary">
            {artifact.title}
          </h1>
          <div data-print="hide" className="flex shrink-0 items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              render={
                <a href={artifactExportUrl(artifact.id)} download aria-label={t.exportMarkdown} />
              }
            >
              <DownloadIcon aria-hidden="true" />
              {t.exportMarkdown}
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <PrinterIcon aria-hidden="true" />
              {t.print}
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t.closeArtifact}
              onClick={onClose}
            >
              <XIcon aria-hidden="true" />
            </Button>
          </div>
        </div>
        <dl className="flex flex-wrap items-center gap-x-6 gap-y-1">
          <dd className="text-caption text-text-secondary">
            {t.quizQuestionCount(payload.questions.length)}
          </dd>
          <div className="flex items-baseline gap-1.5">
            <Tooltip>
              <TooltipTrigger
                render={<dt className="cursor-default text-caption text-text-tertiary" />}
              >
                {t.fidelityLabel}
              </TooltipTrigger>
              <TooltipContent>{t.fidelityHint}</TooltipContent>
            </Tooltip>
            <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
              {artifact.fidelity_score === null ? "—" : artifact.fidelity_score.toFixed(2)}
            </dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-caption text-text-tertiary">{t.droppedCountLabel}</dt>
            <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
              {artifact.dropped_count}
            </dd>
          </div>
        </dl>
        <p className="text-caption text-text-tertiary">{t.quizIntro}</p>
        {result !== null && <ScoreSummary result={result} />}
      </header>

      <ol aria-label={t.quizAria} className="flex flex-col gap-4 px-5 py-5">
        {payload.questions.length === 0 && (
          <p className="text-body-sm text-text-secondary">{t.quizNoQuestions}</p>
        )}
        {payload.questions.map((question, index) => (
          <QuestionCard
            key={question.id}
            index={index}
            question={question}
            value={answers[question.id] ?? ""}
            onChange={(value) =>
              setAnswers((current) => ({ ...current, [question.id]: value }))
            }
            result={resultById.get(question.id) ?? null}
          />
        ))}
      </ol>

      <div data-print="hide" className="flex flex-col gap-2 px-5 pb-5">
        {errorText(error) !== null && (
          <p role="alert" className="text-body-sm text-danger">
            {errorText(error)}
          </p>
        )}
        {result === null ? (
          <Button
            type="button"
            onClick={() => void submit()}
            disabled={submitting || payload.questions.length === 0}
            className="w-fit"
          >
            <CheckIcon aria-hidden="true" />
            {submitting ? t.quizSubmitting : t.quizSubmit}
          </Button>
        ) : (
          <Button type="button" variant="secondary" onClick={retry} className="w-fit">
            {t.quizRetry}
          </Button>
        )}
      </div>

      {payload.dropped.length > 0 && (
        <div className="px-5 pb-5">
          <DroppedQuestions dropped={payload.dropped} />
        </div>
      )}
    </div>
  )
}

/**
 * §12.8: puan yalnızca DETERMİNİSTİK sorulardan. Kısa cevaplar ayrı sayılır ve
 * puana katılmaz — bu, etiketin kendisinde yazılıdır, dipnotta değil.
 */
function ScoreSummary({ result }: { result: AttemptResult }) {
  const t = useT(studio)
  return (
    <dl className="flex flex-wrap items-center gap-x-6 gap-y-1">
      <div className="flex items-baseline gap-1.5">
        <Tooltip>
          <TooltipTrigger
            render={<dt className="cursor-default text-caption text-text-tertiary" />}
          >
            {t.quizScoreLabel}
          </TooltipTrigger>
          <TooltipContent>{t.quizScoreHint}</TooltipContent>
        </Tooltip>
        <dd className="font-mono text-mono font-medium text-text-primary tabular-nums">
          {result.score === null
            ? "—"
            : `${result.correct_count}/${result.deterministic_total}`}
        </dd>
      </div>
      {result.similarity_total > 0 && (
        <div className="flex items-baseline gap-1.5">
          <dt className="text-caption text-text-tertiary">{t.quizTypeShortAnswer}</dt>
          <dd className="font-mono text-mono text-text-secondary tabular-nums">
            {result.similarity_total}
          </dd>
        </div>
      )}
    </dl>
  )
}

function QuestionCard({
  index,
  question,
  value,
  onChange,
  result,
}: {
  index: number
  question: QuizQuestion
  value: string
  onChange: (value: string) => void
  result: QuizAnswerResult | null
}) {
  const t = useT(studio)
  const labels = { yes: t.quizTrue, no: t.quizFalse }
  const answered = result !== null
  const groupName = `q-${question.id}`

  return (
    <li
      data-question-id={question.id}
      data-question-type={question.type}
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-mono text-text-tertiary tabular-nums">
          {index + 1}
        </span>
        <span className="rounded-sm border border-border px-1.5 text-caption text-text-secondary">
          {typeLabel(question.type, {
            multipleChoice: t.quizTypeMultipleChoice,
            trueFalse: t.quizTypeTrueFalse,
            fillBlank: t.quizTypeFillBlank,
            shortAnswer: t.quizTypeShortAnswer,
          })}
        </span>
        {answered && result.correct !== null && (
          <span
            className={cn(
              "text-caption font-medium",
              result.correct ? "text-success" : "text-danger"
            )}
          >
            {result.correct ? t.quizCorrect : t.quizIncorrect}
          </span>
        )}
      </div>

      <p className="text-body text-text-primary">{question.prompt}</p>

      {question.choices.length > 0 ? (
        <fieldset className="flex flex-col gap-1.5" disabled={answered}>
          <legend className="sr-only">{question.prompt}</legend>
          {question.choices.map((choice) => (
            <label
              key={choice}
              className="flex items-center gap-2 text-body-sm text-text-secondary"
            >
              <input
                type="radio"
                name={groupName}
                value={choice}
                checked={value === choice}
                onChange={(event) => onChange(event.target.value)}
                className="accent-[var(--primary)]"
              />
              {choiceLabel(choice, labels)}
            </label>
          ))}
        </fieldset>
      ) : (
        <input
          type="text"
          value={value}
          disabled={answered}
          onChange={(event) => onChange(event.target.value)}
          placeholder={t.quizAnswerPlaceholder}
          aria-label={question.prompt}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-body-sm text-text-primary outline-none focus-visible:border-primary disabled:opacity-70"
        />
      )}

      {answered && <AnswerFeedback question={question} result={result} labels={labels} />}
    </li>
  )
}

function AnswerFeedback({
  question,
  result,
  labels,
}: {
  question: QuizQuestion
  result: QuizAnswerResult
  labels: { yes: string; no: string }
}) {
  const t = useT(studio)
  return (
    <div className="flex flex-col gap-1.5 border-t border-border pt-3">
      {result.given === null && (
        <p className="text-caption text-text-tertiary">{t.quizUnanswered}</p>
      )}
      {result.similarity !== null && (
        <div className="flex flex-wrap items-baseline gap-1.5">
          <Tooltip>
            <TooltipTrigger
              render={<span className="cursor-default text-caption text-text-tertiary" />}
            >
              {t.quizSimilarityLabel}
            </TooltipTrigger>
            <TooltipContent>{t.quizSimilarityHint}</TooltipContent>
          </Tooltip>
          {/* Renk YOK: bu ham cosine sorgu→chunk DEĞİL, cevap↔cevap (§12.8). */}
          <span className="font-mono text-mono text-text-primary tabular-nums">
            {result.similarity.toFixed(4)}
          </span>
        </div>
      )}
      <p className="text-body-sm text-text-secondary">
        <span className="text-caption text-text-tertiary">{t.quizExpectedLabel}: </span>
        {choiceLabel(result.expected, labels)}
      </p>
      <p className="text-body-sm text-text-secondary">
        <span className="text-caption text-text-tertiary">{t.quizEvidenceLabel}: </span>
        {result.evidence}
      </p>
      <p className="font-mono text-mono text-text-tertiary">{question.citation}</p>
    </div>
  )
}

function DroppedQuestions({ dropped }: { dropped: QuizDroppedQuestion[] }) {
  const t = useT(studio)
  const reasonLabel = (reason: QuizDroppedQuestion["reason"]): string =>
    reason === "unsupported"
      ? t.droppedReasonUnsupported
      : reason === "weak"
        ? t.droppedReasonWeak
        : t.droppedReasonUnverifiedTerms
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-h2 font-semibold text-text-primary">{t.quizDroppedHeading}</h2>
      <p className="text-body-sm text-text-secondary">{t.droppedIntro}</p>
      <ul className="flex flex-col gap-2">
        {dropped.map((item, index) => (
          <li
            key={index}
            className="flex flex-col gap-1 rounded-lg border border-border bg-card p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-caption font-medium text-warning">
                {reasonLabel(item.reason)}
              </span>
              {item.score !== null && (
                <span className="font-mono text-mono text-text-tertiary tabular-nums">
                  {item.score.toFixed(4)}
                </span>
              )}
            </div>
            <p className="text-body-sm text-text-primary">{item.prompt}</p>
            {/* Düşen METNİN kendisi ayrı: neyin doğrulanamadığı gizlenmez. */}
            <p className="text-body-sm text-text-secondary">{item.text}</p>
            {item.terms.length > 0 && (
              <p className="font-mono text-mono text-text-tertiary">
                {t.droppedTerms(item.terms)}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
