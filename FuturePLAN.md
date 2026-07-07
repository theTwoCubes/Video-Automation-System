# theTwoCubes — Production-Grade Video Automation Roadmap

> **Status:** Iteration 2 complete. The pipeline is functional and produces real videos.
> This document tracks everything needed to go from "working prototype" to "production system."

---

## ✅ Already Implemented

| Feature | Notes |
|---|---|
| Checkpoint / Resume system | JSON checkpoints per agent, survives crashes |
| Parallel audio synthesis | ThreadPoolExecutor, 8 workers |
| Token & cost tracker | SQLite usage_log + cost_report.py CLI |
| Audio normalization | ffmpeg loudnorm on all segments |
| Slide transitions | FFmpeg xfade between all segments |
| Background music mixing | assets/music/bg_track.mp3 at 8% volume |
| Adaptive font sizing | JS auto-scale in slide template |
| Inline syntax highlighter | C++ / Python tokenizer, no CDN |
| 11 slide layouts | numbered_steps, comparison, checklist, error_fix, terminal + originals |
| Progress bar + slide counter | On every slide |
| Code reveal animation | Line-by-line typewriter via Playwright + FFmpeg |
| HTML/CSS animated diagrams | Playwright frame capture → MP4, fallback templates |
| Subtitle .srt generation | Timing-based from audio durations |
| Intro & Outro slides | Branded templates + optional music |
| Slide review CLI | review_slides.py — approve/flag before audio |
| Fixture-based test pipeline | Zero LLM calls, full render stack |
| Test Runner GUI | React dashboard with live polling |
| FastAPI backend | Serves courses, lessons, test runs, usage |
| Cost report GUI | Per-model breakdown in dashboard |

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

- Reject bullets shorter than 6 words or longer than 18 words
- Reject headlines with vague words: "understanding", "exploring", "introduction to"
- Require code slides to have `return` or a function signature
- Require `summary` slides to have exactly 3 bullets
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

---

### A.4 Code Validation (Static Analysis)

**Problem:** `CodeAgent` sometimes generates code that doesn't compile (missing semicolons,
wrong include, undefined variable).

**Fix:** After code generation, run a fast static check:
- Check brace balance (simple regex counter)
- Confirm `#include` appears if `cout` / `cin` / `endl` is used
- Confirm `return 0;` exists in `main()`
- If any check fails → auto-retry CodeAgent with error context

**File:** `agents/code_agent.py`, new `services/code_validator/checker.py`

---

### A.5 Narration Pacing Score

**Problem:** Some segments are too fast (30 words, 2 seconds of audio = rushed), some
too slow (5 words, 4 seconds = awkward silence).

**Fix:** After `VoiceAgent` finishes, compute words-per-minute for each segment.
Flag segments outside 100–160 WPM range in `lesson_summary.json`.
Show flagged segments in the GUI slide detail view.

---

### A.6 SSML Pause Tags

**Problem:** Narration has no breathing room between topic transitions.

**Fix:** In `ScriptAgent` prompt, instruct it to insert `[PAUSE]` markers between major
topic shifts. In `VoiceAgent`, replace `[PAUSE]` with 600ms of silence via:

```python
pydub.AudioSegment.silent(duration=600)
```

**File:** `agents/voice_agent.py`, `agents/script_agent.py`

---

### A.7 Auto Pronunciation Lexicon (Expanded)

**Problem:** TTS mispronounces: `cout` ("cout"), `endl` ("end-l"), `nullptr` ("null-pt-er"),
`argc` ("ar-gee-see"), `argv` ("ar-gee-vee"), `uint32_t` ("oo-int-32-t").

**Fix:** Expand `config/pronunciation_lexicon.py` to 100+ CS terms with phonetic
replacements. Use a community-curated list as source.

---

## Phase B — Visual Excellence (Slides)

### B.1 Ken Burns Effect on Long Static Slides

**Problem:** Static slides longer than 8 seconds feel dead.

**Fix:** For slides where the audio duration exceeds 7 seconds, apply a slow zoom:

```
ffmpeg -i slide.png -vf "zoompan=z='min(zoom+0.0001,1.04)':d=1:s=1920x1080,fps=30"
```

Detect duration from audio file. Only apply to non-code slides.

**File:** `services/video_composer/composer.py`

---

### B.2 Per-Layout Slide Transitions

**Problem:** All slides use the same `fade` xfade. Monotonous.

**Fix:** Store `transition_hint` in slide spec JSON. Map layouts to transitions:

| Layout | Transition |
|---|---|
| `title` → first content | `zoomin` |
| `content` → `content` | `fade` |
| `code` → next | `wipeleft` |
| Any → `summary` | `fadeblack` |
| Any → `exercise` | `slideleft` |

**File:** `agents/slide_agent.py`, `services/video_composer/composer.py`

---

### B.3 Blinking Cursor in Code Reveal

**Problem:** Code reveal animation has no visual indicator of where "typing" is happening.

**Fix:** After each frame render, overlay a `█` character at the end of the last visible
line using PIL/Pillow (no LLM). Blink effect: include cursor in odd frames only.

**File:** `services/code_animator/animator.py`

---

### B.4 Code Reveal Timing Intelligence

**Problem:** Equal time per line — blank lines and comment lines get same time as
complex code lines.

**Fix:** Weighted duration per line:
- Blank line: 0.05s
- Comment line (`//`, `#`): 0.3s
- Simple line (`return 0;`, closing `}`): 0.4s
- Complex line (function call, conditional, loop): 0.8–1.5s based on character count

**File:** `services/code_animator/animator.py`

---

### B.5 More Diagram Fallback Templates

**Problem:** Only 2 hardcoded fallback diagram templates (memory, compilation).

**Fix:** Add 6 more commonly needed C++ diagrams:
- Pointer / reference illustration (box + arrow)
- Linked list (nodes with next pointers)
- Call stack with frame push/pop
- Loop iteration counter (variable updating each step)
- Array indexing visualization
- Class inheritance tree

**File:** `agents/diagram_agent.py`

---

### B.6 Thumbnail A/B Variants

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

### D.5 Visual Regression Testing

**Problem:** A slide template change might break slide 3 layout across all fixtures,
but you only notice when watching the full video.

**Fix:** After each test run, compare slides pixel-by-pixel against a "golden" reference:
- Store reference PNGs in `tests/golden/<fixture_name>/slide_*.png`
- If diff exceeds 1% of pixels → print warning with side-by-side image
- CLI: `python scripts/visual_regression.py --fixture cpp_variables`

**File:** New `scripts/visual_regression.py`

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

---

## Phase H — Long-Term / Ambitious

> These require significant external dependencies or research. Plan for 3–6 months out.

### H.1 Real Terminal Recording (asciinema)

**Problem:** "Terminal" slides show fake output that looks designed, not real.

**Fix:**
1. `CodeAgent` generates working C++ code
2. A subprocess compiles it with `g++` and runs it via `asciinema rec`
3. `asciinema` recording is converted to a video using `agg` (asciinema gif generator)
4. Embedded into the video at the correct position

**Requires:** g++ on PATH, asciinema, agg.

---

### H.2 Shorts Auto-Generation (9:16 Format)

**Problem:** 10-minute lessons can't go on YouTube Shorts. Missing a huge growth channel.

**Fix:** For each lesson, identify the single most "hook-worthy" 45-second segment
(the `HOOK`-tagged slide + its narration). Re-render at 1080×1920 (vertical) with larger
fonts, and export as a separate Shorts MP4.

**File:** New `pipelines/shorts_pipeline.py`

---

### H.3 Multi-Language Narration

**Problem:** English-only limits audience.

**Fix:**
1. Translate each narration segment using Gemini (cheap: pure text)
2. Synthesize in target language using edge-tts (has: Hindi, Spanish, French, German, Arabic)
3. Generate parallel video with translated audio

**Cost:** ~$0.002 extra per translated lesson (translation tokens only).

---

### H.4 Course Website Auto-Generation

**Problem:** YouTube is the only distribution channel.

**Fix:** After generating a full course, auto-generate a `Next.js` / `Nextra` static site:
- One page per lesson with embedded video, script transcript, and quiz
- Searchable via Pagefind (local, no backend needed)
- `python scripts/generate_course_site.py --course-id cpp_beginner`
- Deployable to Vercel / Cloudflare Pages for free

---

### H.5 Analytics Feedback Loop

**Problem:** No signal from actual viewers on what works and what doesn't.

**Fix:**
1. YouTube Analytics API: pull retention data per lesson after 7 days
2. Identify segments where viewers drop below 60% retention
3. Flag those segments in the GUI with timestamp + retention %
4. On next version of the lesson, pass retention data to `ScriptAgent`: "viewers dropped off at 4:30 — this is the pointer arithmetic section — rewrite it more clearly"

**Requires:** YouTube Analytics API OAuth (read-only).

---

## Priority Stack (What to Build Next)

| # | Feature | Impact | Effort | Phase |
|---|---|---|---|---|
| 1 | Slide Content Validator | High | 1 day | A.2 |
| 2 | Two-Pass Script Generation | High | 2 days | A.1 |
| 3 | SSML Pause Tags | High | 0.5 day | A.6 |
| 4 | Ken Burns on long slides | Medium | 0.5 day | B.1 |
| 5 | Code Reveal Timing Intelligence | Medium | 1 day | B.4 |
| 6 | Hot-Reload Slide Preview | High (DX) | 0.5 day | D.1 |
| 7 | Partial Pipeline Replay | High (DX) | 0.5 day | D.4 |
| 8 | Slide Layout Stress Test | High (DX) | 0.5 day | D.3 |
| 9 | Per-Layout Transitions | Medium | 1 day | B.2 |
| 10 | Lesson Continuity Awareness | High | 1 day | A.3 |
| 11 | Silence Trimming | Medium | 0.5 day | C.3 |
| 12 | Cost Budget Guard | Medium | 0.5 day | E.4 |
| 13 | Video Quality Metrics Guard | High | 1 day | E.2 |
| 14 | Failure Alerting in GUI | Medium | 1 day | E.5 |
| 15 | Course Batch Runner | High | 1 day | F.1 |
| 16 | Auto-Quiz Generation | High (UX) | 2 days | G.2 |
| 17 | Visual Regression Testing | High (DX) | 1 day | D.5 |
| 18 | Prerequisite Graph | Medium | 2 days | G.1 |
| 19 | Shorts Auto-Generation | High (growth) | 3 days | H.2 |
| 20 | Multi-Language Narration | High (reach) | 2 days | H.3 |
