# Implementation Log — Blueprint Execution

This document records the changes made while implementing the engineering &
design blueprint, organized by phase. Every item notes **what** changed, **why**,
and the **files** touched. Verification evidence is included where a change was
rendered/executed rather than only reasoned about.

Stable IDs (`BUG-01…12`, `ARCH-A…D`) match the blueprint.

---

## Phase 0 — Critical fixes

| ID | Change | Files |
|----|--------|-------|
| **BUG-01** | **Fixed audio/video desync.** The transition step overlapped video with `xfade` (shortening the timeline) while concatenating audio at full length, so narration drifted ahead of the visuals by `~0.5s × (slides−1)`. Replaced with a **single shared timeline**: plain concatenation plus a short fade baked into each segment (`_fade_suffix`), so audio and video advance in lockstep. | `services/video_composer/composer.py` |
| **BUG-07** | **Enabled LLM reasoning.** `thinking_budget` was hardcoded to `0` on every call, disabling Gemini 2.5 reasoning. Now configurable via `settings.LLM_THINKING_BUDGET` (default 4096) with a per-call override; cheap agents (QA/SEO/quiz) pass `0`. Added tolerant JSON parsing to avoid billed 8× retries on trailing prose. | `providers/llm/gemini.py`, `providers/llm/base.py`, `config/settings.py`, `agents/qa_agent.py`, `agents/seo_agent.py`, `agents/quiz_agent.py` |
| **BUG-03** | **Stopped fabricating code output.** `is_validated=True` and `actual_output=expected_output` were hardcoded — invented output shown as fact. Now honest: with execution off (default) code is marked **unvalidated** with no fake output; opt-in `settings.ENABLE_CODE_EXECUTION` runs the sandbox and captures **real** stdout. | `agents/code_agent.py`, `config/settings.py` |
| **BUG-02** | **Revived weighted code-reveal timing.** A stub (`reveals_seen_blank`, always `True`) made the weight list mismatch the frame list, so reveals always fell back to uniform timing. Unified both on one `_reveal_lines()` filter. | `services/code_animator/animator.py` |
| **BUG-08** | **Grounded YouTube chapters** in real cumulative audio durations (grouped by slide) instead of LLM-hallucinated timestamps; honors YouTube's 0:00 / ≥3-chapter / ≥10s rules. | `agents/seo_agent.py` |
| **BUG-04** | **Fixed SSE framing** on the course log stream (emitted literal `\n\n` text). | `api/server.py` |
| **BUG-05** | **Fixed interpreter spawn** — `sys.executable` instead of bare `python`. | `api/server.py` |
| **BUG-11** | **Graceful TTS fallback** — a failed segment now becomes a sized silence placeholder (preserving audio↔slide alignment) instead of aborting the whole run; failures flagged in `state["tts_failures"]`. | `agents/voice_agent.py` |
| **BUG-10** | **Guard empty-section lectures** — a lecture whose section IDs were all invalid is dropped/renumbered rather than generating from nothing. | `agents/curriculum_agent.py` |
| — | **Hardened music mixing** — an empty `music_track` (the `no_music` profile) resolved to the cwd and failed the step; now treated as "no music". (Surfaced by the BUG-01 render test.) | `services/video_composer/composer.py` |

**Verification:** synthetic 3-slide render → **0.000s A/V skew**; code-reveal now produces varied per-line durations summing exactly to the audio; tolerant-JSON, fade, and timestamp helpers unit-tested; all modules import-clean.

---

## Phase 1 — Foundation

| ID | Change | Files |
|----|--------|-------|
| **ARCH-A** | **Shared media utilities.** `get_ffmpeg`, `fwd`, `get_audio_duration`, `run_ffmpeg` (raises `FFmpegError` on non-zero exit), `make_silence`, `seconds_to_srt_time` now live in one module; five files that each re-implemented them delegate to it. | **new** `services/media/ffmpeg.py`, `services/media/__init__.py`; refactored `composer.py`, `voice_agent.py`, `video_agent.py`, `code_animator/animator.py`, `diagram_renderer/html_animator.py` |
| **BUG-09** | **Deterministic slide render.** The renderer now awaits `document.fonts.ready` and an explicit in-page `window.__slideReady` flag before screenshotting, so a slide can never capture mid-highlight or in a fallback font. Same font wait added to diagram frame capture. | `services/slide_renderer/renderer.py`, `services/slide_renderer/templates/slide.html`, `services/diagram_renderer/html_animator.py` |
| **ARCH-C** | **Removed dead code** — `compose_video()` legacy, `_mix_background_music()` alias, `resolve_transition_hints()`, `BaseAgent._load_prompt()` (read a nonexistent `prompts/` dir), and the unused `lucide-react` GUI dependency. | `composer.py`, `agents/base_agent.py`, `gui/package.json` |
| **ARCH-B** | **Validated agent boundaries.** A new validator checks each agent's declared outputs the moment it finishes (hooked into the checkpoint wrapper), so malformed/empty output fails at its own stage with a clear message instead of crashing a downstream agent. `ScriptSegment` schema aligned with the real `slide_id` field. | **new** `contracts/validation.py`; `pipelines/full_video_pipeline.py`, `contracts/schemas.py` |
| **BUG-06** | **Durable job state.** The API's in-memory task dicts (`_ingest_tasks`, `_curricula_tasks`, `_test_runs`, `_rerender_tasks`) — lost on reload, unbounded, single-worker-only — are replaced by a SQLite-backed store (`Job` model). | **new** `db/jobs.py`; `db/models.py`, `api/server.py` |
| — | Added the genuinely-required **`python-multipart`** to `requirements.txt` (FastAPI needs it for PDF upload). | `requirements.txt` |

**Verification:** media refactor preserves the 0.000s A/V skew; a real **code slide rendered with full syntax highlighting and correct fonts** (BUG-09); boundary validator unit-tested; job store round-trip tested; **`api.server` imports clean with all 39 routes**.

---

## Phase 2 — The presentation engine

The slide system is now driven by a machine-readable design system that the LLM,
the selection engine, and the linter all read from — so the rules can't drift.

| Item | Change | Files |
|------|--------|-------|
| **Layout catalog / design brief (§22)** | The canonical design system as data: canvas/grid, type floor, invariant rules, hard bindings, the density formula, and a per-layout catalog (id, family, use-when, caps, density capacity, motion/transition defaults) for all 35 layouts. `design_brief_json()` is what the LLM is handed. | **new** `services/slide_renderer/layout_catalog.py` |
| **Selection engine (§13)** | Content-shape → candidate-layout classifier and a deck-level `audit()` of the diversity/rhythm/density invariants (consecutive-layout, content-overuse, required-once, pacing breaths, over-density). | **new** `services/slide_renderer/selection.py` |
| **Render linter (§21)** | The pre-render validator now enforces the catalog's per-slide **density budget** so an overloaded slide is flagged to be split. | `services/slide_validator/validator.py` |
| **Slide-agent integration** | The design brief is injected into the slide LLM prompt (with reasoning on), and the deck audit runs on its output and is logged + stored in `state["layout_audit"]`. | `agents/slide_agent.py` |
| **Shared design tokens (§10–11)** | A token partial defines the slide design system (ground/ink ramp, accent, semantic colors, radius, type scale) as CSS variables from one source; wired into the slide template. | **new** `services/slide_renderer/templates/_tokens.html`; `services/slide_renderer/templates/slide.html` |

**Verification:** catalog emits valid JSON (35 layouts, 8 families); `classify`, `audit`, and the density linter unit-tested; slide agent imports with the 8.6 KB brief; **title and prose slides re-render correctly through the token layer.**

---

## Phase 3 — Operator studio (GUI)

| Item | Change | Files |
|------|--------|-------|
| **Shared UI tokens** | The `S` token object and `cx` helper — previously copy-pasted into all four pages — now live in one module, along with the 11-stage pipeline model and a log→stage parser. | **new** `gui/src/lib/ui.js`; `Dashboard.jsx`, `Curricula.jsx`, `PipelineMonitor.jsx`, `TestingStudio.jsx` |
| **Fixed navigation IA** | The sidebar's `Settings` link now routes to a real page (profiles/voices/usage); `Docs` opens the live API reference. Both previously dead-ended and silently redirected home. | **new** `gui/src/pages/Settings.jsx`; `App.jsx`, `components/Sidebar.jsx` |
| **Live production monitor** | An 11-stage stepper on the Pipeline Monitor turns the raw SSE log into real per-stage progress (done / active / pending), replacing the coarse pending→done status. | `gui/src/pages/PipelineMonitor.jsx` |

**Verification:** `npm run build` succeeds (32 modules); stage parser unit-tested via node; oxlint clean (one pre-existing unused-var warning, untouched).

---

## Phase 4 — Completion of deferred engine work

| Item | Change | Files |
|------|--------|-------|
| **Golden render gallery** | A catalog-driven script renders **all 35 layouts** with representative fixtures to reference PNGs — the safety net for any template change and a smoke test that fails if a layout can't render. | **new** `scripts/render_layout_gallery.py` |
| **Server-side syntax highlighting (§14)** | The C/C++ tokenizer was ported from the in-page `<script>` to Python and baked into the HTML at render time; the JS highlighter is gone (only a trivial `__slideReady` flag remains). This removes the JS half of the render race entirely and makes highlighting deterministic. Font-size tiering moved server-side too. | `services/slide_renderer/renderer.py`, `services/slide_renderer/templates/slide.html` |

**Verification:** the tokenizer unit-tests produce the right span classes and escape `<`/`>`; a `split_code` slide **re-renders with full highlighting** identical to the old JS output; the **full 35-layout gallery renders 35/35** both before and after the change (no regression).

---

## Phase 5 — Template split &amp; full studio

| Item | Change | Files |
|------|--------|-------|
| **Master-slide file split (§8)** | `slide.html`'s 34-branch layout chain was split into a `base.html` master (chrome, CSS, tokens, dynamic include) plus one partial per layout under `templates/layouts/` (36 files: 35 catalog layouts + legacy `checklist`). The renderer loads `base.html`, which does `{% include "layouts/" ~ layout ~ ".html" %}` with a `content` fallback. A new layout is now a ~30-line file, not a copy of the monolith. | **new** `templates/base.html`, `templates/layouts/*.html`; `services/slide_renderer/renderer.py`; removed `templates/slide.html` |
| **Studio: cancel** | The generation subprocess is tracked per lesson; a cancel endpoint terminates it and marks the lesson failed. A Cancel button appears on the live monitor while a run is in flight. | `api/server.py`, `gui/src/pages/PipelineMonitor.jsx` |
| **Studio: per-slide edit + before/after** | New endpoints return a lesson's editable slide specs and re-render a single edited slide (persisting the edit to the checkpoint). The Testing Studio's gallery became a **Slide Studio**: pick a slide, edit its text/bullets, re-render just that slide, and see before/after. The `/slides` list now merges original + re-rendered folders per-file so a single edit shows alongside the unchanged rest. | `api/server.py`, `gui/src/pages/TestingStudio.jsx` |
| **Studio: curriculum reorder** | The generated curriculum is drag-to-reorder (native DnD) with a Save button that persists the new order via the existing curriculum edit endpoint. | `gui/src/pages/Curricula.jsx` |

**Verification:** the split renders the **full 35-layout gallery byte-identical** to the pre-split output (35 identical / 0 different by MD5); the API imports with all 42 routes; the slide-edit endpoints were exercised against the real `cpp_678b` lesson (7 slides read, `slide_003` re-rendered, PNG written); the GUI builds (32 modules) and lints clean apart from one pre-existing unused-var warning.

---

## Operational notes (behavior changes)

- **Cost & latency:** enabling reasoning (BUG-07) makes plan/script/slide calls think and cost more. `MAX_COST_USD_PER_RUN` (default `$0.50`) may now trip — **raise it**, and tune `LLM_THINKING_BUDGET`.
- **QA scores drop** because code is honestly marked unvalidated unless `ENABLE_CODE_EXECUTION=true` (which runs generated code on the host — a deliberate security choice, off by default).
- **Transitions:** overlapping wipe/slide transitions are disabled in favor of a sync-safe per-segment fade. Layout-aware overlapping transitions can return once they overlap audio and video by the same amount (see the retained-but-unused `_apply_xfade_transitions`).

---

## What remains

One item remains, and it is purely an infrastructure/scale concern:

1. **Job queue + render workers (scale).** The durable `Job` store (Phase 1) and
   the per-lesson cancel handle (Phase 5) are the foundation. Moving generation
   off FastAPI background tasks onto a real broker (RQ/Celery/Redis) with
   separate render workers needs that infrastructure running to build and verify
   end-to-end, so it is out of scope for a headless code session. It is the
   natural next step for multi-user / multi-machine deployment.

Everything else in the blueprint is implemented and verified: all Phase 0-2
engine work (catalog, selection engine, linter, design brief, tokens,
deterministic + server-side-highlighted rendering, the golden gallery, and the
`base.html` + per-layout-partial master architecture) and the operator studio
(live stage monitor, cancel, per-slide edit with before/after, curriculum
reorder, shared UI tokens, fixed navigation).
