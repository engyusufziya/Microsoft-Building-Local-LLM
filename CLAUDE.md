# Project Instructions

A **fully offline Turkish PDF document Q&A assistant** running on Foundry
Local. The user uploads PDFs; questions are answered only from the uploaded
documents, with source citations. Built for the Microsoft Türkiye AI
Innovators program.

**Language:** the repo's prose is Turkish — code comments, `PROJE_DURUMU.md`,
`docs/`, UI strings, and commit messages. Write in Turkish when you write into
the repo. This file and `.claude/agents/*.md` are English on purpose:
instructions to an agent are kept in their original wording so nothing is lost
in translation.

Current technical state, decisions, and **the reasoning behind them**:
`PROJE_DURUMU.md`. Endpoint schemas and user flows: `docs/FEATURE_SPEC.md`.
Color, typography, contrast: `docs/DESIGN_SYSTEM.md`.

---

## 1. Inviolable contracts

The real risk in this project is not that code fails to work — it is
**contracts that break silently**. Each of the following can be violated
without failing a single test. Stop and ask before violating any of them.

**1.1 — `Hit.score` is always the raw cosine similarity.**
`MIN_SCORE` (0.45), the Retrieval Inspector's confidence bands, and the
`DESIGN_SYSTEM.md §1.2` color thresholds are all bound to that one number.
Normalizing, rescaling, or replacing it with a fusion score makes the
Inspector lie. Hybrid retrieval widens the candidate **pool** only; it never
touches the score.

**1.2 — The offline guarantee is absolute.**
No runtime path may make a network call: no HTTP client, no CDN font, no
telemetry, no remote model. `eval/offline_proof.py` audits this at the socket
level and expects **0 socket calls**. The frontend is built with
`output: 'export'`; no external resource may be added.

**1.3 — `rag/config.py` is the single point of configuration.**
No module keeps its own constants. A new constant goes into config **together
with its rationale** — follow the commenting style already in that file.

**1.4 — Eval honesty is not negotiable.**
If a question fails, do not loosen the metric, lower the threshold, or soften
`expected_keywords`. That `expected_keywords` sometimes reports loosely is a
**known limitation, deliberately left unfixed** — do not "fix" it. A threshold
change is presented as its own decision, justified by a measurement.

**1.5 — `rag/` is pure; `backend/` is thin.**
Business logic belongs in `rag/`. `backend/` is the HTTP/SSE surface; every
condition that leaks into it is an architecture violation.

**1.6 — The decision record includes rejected alternatives.**
`PROJE_DURUMU.md` records not only what was done but what was tried and **why
it was dropped** (the eliminated model, the walked-back threshold, the
measurement that turned out to be wrong). Do not flatten this into a sterile
summary list.

---

## 2. Coding discipline

Karpathy's four principles on LLM coding pitfalls, grounded in this project's
actual failure modes.

### 2.1 Think before coding — don't assume, don't hide confusion

State assumptions explicitly. If multiple interpretations exist, present them
— don't pick silently. If a simpler approach exists, say so. If something is
unclear, **stop and name what is confusing**.

This matters especially here, because the SDK carries undocumented behavior.
`ChatClientSettings` serializes `temperature`, `top_p`, and `random_seed` into
the request body, but the runtime **ignores them** (measured: 0.0 and 1.5
produced byte-identical output; different seeds produced identical output).
Streaming occasionally yields empty `chunk.choices`. If you are not certain an
API exists in the installed version — do not write it on "it probably does."
Verify.

### 2.2 Simplicity first — nothing speculative

No features beyond what was asked. No abstractions for single-use code. No
"flexibility" or configurability that wasn't requested. No error handling for
impossible scenarios.

**The test:** would a senior engineer call this overcomplicated? If yes,
simplify. If you wrote 200 lines and 50 would do, rewrite it.

### 2.3 Surgical changes — touch only what you must

Don't "improve" adjacent code, comments, or formatting. Don't refactor what
isn't broken. Match the existing style even if you'd do it differently — in
this repo comments are Turkish and carry rationale; keep it that way.

If you notice unrelated dead code, **mention it, don't delete it**. Remove
only the imports, variables, and functions that *your* change made unused.

**The test:** does every changed line trace directly to the requested work?

### 2.4 Goal-driven execution — define verifiable success criteria

| Instead of… | Transform to… |
|---|---|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Improve retrieval" | "Add the query to the eval set, measure, then hold 23/23" |

For multi-step work, state a brief plan and attach a check to each step:

```
1. [step] → verify: [check]
2. [step] → verify: [check]
```

**In this project, verification is always a number.** "Seems to work" is not a
delivery. A retrieval change ships with an eval result, a UI change with a
clean build plus measured contrast, a backend change with a passing test.

### 2.5 When to relax

These principles bias toward caution over speed. Use judgment on typo fixes
and obvious one-liners. They matter most on: changes over ~20 lines, code you
don't fully understand, and multi-step work with unclear requirements.

---

## 3. Commands

```bash
.venv/bin/python cli.py "RAG kaç adımdan oluşur?"    # single question
.venv/bin/python cli.py --show-chunks                 # interactive, with context
.venv/bin/streamlit run streamlit_app.py              # v1 interface
.venv/bin/python eval/run_eval.py                     # 23-question evaluation
.venv/bin/python eval/offline_proof.py                # + network audit log
.venv/bin/python docs/check_contrast.py               # verify contrast claims
.venv/bin/python -m rag.ingest --pdf dosya.pdf        # ingest a document
.venv/bin/python -m pytest backend/tests -q           # backend tests
cd web && npm run build && npm run lint               # frontend
```

Minimum gate before delivery: **eval 23/23 · backend 124/124 · clean frontend
build**.

---

## 4. Architecture map

```
PDF ──> pdf_loader (page text, OCR fallback)
    ──> chunking (130 words + 30 overlap, page boundary preserved)
    ──> models.embed_texts (qwen3-embedding-0.6b, 1024 dims)
    ──> store (SQLite, float32 BLOB, L2-normalized matrix cache)

Query ──> query_router (rule-based: search / summarize / corpus)
      ──> retrieve (cosine + MIN_SCORE, optional BM25+RRF candidate pool)
      ──> answer (SYSTEM_PROMPT | SUMMARY_PROMPT + qwen2.5-7b)
      ──> answer + [Kaynak: dosya.pdf s.4]
```

`backend/` exposes this pipeline over HTTP/SSE. `web/` is served as a static
export by the backend — one process at runtime, zero network.

---

## 5. Agents

Eight agents are defined under `.claude/agents/`. The front door is
**urun-mimari**; ambiguous work goes there. Implementers (`rag-muhendisi`,
`backend-muhendisi`, `frontend-muhendisi`, `bilgi-alani-muhendisi`) cannot
approve their own work — the verifiers (`prompt-eval-muhendisi`,
`kalite-muhafizi`) report directly to the architect. Each agent's tool
permissions and escalation boundaries are written in its own file.

**Model split:** `urun-mimari` runs on `opus` — it writes specs, arbitrates
conflicts, and decides what gets built, which is the judgment-heavy work. The
other seven run on `sonnet`, where the task is bounded by a spec and a
contract. Set per agent via the `model` frontmatter field. Note that the
`CLAUDE_CODE_SUBAGENT_MODEL` environment variable, if set, overrides every
one of these.
