# USAGE.md — theTwoCubes Video Automation

## Cost Analysis

### Real-world cost for one 10-minute lesson video

All measurements use `gemini-2.5-flash` (thinking disabled, `thinking_budget=0`).

| Agent | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|
| LessonPlannerAgent | 1 | ~2 000 | ~800 | $0.00038 |
| ScriptAgent | 1 | ~3 500 | ~2 000 | $0.00086 |
| CodeAgent | 1 | ~2 000 | ~1 200 | $0.00046 |
| DiagramAgent | 1–3 | ~2 500 | ~4 000 | $0.00146 |
| SlideAgent | 1 | ~4 000 | ~3 000 | $0.00120 |
| QAAgent | 1 | ~3 000 | ~500 | $0.00105 |
| SEOAgent | 1 | ~2 500 | ~800 | $0.00090 |
| QuizAgent | 1 | ~3 000 | ~1 000 | $0.00120 |
| **Total** | **8–10** | **~22 500** | **~13 300** | **~$0.0075** |

**Per video: ≈ $0.0075 USD (~₹0.60)**

### 100-lesson C++ course (based on 300-page book)

| Resource | Quantity | Cost |
|---|---|---|
| Gemini API (all agents × 100 lessons) | ~1 000 calls | ~$0.75 USD (~₹60) |
| edge-tts (Microsoft TTS) | 100 lessons | **Free** |
| Playwright rendering | 100 × ~8 slides | **Free** |
| FFmpeg video composition | 100 videos | **Free** |
| **Total** | | **~$0.75 USD (~₹60)** |

> **Upper bound**: $1.50 USD for a full 100-video course if every lesson is unusually long and uses Retry + complex diagrams.

### Token budget breakdown

- 1 lesson plan: ~2 800 tokens
- 1 full script (7 segments × ~200 words): ~3 500 tokens
- 1 code block (runnable, complete): ~800 tokens
- 1 animated diagram (HTML CSS): ~4 000 tokens
- 7 slide specs: ~3 000 tokens output
- 1 QA check + 1 SEO block + 1 Quiz block: ~4 500 tokens combined

---

## Testing System

### Why a test harness?

Every rendering code change (new slide layout, transition tweak, font size fix) previously required a full LLM run to verify the output — expensive and slow. The test pipeline solves this by pre-capturing all LLM outputs once and replaying only the rendering stages on every subsequent run.

### Workflow

```
First run (one time, costs money):
  python main.py → complete pipeline → checkpoints saved

Capture fixture (one time, free):
  python scripts/capture_fixtures.py --lesson-id <id>
  → tests/fixtures/<name>.json

Every iteration (zero cost):
  python pipelines/test_pipeline.py --from-step slides
  → Slides rendered (Playwright)
  → Audio synthesized (edge-tts, free)
  → Video composed (FFmpeg, free)
  → Output in output/test_course/test_<lesson_id>/

Partial iteration (e.g., tweaking just FFmpeg animations):
  python pipelines/test_pipeline.py --from-step video
  → Skips Playwright & edge-tts
  → Video composed (FFmpeg)
```

### Running from GUI

1. Start dashboard: `python scripts/start_dashboard.py`
2. Open http://localhost:5173
3. Click **Test Runner** in sidebar
4. Select a fixture (shows slide count + segment count)
5. Select a **Start from** step (`slides`, `audio`, `video`, `thumbnail`) to skip earlier unchanged stages
6. Optionally enable **Force restart** to clear caches
7. Click **Run Test** → watch pipeline stages update live
8. Click a previous run in history to re-inspect video output and validation metrics

### Creating new fixtures

**From a completed pipeline run (recommended):**
```bash
python scripts/capture_fixtures.py --lesson-id <lesson_id>
# → tests/fixtures/<lesson_id>.json
```

**From a raw output directory:**
```bash
python scripts/capture_fixtures.py --output-dir output/cpp/003_abc12345
# → tests/fixtures/test.json
```

**Manually:** Write a JSON file in `tests/fixtures/` following the schema in `tests/fixtures/cpp_variables_lesson.json`. Required fields:
- `lesson_title`, `lesson_id`, `course_title`
- `script.segments[]` — each with `type`, `slide_id`, `text`
- `slide_contents[]` — each with `id`, `layout`, `headline`, and layout-specific fields
- `code_examples[]` (optional but recommended for code slides)

### Fixture schema

```json
{
  "lesson_id": "string",
  "lesson_title": "string",
  "course_title": "string",
  "lesson_position": 1,
  "script": {
    "segments": [
      { "type": "narration", "slide_id": "slide_001", "text": "narration text..." },
      { "type": "code_demo", "slide_id": "slide_005", "code_ref": "code_001", "text": "..." }
    ]
  },
  "slide_contents": [
    {
      "id": "slide_001",
      "layout": "title|content|code|numbered_steps|checklist|comparison|error_fix|terminal|summary|exercise",
      "headline": "string",
      "bullets": [],
      "code_content": "",
      "transition_hint": "fade|zoomin|wipeleft|wiperight",
      "left_bullets": [], "right_bullets": [],
      "left_label": "", "right_label": "",
      "tag": "HOOK|CONCEPT|CODE|MISTAKES|SUMMARY|EXERCISE",
      "lesson_number": 1
    }
  ],
  "code_examples": [{ "id": "code_001", "source_code": "..." }],
  "seo_metadata": { "title": "", "description": "", "tags": [], "chapters": [] },
  "qa_report": { "score": 90, "passed": true },
  "quiz_questions": [
    {
      "question": "string",
      "options": ["A", "B", "C", "D"],
      "correct_answer": 0,
      "explanation": "string"
    }
  ]
}
```

---

## Batch Processing & Validation

The pipeline includes built-in safeguards and batch tools:

- **Batch Generation**: `python scripts/generate_course.py --course-id <id>` will queue all lessons.
- **Cost Guard**: Set `MAX_COST_USD_PER_RUN=0.10` in `.env` to prevent budget blowouts.
- **Validation**: Includes automatic `SlideValidator` (auto-fixes too long bullets), `CodeValidator` (regex sanity checks), and `VideoValidator` (checks final MP4).
- **GUI Alerts**: The dashboard shows a red banner if any lesson creates a `FAILED.txt` during generation.

The following is a prioritized list of improvements to reach full production quality.

### Priority 1 — Output Quality (High Impact, Achievable Now)

#### 1.1 Slide Content Intelligence
- **Slide validator**: Before rendering, check each slide against rules (max 5 bullets, no vague text, code must have `return 0`, etc.)
- **Automatic headline shortener**: If headline > 8 words, trim with an LLM micro-call (cheap, <50 tokens)
- **Bullet density score**: Flag slides where bullets are too short (<6 words) or too long (>15 words)

#### 1.2 Better Code Reveal Timing
- Currently: equal time per line. Better: weight time by line complexity — blank lines get 0.05s, comment lines 0.3s, actual code lines 0.8–1.5s
- Add a blinking cursor character `█` at the end of the current line being "typed"
- Minimum frame count: if code has 3 lines, still show intro for 2s before starting reveal

#### 1.3 Voice Quality
- **Pause insertion**: Add `<break time="600ms"/>` SSML tags after topic transitions in narration text
- **Pronunciation lexicon expansion**: Add 50+ CS/C++ terms (e.g., `cout` → "see out", `endl` → "end el", `nullptr` → "null pointer")
- **Voice variety**: Use different edge-tts voices per course (en-US-GuyNeural for C++, en-US-JennyNeural for Python)

#### 1.4 Diagram Animation Polish
- Add easing to CSS animations (`cubic-bezier(0.34, 1.56, 0.64, 1)` for bounce-in elements)
- Generate 3–4 hardcoded fallback templates for common C++ concepts: pointer diagram, call stack, loop iteration, linked list node
- Diagram playback speed: slow reveal for first 2s, hold for 2s, then fade out — synced to narration

### Priority 2 — Iteration Speed (Developer Experience)

#### 2.1 Hot-reload Slide Preview
- A CLI command `python scripts/preview_slide.py --layout code --code "int x = 5;"` that renders a single slide and opens it
- Used during template development without running the full pipeline

#### 2.2 Fixture Diff Tool
- `python scripts/diff_fixtures.py --a fixture_v1.json --b fixture_v2.json` — shows which slides changed between two captured runs
- Helps identify regressions after prompt changes

#### 2.3 Slide Layout Stress Test
- A script that renders every layout type with maximal content (5 bullets, 20-line code block, etc.) and saves all as PNGs
- Catches font overflow and layout break issues without running audio/video

#### 2.4 Partial Pipeline Replay
- Add `--from-step` flag to test_pipeline: `--from-step video` skips slide rendering and audio if already done
- Useful for tweaking just the FFmpeg parameters

### Priority 3 — Video Quality (Visual Polish)

#### 3.1 Slide Transitions per Layout
- Currently all slides use the same `fade` xfade. Better: `wipeleft` for sequential slides, `zoomin` for emphasis slides, `fade` for summary
- Store `transition_hint` in slide content JSON

#### 3.2 B-roll Footage
- For content slides with no code, overlay a subtle animated background pattern (geometric shapes, particle grid) using CSS canvas
- Renders as the slide background — no external footage needed

#### 3.3 Progress Audio Cues
- A short 0.1s "tick" sound on each new slide (optional, from `assets/sounds/tick.mp3`)
- Mixed at very low volume using FFmpeg during composition

#### 3.4 Zoom/Ken Burns on Static Slides
- For long static slides (>8s), apply a slow zoom-in FFmpeg filter: `zoompan=z='min(zoom+0.0002,1.05)':d=1:s=1920x1080`
- Makes static slides feel dynamic without code animation

### Priority 4 — Content Generation Quality (Prompt Engineering)

#### 4.1 Two-pass Script Generation
- Pass 1: Generate rough script with all key points
- Pass 2: Revise each segment for pacing — max 35 words per narration, no sentence > 20 words
- Cost: 2× script agent calls, but dramatically improves narration quality

#### 4.2 Code Example Validation
- After CodeAgent generates code, run it through a static analysis check (regex for common C++ mistakes: missing `return`, unclosed braces, etc.)
- If it fails, auto-retry with the error as context

#### 4.3 Lesson Continuity Awareness
- Pass previous lesson's `seo_title` and `summary.bullets` into the LessonPlannerAgent prompt
- Prevents repetition and ensures concepts build on each other

#### 4.4 Slide Spec Review Loop
- After SlideAgent generates specs (before rendering), run a micro LLM check: "Is this slide too vague? Return YES/NO + reason"
- If YES, regenerate that specific slide — costs ~100 tokens, saves bad slide from being rendered

### Priority 5 — Reliability & Monitoring

#### 5.1 Structured Logging
- Replace `print()` with `structlog` everywhere
- Log every agent call with: agent_name, lesson_id, duration_ms, token_count, slide_count
- Persist logs to `db/pipeline_log.sqlite`

#### 5.2 Alerting on Failures
- If a lesson fails, write a `FAILED.txt` marker in the output directory with the error and traceback
- GUI shows a red banner with "N failed lessons" on the dashboard

#### 5.3 Video Quality Metrics
- After composition, run `ffprobe` to verify: video duration matches expected (±5s), has audio track, resolution is 1920x1080
- Log metrics to `lesson_summary.json`

#### 5.4 Slide Image Dedup Guard
- Before rendering, hash each slide spec's key fields (`layout + headline + bullets`)
- If the hash matches a previously rendered slide, skip rendering and reuse the image
- Prevents the "same slide repeated" bug permanently

### Priority 6 — Scale (Batch Processing)

#### 6.1 Course Batch Runner
- `python scripts/generate_course.py --course-id cpp_beginner` — generates all N lessons sequentially
- With checkpoint support: if run crashes at lesson 47, restart resumes from lesson 47

#### 6.2 Concurrent Lesson Generation
- Run up to 3 lessons in parallel using `multiprocessing.Pool(3)`
- Each lesson is independent — they share only the vector store (read-only)

#### 6.3 Cost Budget Guard
- Set `MAX_COST_USD_PER_RUN=0.10` in `.env`
- Pipeline checks cumulative cost from SQLite log before each agent call
- Aborts with a clear message if budget exceeded

---

## File Size Reference

| Output file | Typical size |
|---|---|
| One 10-minute lesson MP4 | 80–150 MB |
| Thumbnail PNG | 200–400 KB |
| Subtitles SRT | 5–15 KB |
| All slides (7 PNGs) | 3–6 MB |
| All audio segments | 4–8 MB |
| Checkpoints JSON | < 100 KB |
| 100-video course total | 8–15 GB |
