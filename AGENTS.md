# Project Instructions

A **fully offline Turkish PDF document Q&A assistant** running on Foundry
Local. The user uploads PDFs; questions are answered only from the uploaded
documents, with source citations. Built for the Microsoft Türkiye AI
Innovators program.

**Language:** the repo's prose is Turkish — code comments, `PROJE_DURUMU.md`,
`docs/`, UI strings, and commit messages. Write in Turkish when you write into
the repo. This file and the agent definitions are English on purpose:
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
.venv/bin/python eval/run_eval.py --category meta     # PARTIAL run, for iteration only
.venv/bin/python eval/offline_proof.py                # + network audit log
.venv/bin/python eval/fidelity_trap.py                # pinned known limit of the gate
.venv/bin/python eval/report_trap.py                  # Faz 2 closing measurement, NOT a routine gate
.venv/bin/python eval/mindmap_proof.py                # Faz 3 closing measurement, NOT a routine gate
.venv/bin/python eval/quiz_proof.py [--trap]          # Faz 4 closing measurement, NOT a routine gate
.venv/bin/python eval/ui_proof.py                     # browser proof on a deterministic fixture; no model
.venv/bin/python eval/ui_proof.py --shots-dir docs/screenshots   # refresh README screenshots
.venv/bin/python eval/ui_proof.py --db rag.db        # same proof against real data (fragile by design)
.venv/bin/python eval/short_answer_calibration.py     # short_answer threshold measurement; embedding only
.venv/bin/python docs/check_contrast.py               # verify contrast claims
.venv/bin/python -m rag.ingest --pdf dosya.pdf        # ingest a document
.venv/bin/python -m rag.ingest --markdown-dir data    # ingest the markdown fixtures
.venv/bin/python -m pytest backend/tests -q           # backend tests
cd web && npm run build && npm run lint               # frontend
```

`--category` exists because a full eval run costs ~200 s **and loads the 7B
model**; iterating on one category costs ~45 s. It is deliberately refused in
combination with `--json`: a partial result must never reach `results.json`,
or `/api/metrics` and every baseline comparison would report a subset as if it
were the gate.

Minimum gate before delivery: **eval 23/23 · `pytest backend/tests -q` with
zero failures · `eval/fidelity_trap.py` PASS · clean frontend build**.

`eval/ui_proof.py` now defaults to a **deterministic fixture**
(`eval/fixtures/ui.db`, built on demand like `eval/eval.db`) rather than the
developer's `rag.db`. That coupling broke the proof twice — once when a new
artifact changed the list order, once when re-uploading a PDF removed the
"document without a stored source" case the proof asserted. `--db rag.db`
still points it at real data when you want to look at real data.

`.github/workflows/gates.yml` runs the model-free part of that gate: pytest ·
frontend build · lint on every push, plus `eval/ui_proof.py` on pull requests
and pushes to `main` (a separate job — it needs both toolchains and a
cached Chromium, so it is not worth paying on every WIP commit). The model-loading half — eval, offline
proof, the trap runners — stays local by design (see `PROJE_DURUMU.md`,
"Kapıların model yüklemeyen yarısı CI'a devredildi"). CI passing is therefore
necessary, never sufficient.

The pytest gate is deliberately *not* a fixed number. It was written as
`91/91` while the real count was 93, then 123, then 124 — a stale count
reports a lost test as green, which is the exact failure the gate exists to
catch. The eval gate stays numeric (23/23) because that set only grows by an
explicit, justified decision.

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

Alongside it, the source PDF is kept so a cited page can be rendered on
demand (FEATURE_SPEC §13.4):

```
PDF bytes ──> store.document_files (BLOB, CASCADE with the document)
          ──> raster.render_page (pypdfium2, on request, ~47 ms)
          ──> GET /api/documents/{filename}/pages/{page}/image
```

`backend/` exposes this pipeline over HTTP/SSE. `web/` is served as a static
export by the backend — one process at runtime, zero network.

---

## 5. Agents

Eight agents are defined in the local agent-tooling configuration, which is
**not tracked in this repository** (it is machine-specific and vendor-specific;
only the roles and the ownership contract below are part of the project). The
front door is
**urun-mimari**; ambiguous work goes there. Implementers (`rag-muhendisi`,
`backend-muhendisi`, `frontend-muhendisi`, `bilgi-alani-muhendisi`) cannot
approve their own work — the verifiers (`prompt-eval-muhendisi`,
`kalite-muhafizi`) report directly to the architect. Each agent's tool
permissions and escalation boundaries are written in its own file.

**Model split:** `urun-mimari` runs on `opus` — it writes specs, arbitrates
conflicts, and decides what gets built, which is the judgment-heavy work. The
other seven run on `sonnet`, where the task is bounded by a spec and a
contract. Set per agent via the `model` frontmatter field. Note that a harness-level
subagent-model environment override, if set, takes precedence over every one
of these.

### Ownership map

Every directory has exactly one owner. Work goes to the owner of the directory
it lands in, not the owner of the topic it sounds like.

| Path | Owner |
|---|---|
| `rag/` except `rag/artifacts/` | `rag-muhendisi` |
| `rag/artifacts/`, `web/components/studio/` | `bilgi-alani-muhendisi` |
| `backend/` | `backend-muhendisi` |
| `web/` except `web/components/studio/` | `frontend-muhendisi` |
| `eval/`, `data/` | `prompt-eval-muhendisi` |
| `docs/FEATURE_SPEC.md` | `urun-mimari` (exclusive) |
| `PROJE_DURUMU.md`, rest of `docs/` | `dokuman-anlati` |
| `graphify-out/` | generated artifact — no owner, never hand-edited |

### What the harness enforces, and what it does not

Be honest about this, because it changes how much the written rules can be
trusted:

- **Enforced by the harness:** each agent's tool set, and the allow/ask/deny
  permission rules in the local tooling configuration. Those deny rules
  are **session-wide, not per-agent** — the harness has no per-agent path
  permissions, so a rule like `Edit(rag/**)` would lock out `rag-muhendisi`
  along with everyone else. That is why the ownership map above is not, and
  cannot be, a permission rule.
- **Not enforced — instruction only:** the ownership map, read-only status,
  escalation. `kalite-muhafizi` reading the diff is the actual detection
  mechanism, and it only runs when it is called.

So: **route every delivery through `kalite-muhafizi`.** It is not a formality;
it is the only thing standing between the ownership model and wishful
thinking.

### Escalation is an output, not a call

Only `urun-mimari` can invoke other agents. The other seven escalate by
**writing** a delivery whose first line is `ESKALASYON: <reason>` and stopping.
Such a delivery is not a completed delivery. This matters most when an
implementer is invoked directly by the user with no architect above it — the
escalation lands with the user, so it must name the contract it is protecting.

### Concurrency

One git working tree, several sessions. Two agents editing the same file, or
two `--ingest` runs against the same SQLite file, race — and the loser is
silent. Rules:

- **At most one implementer at a time** on the same path, unless each runs in
  its own worktree (`isolation: "worktree"`).
- Verification (`kalite-muhafizi`, `prompt-eval-muhendisi`) is read-mostly and
  may run in parallel with nothing else writing.
- A measurement run and an implementation run must not overlap: the numbers
  would describe a tree that no longer exists.

### Memory — the same rule, second reason

The concurrency rules above exist to prevent silent races. They have a second,
harder justification: **the dev machine has 16 GB and the models are local.**
Parallel agents crashed it once, and the cause was not the agents — it was two
of them loading `qwen2.5-7b` at the same time while a third ran a Node build.

Work that loads a local model, and therefore must never run concurrently with
anything else on this list:

| Work | Loads | Cost |
|---|---|---|
| `eval/run_eval.py` | 7B + embedding | ~200 s |
| `eval/run_eval.py --category X` | **7B + embedding** | ~45 s |
| `eval/offline_proof.py` | 7B + embedding | ~180 s |
| `eval/fidelity_trap.py` | embedding | ~10 s |
| `eval/short_answer_calibration.py` | embedding | ~15 s |
| `eval/report_trap.py` | 7B + embedding | ~4 min (9 LLM calls on eval.db) |
| `eval/mindmap_proof.py` | 7B + embedding | ~1 min (7 LLM calls on eval.db) |
| `eval/quiz_proof.py` | 7B + embedding | ~1 min (LLM only for short_answer) |
| `python -m rag.ingest` | embedding | per document |
| **Running an artifact generator** | 7B + embedding | per LLM call |

Three traps in that table, all of them easy to walk into:

1. **`--category` buys time, not memory.** 45 s instead of 200 s, but the 7B
   still loads. It is the cheap *iteration* path, never the cheap *concurrent*
   path.
2. **From Studio Faz 2 onward the feature under development is itself on this
   list.** A report generator makes one LLM call per section; an agent
   developing it loads the model on every iteration, not just at the gate. The
   rule is no longer "the gates are expensive" — it is "the work is expensive."
3. **`npm run build` is cheap alone, not free alongside.** It spawns six Node
   workers and it was running next to two model loads when the machine died.
   ~3 s on its own; do not overlap it with a model run to save wall time.

`pytest backend/tests -q` is the one genuinely free loop: ~1 s, **no model**.

So the working loop is: **iterate against pytest; when you must exercise the
model, do it alone; pay the full gate once, at delivery, with nothing else
running.** Do not give each agent in a chain its own eval run — one
measurement, one runner, and say in the delivery who ran it. Prefer a small
bounded change inline over an agent chain: every agent starts cold, re-derives
context, and runs its own gates.
