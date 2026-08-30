"use client"

import * as React from "react"
import { CheckIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { ArtifactScreen } from "../artifact-screen"
import { useT } from "@/lib/i18n"
import { studio } from "@/lib/i18n/studio"
import { ApiRequestError, submitQuizAttempt } from "@/lib/api"
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
    <ArtifactScreen
      artifact={artifact}
      onClose={onClose}
      slot="quiz-runner"
      meta={t.quizQuestionCount(payload.questions.length)}
      className={className}
    >
      {/* Gövde ortada ölçülü bir sütun, sağda ilerleme rayı — mockup'ın
          660 px + 240 px düzeni.

          Mockup soruları TEK TEK gösteriyor (sayfalama). Bu ALINMADI:
          §12 dondurulmuş bir sözleşme ve tek denemede tüm cevapların
          gönderilmesi (`submitQuizAttempt`) puanlama ile deneme kaydının
          temeli. Sayfalama, düzen değil ETKİLEŞİM değişikliği olurdu.
          Rayın kare ızgarası mockup'ın ilerleme sinyalini sayfalama
          olmadan veriyor. */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-w-0 flex-1 flex-col overflow-y-auto print:overflow-visible">
          <div className="mx-auto flex w-full max-w-3xl flex-col px-6 py-7">
            <dl className="flex flex-wrap items-center gap-x-6 gap-y-1">
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
        <p className="mt-3 text-caption text-text-tertiary">{t.quizIntro}</p>
        {result !== null && <ScoreSummary result={result} />}

      <ol aria-label={t.quizAria} className="mt-6 flex flex-col gap-4">
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

      <div data-print="hide" className="mt-5 flex flex-col gap-2">
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
        <div className="mt-5">
          <DroppedQuestions dropped={payload.dropped} />
        </div>
      )}
          </div>
        </div>

        <QuizRail
          questions={payload.questions}
          answers={answers}
          resultById={resultById}
        />
      </div>
    </ArtifactScreen>
  )
}

/**
 * Sağ ilerleme rayı — mockup'ın 240 px'lik kolonu (§13.5 Faz 4).
 *
 * İki sinyal: hangi soruların cevaplandığı (kare ızgara) ve şu ana kadarki
 * doğru sayısı. Skor YALNIZCA sonuç geldikten sonra ve YALNIZCA
 * deterministik sorulardan sayılır -- `short_answer` doğru/yanlış olarak
 * işaretlenmez (§12.8) ve bu ray o kuralı bozmaz: sayaç sunucunun
 * döndürdüğü `correct` alanına bakar, kendi kararını vermez.
 */
function QuizRail({
  questions,
  answers,
  resultById,
}: {
  questions: QuizQuestion[]
  answers: Record<string, string>
  resultById: Map<string, QuizAnswerResult>
}) {
  const t = useT(studio)
  const graded = questions.filter((q) => resultById.get(q.id)?.correct !== null)
  const correct = graded.filter((q) => resultById.get(q.id)?.correct === true)
  const hasResult = resultById.size > 0

  return (
    <aside
      data-print="hide"
      data-slot="quiz-rail"
      aria-label={t.quizProgressLabel}
      className="hidden w-60 shrink-0 flex-col gap-5 overflow-y-auto border-l-2 border-border px-5 py-6 lg:flex"
    >
      <div>
        <p className="mb-3 text-caption font-medium tracking-[0.08em] text-text-secondary uppercase">
          {t.quizProgressLabel}
        </p>
        <ol className="grid grid-cols-4 border-t border-l border-border">
          {questions.map((question, index) => {
            const result = resultById.get(question.id)
            const answered = (answers[question.id] ?? "") !== ""
            return (
              <li
                key={question.id}
                className={cn(
                  "flex aspect-square items-center justify-center border-r border-b border-border",
                  "font-mono text-mono tabular-nums",
                  result?.correct === true
                    ? "bg-primary text-primary-foreground"
                    : result?.correct === false
                      ? "bg-danger text-primary-foreground"
                      : answered
                        ? "bg-surface-raised text-text-primary"
                        : "text-text-tertiary"
                )}
              >
                {index + 1}
              </li>
            )
          })}
        </ol>
      </div>

      {hasResult && (
        <div className="border-t-2 border-border pt-4">
          <p className="text-h1 font-semibold text-text-primary tabular-nums">
            {correct.length}/{graded.length}
          </p>
          <p className="mt-0.5 text-body-sm text-text-secondary">{t.quizScoreSoFar}</p>
        </div>
      )}

      <p className="text-caption text-text-tertiary">{t.quizIntro}</p>
    </aside>
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
      {/* Yargı YOKSA (short_answer) kararı kullanıcı veriyor -- iki metni
          yan yana koymak o kararı kolaylaştırır. Yargı VARSA (üç
          deterministik tip) böyle bir karşılaştırmaya gerek yok: sonuç zaten
          "Doğru/Yanlış" diyor ve seçilen şık işaretli duruyor. */}
      {result.correct === null && result.given !== null ? (
        <div className="grid border-2 border-text-primary sm:grid-cols-2">
          <div className="border-b border-border p-2.5 sm:border-r sm:border-b-0">
            <p className="text-caption font-medium tracking-[0.08em] text-text-tertiary uppercase">
              {t.quizGivenLabel}
            </p>
            <p className="mt-1 text-body-sm text-text-primary">
              {choiceLabel(result.given, labels)}
            </p>
          </div>
          <div className="bg-surface p-2.5">
            <p className="text-caption font-medium tracking-[0.08em] text-text-tertiary uppercase">
              {t.quizExpectedLabel}
            </p>
            <p className="mt-1 text-body-sm text-text-primary">
              {choiceLabel(result.expected, labels)}
            </p>
          </div>
        </div>
      ) : (
        <p className="text-body-sm text-text-secondary">
          <span className="text-caption text-text-tertiary">{t.quizExpectedLabel}: </span>
          {choiceLabel(result.expected, labels)}
        </p>
      )}
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
