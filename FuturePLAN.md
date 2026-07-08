# theTwoCubes — Production-Grade Video Automation Roadmap

> **Status:** Iteration 2 complete. The pipeline is functional and produces real videos.
> This document tracks everything needed to go from "working prototype" to "production system."

---

## ✅ Already Implemented

| Feature                      | Notes                                                                  |
| ---------------------------- | ---------------------------------------------------------------------- |
| Checkpoint / Resume system   | JSON checkpoints per agent, survives crashes                           |
| Parallel audio synthesis     | ThreadPoolExecutor, 8 workers                                          |
| Token & cost tracker         | SQLite usage_log + cost_report.py CLI                                  |
| Audio normalization          | ffmpeg loudnorm on all segments                                        |
| Slide transitions            | FFmpeg xfade between all segments                                      |
| Background music mixing      | assets/music/bg_track.mp3 at 8% volume                                 |
| Adaptive font sizing         | JS auto-scale in slide template                                        |
| Inline syntax highlighter    | C++ / Python tokenizer, no CDN                                         |
| 11 slide layouts             | numbered_steps, comparison, checklist, error_fix, terminal + originals |
| Progress bar + slide counter | On every slide                                                         |
| Code reveal animation        | Line-by-line typewriter via Playwright + FFmpeg                        |
| HTML/CSS animated diagrams   | Playwright frame capture → MP4, fallback templates                    |
| Subtitle .srt generation     | Timing-based from audio durations                                      |
| Intro & Outro slides         | Branded templates + optional music                                     |
| Slide review CLI             | review_slides.py — approve/flag before audio                          |
| Fixture-based test pipeline  | Zero LLM calls, full render stack                                      |
| Test Runner GUI              | React dashboard with live polling                                      |
| FastAPI backend              | Serves courses, lessons, test runs, usage                              |
| Cost report GUI              | Per-model breakdown in dashboard                                       |

---

## Phase A — Content Quality (Highest Impact)

> Make every video feel like a real teacher thought it through.

### A.1 Two-Pass Script Generation

**Problem:** First-pass scripts often have sentences over 20 words, passive voice, and
filler phrases ("In this section we will...").

**Fix:**

1. Pass 1: Generate full script (current behavior)
2. Pass 2: Send each segment back with this constraint — max 25 words per sentence,
   active voice, no filler openers, every sentence must contain a concrete technical fact
3. Cost: ~1 500 extra tokens per lesson (~$0.0003 — negligible)

**Impact:** Dramatically improves narration clarity and listener retention.

---

### A.2 Slide Content Validator (Pre-Render)

**Problem:** LLM generates slides with vague bullets despite prompt engineering.

**Fix:** After `SlideAgent` outputs JSON specs, run a rule-based validator before
rendering any PNGs:

- Require code slides to have `return` or a function signature
- Auto-flag and regenerate only the failing slides (cheap — single slide re-call)

**File:** New `services/slide_validator/validator.py`

---

### A.3 Lesson Continuity Awareness

**Problem:** Lesson 5 may repeat what Lesson 3 already taught. No cross-lesson memory.

**Fix:** Before `LessonPlannerAgent` runs, inject the previous lesson's summary bullets
and SEO title into the prompt:

```
Previously taught:
- Lesson 3: "Pointers — int* p stores an address, not a value"
- Lesson 4: "Arrays are contiguous blocks of memory, ptr arithmetic works on them"

Do NOT re-explain the above. Build on it.
```

**File:** `agents/lesson_planner_agent.py`, `pipelines/full_video_pipeline.py`

### A.4 Narration Pacing Score

**Problem:** Some segments are too fast (30 words, 2 seconds of audio = rushed), some
too slow (5 words, 4 seconds = awkward silence).

**Fix:** After `VoiceAgent` finishes, compute words-per-minute for each segment.
Flag segments outside 100–160 WPM range in `lesson_summary.json`.
Show flagged segments in the GUI slide detail view.

---

### A.5 SSML Pause Tags

**Problem:** Narration has no breathing room between topic transitions.

**Fix:** In `ScriptAgent` prompt, instruct it to insert `[PAUSE]` markers between major
topic shifts. In `VoiceAgent`, replace `[PAUSE]` with 600ms of silence via:

```python
pydub.AudioSegment.silent(duration=600)
```

**File:** `agents/voice_agent.py`, `agents/script_agent.py`

---

### A.6 Auto Pronunciation Lexicon (Expanded)

**Problem:** TTS mispronounces: `cout` ("cout"), `endl` ("end-l"), `nullptr` ("null-pt-er"),
`argc` ("ar-gee-see"), `argv` ("ar-gee-vee"), `uint32_t` ("oo-int-32-t").

**Fix:** Expand `config/pronunciation_lexicon.py` to 100+ CS terms with phonetic
replacements. Use a community-curated list as source.

---

## Phase B — Visual Excellence (Slides)

---

### B.1 Per-Layout Slide Transitions

**Problem:** All slides use the same `fade` xfade. Monotonous.

**Fix:** Store `transition_hint` in slide spec JSON. Map layouts to transitions:

| Layout                     | Transition    |
| -------------------------- | ------------- |
| `title` → first content | `zoomin`    |
| `content` → `content` | `fade`      |
| `code` → next           | `wipeleft`  |
| Any →`summary`          | `fadeblack` |
| Any →`exercise`         | `slideleft` |

**File:** `agents/slide_agent.py`, `services/video_composer/composer.py`

---

### B.2 Blinking Cursor in Code Reveal

**Problem:** Code reveal animation has no visual indicator of where "typing" is happening.

**Fix:** After each frame render, overlay a `█` character at the end of the last visible
line using PIL/Pillow (no LLM). Blink effect: include cursor in odd frames only.

**File:** `services/code_animator/animator.py`

---

### B.3 Code Reveal Timing Intelligence

**Problem:** Equal time per line — blank lines and comment lines get same time as
complex code lines.

**Fix:** Weighted duration per line:

- Blank line: 0.05s
- Comment line (`//`, `#`): 0.3s
- Simple line (`return 0;`, closing `}`): 0.4s
- Complex line (function call, conditional, loop): 0.8–1.5s based on character count

**File:** `services/code_animator/animator.py`

---

### B.4 More Diagram Fallback Templates

**Problem:** Only 2 hardcoded fallback diagram templates (memory, compilation).

**Fix:** Add 6 or more commonly needed C++ diagrams:

- Pointer / reference illustration (box + arrow)
- Linked list (nodes with next pointers)
- Call stack with frame push/pop
- Loop iteration counter (variable updating each step)
- Array indexing visualization
- Class inheritance tree
- Some more used diagram templates which is used across computer science

**File:** `agents/diagram_agent.py`

---

### B.5 Thumbnail A/B Variants

**Problem:** Single thumbnail per lesson. No optimization.

**Fix:** Generate 3 variants per lesson automatically:

1. Dark background, large gradient text
2. Code screenshot on right half, title on left
3. High-contrast orange/green split with lesson number

Compare CTR in GUI after publishing. Retire underperforming variants.

**File:** `agents/thumbnail_agent.py`

---

## Phase C — Audio Quality

### C.1 Voice Variety Per Course

**Problem:** Same voice for every course — viewers can tell it's TTS.

**Fix:** Allow `voice` to be configured per course in the course DB record. Options:

- `en-US-GuyNeural` — default (confident, clear)
- `en-US-EricNeural` — deeper, authoritative
- `en-US-AndrewNeural` — friendly, fast-paced
- `en-GB-RyanNeural` — British accent variant

**File:** `providers/tts/edge_tts_provider.py`, DB schema

---

### C.2 Chapter Marker Audio Cues

**Problem:** No audio signal when moving to a new major section.

**Fix:** Place a short (0.1s) subtle chime sound at the start of "section transition" segments.
Source from `assets/sounds/chime.mp3`. Mix at 20% volume.

**File:** `services/video_composer/composer.py`

---

### C.3 Silence Trimming

**Problem:** TTS sometimes produces trailing silence at the end of each segment,
causing awkward gaps between slides.

**Fix:** After synthesis, use `ffmpeg silenceremove` to strip leading and trailing silence
beyond 200ms from each audio file.

**File:** `agents/voice_agent.py`

---

## Phase D — Developer Experience

### D.1 Hot-Reload Slide Preview

**Problem:** Tweaking slide.html requires running the full pipeline to see changes.

**Fix:** CLI command that renders a single slide in isolation:

```bash
python scripts/preview_slide.py --layout code --headline "Pointers in C++" \
  --code "#include <iostream>\nint main() { int x=5; int* p=&x; }"
# → opens slide_preview.png in default image viewer instantly
```

**File:** New `scripts/preview_slide.py`

---

### D.2 Fixture Diff Tool

**Problem:** After changing a prompt, no way to know which slides changed without
manually comparing videos.

**Fix:**

```bash
python scripts/diff_fixtures.py --a tests/fixtures/v1.json --b tests/fixtures/v2.json
# Shows: slide_003 headline changed, slide_005 bullet 2 reworded, slide_007 added
```

**File:** New `scripts/diff_fixtures.py`

---

### D.3 Slide Layout Stress Test

**Problem:** Font overflow and layout breaks only discovered when running a real lesson.

**Fix:** Script that renders every layout with maximal content (5 bullets, 20-line code,
longest possible headline) and saves them all as PNGs for visual inspection:

```bash
python scripts/stress_test_layouts.py
# → output/layout_tests/*.png (one per layout variant)
```

**File:** New `scripts/stress_test_layouts.py`

---

### D.4 Partial Pipeline Replay

**Problem:** Tweaking just the composer means re-running slide rendering and audio too.

**Fix:** Add `--from-step` to the test pipeline:

```bash
python pipelines/test_pipeline.py --from-step video
# Skips slide rendering and audio if already done → jumps to FFmpeg
```

Detects already-rendered slides and audio in the output directory.

**File:** `pipelines/test_pipeline.py`

---

## Phase E — Reliability & Operations

### E.1 Structured Logging

**Problem:** All logging is `print()` — impossible to filter, search, or alert on.

**Fix:** Replace all `print()` with `structlog`. Log every agent call:

```python
log.info("agent.complete", agent="SlideAgent", lesson_id=..., duration_ms=..., tokens=...)
```

Persist to `db/pipeline_log.sqlite`. Show last 50 log lines in GUI.

**File:** All agents, `providers/llm/gemini.py`

---

### E.2 Video Quality Metrics (ffprobe Guard)

**Problem:** Composed video sometimes has wrong duration or missing audio track.

**Fix:** After every video composition, run ffprobe and verify:

- Duration is within ±5s of expected (sum of audio durations)
- Has exactly one video track at 1920×1080
- Has exactly one audio track
- File size > 1 MB (not empty/corrupt)

If any check fails → mark lesson as `failed` and log the specific mismatch.

**File:** `agents/video_agent.py`, new `services/video_composer/validator.py`

---

### E.3 Slide Image Dedup Guard (Permanent Fix)

**Problem:** Same slide image rendered multiple times due to state propagation bugs.

**Fix:** Before rendering each slide, compute a hash of:
`layout + headline + bullets + code_content`

Store in `slide_id_to_hash`. If hash matches a previous slide → copy the PNG, don't re-render.
Also serves as a render cache across runs.

**File:** `services/slide_renderer/renderer.py`

---

### E.4 Cost Budget Guard

**Problem:** A bug in a loop could make 1000 LLM calls before you notice.

**Fix:** Read `MAX_COST_USD_PER_RUN` from `.env` (default: $0.15). Before each LLM call,
check cumulative cost from SQLite. If budget exceeded → abort with a clear message.

**File:** `providers/llm/gemini.py`

---

### E.5 Failure Alerting in GUI

**Problem:** Failed lessons are silent — you only notice when looking at the course table.

**Fix:**

- Write a `FAILED.txt` marker to the lesson output directory with error + traceback
- GUI Dashboard shows a red "N lessons failed" banner at the top
- GUI lesson table highlights failed rows in red with the error message on hover

**File:** `api/server.py`, `gui/src/App.jsx`, `pipelines/full_video_pipeline.py`

---

### E.6 Retry Exponential Backoff (Per Agent)

**Problem:** Rate limit errors on Gemini cause the whole pipeline to crash. Current retry
uses `tenacity` but only on the provider level.

**Fix:** Move retry logic to the node level in the pipeline. Each agent node retries up to
5 times with exponential backoff (5s, 10s, 20s, 40s, 80s). After max retries → mark node
as failed and let checkpoint resume handle it.

**File:** `pipelines/full_video_pipeline.py`

---

## Phase F — Scale & Batch

### F.1 Course Batch Runner

**Problem:** No way to queue all lessons in a course and walk away.

**Fix:**

```bash
python scripts/generate_course.py --course-id cpp_beginner
# Generates all pending lessons sequentially
# Checkpoint-safe: if lesson 47 crashes, restart continues from lesson 47
```

Prints a live progress table (rich) showing each lesson's status.

**File:** New `scripts/generate_course.py`

---

### F.2 Concurrent Lesson Generation

**Problem:** Sequential generation of 100 lessons takes 100× the per-lesson time.

**Fix:** `multiprocessing.Pool(3)` — run 3 lessons concurrently. Each lesson writes to
its own output directory, reads the vector store read-only. No shared mutable state.

**File:** `scripts/generate_course.py`

---

### F.3 Generation Queue (Persistent)

**Problem:** Batch runner is not resumable across machine restarts.

**Fix:** Store pending lessons in a SQLite queue table:

- `INSERT` all lessons at the start
- `UPDATE status='processing'` when starting
- `UPDATE status='done'/'failed'` on completion
- On restart → pick up first `pending` lesson

GUI shows queue status — how many remain, ETA based on average per-lesson time.

**File:** `db/queue.py`, `api/server.py`, `gui/src/App.jsx`

---

## Phase G — Content Strategy

### G.1 Prerequisite Graph

**Problem:** No enforcement that concepts build logically. A viewer who skips lesson 4
may be lost in lesson 7.

**Fix:**

- `LessonPlannerAgent` assigns `prerequisites: ["lesson_002", "lesson_004"]` to each lesson
- GUI shows a prerequisite graph (D3.js / mermaid diagram)
- When a lesson is generated, its prerequisite lessons are summarized and injected into the prompt

---

### G.2 Auto-Quiz Generation

**Problem:** Passive watching — no mechanism for viewers to test understanding.

**Fix:** `QuizAgent` runs after `ScriptAgent`. Generates 3 multiple-choice questions per lesson:

```json
{
  "question": "What does sizeof(int) return on a 64-bit system?",
  "options": ["2", "4", "8", "16"],
  "correct": "4",
  "explanation": "int is always 4 bytes on both 32-bit and 64-bit systems per the C++ standard."
}
```

Quiz JSON saved in `output/<lesson>/quiz.json`. Will be used for a future interactive
quiz overlay on the course website.

---

### G.3 Timestamps Auto-Embedded in Description

**Problem:** YouTube chapter markers are manually written in SEO metadata.

**Fix:** `SEOAgent` currently generates chapter timestamps as a guess. Replace with
precise timestamps computed from cumulative audio durations — each `slide_id` maps to
a known start time.

**File:** `agents/seo_agent.py`, `agents/video_agent.py`

---

### G.4 Difficulty Curve Analysis

**Problem:** No visibility into whether the lesson sequence is appropriately paced.

**Fix:** `LessonPlannerAgent` assigns `difficulty: 1–5` to each section. After generating
all lesson plans for a course, plot difficulty over lesson number. Flag any jump > 2 in a
single lesson.
