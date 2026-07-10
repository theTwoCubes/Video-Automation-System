# USAGE.md — Developer Reference

This document covers advanced usage patterns, key design decisions, and how to extend the system.

---

## 1. Pipeline Internals

### Agent Sequence

The `full_video_pipeline.py` runs a **LangGraph** DAG where each node is one agent. Nodes run sequentially; the pipeline short-circuits on any error.

```
plan_lesson → write_script → generate_code → generate_diagrams
           → generate_slides → synthesize_voice → compose_video
           → generate_thumbnail → qa_check → generate_seo → generate_quiz
```

### Checkpointing

Every agent writes its outputs to `output/<course>/<lesson>/checkpoints/<step>.json` **after** it finishes. On the next run (or a re-render), the pipeline reads the checkpoint, skips the step, and merges the data back into state. This means:

- LLM calls are never repeated unless you delete the checkpoint.
- The `rerender_lesson.py` script works entirely from checkpoints — zero LLM cost.
- If `VideoAgent` fails due to an FFmpeg issue, re-running skips all prior steps automatically.

### `PipelineState` (TypedDict)

The shared state dictionary (`contracts/schemas.py`) carries everything between agents:
- Source/course/lesson metadata
- `script`, `slide_contents`, `audio_paths`, `slide_image_paths`
- `profile` dict (from the active YAML profile)
- `video_path`, `thumbnail_path`, `qa_report`, `seo_metadata`, etc.
- `error` — if set, all subsequent agents skip execution

---

## 2. Testing Studio (No-LLM Iteration)

The Testing Studio at `/testing` in the GUI allows iterating on render quality without LLM costs.

### How It Works

1. Pick any lesson that has previously been generated (has checkpoints on disk).
2. Choose which steps to re-run: **Slides only**, **Voice only**, **Video only**, or **All**.
3. Optionally override: voice ID, background music track, profile.
4. Click **Re-render** — live logs stream via SSE, same as Pipeline Monitor.
5. A slide gallery and a video player appear when rendering completes.

### CLI Equivalent

```bash
# Re-render just slides (new slide.html template, same script)
python scripts/rerender_lesson.py --lesson-id <UUID> --steps slides

# Re-synthesize audio with a different voice
python scripts/rerender_lesson.py --lesson-id <UUID> --steps voice --voice en-GB-RyanNeural

# Re-compose video with a different profile (e.g. no music)
python scripts/rerender_lesson.py --lesson-id <UUID> --steps video --profile no_music

# Full re-render (all steps, no LLM)
python scripts/rerender_lesson.py --lesson-id <UUID> --steps all --profile testing
```

---

## 3. Configuration Profiles

Profiles are YAML files in `config/profiles/`. They are the single source of truth for every rendering parameter. You never need to touch Python code to change a voice or disable music.

### Available Profiles

| Profile | Description |
|---|---|
| `default` | Andrew Neural voice, bg music with ducking, smooth transitions, intro+outro |
| `no_music` | Same as default but all music disabled |
| `testing` | Guy Neural voice, no music, minimal transitions, fast encoding preset |

### Creating a Custom Profile

Copy any existing profile and modify:
```bash
cp config/profiles/default.yaml config/profiles/my_profile.yaml
# Edit my_profile.yaml, then:
python scripts/rerender_lesson.py --lesson-id <UUID> --profile my_profile
```

Or create/edit profiles directly in the Testing Studio GUI.

---

## 4. Slide Layouts Reference

The slide renderer supports 9 layouts. The `SlideAgent` is prompted to use them with enforced variety rules (max 40% `content`, must have at least one structural layout per lesson).

| Layout | Use Case | Key Fields |
|---|---|---|
| `title` | First slide: lesson intro | `headline`, `subtitle`, `lesson_number` |
| `content` | General explanations | `headline`, `bullets[]` |
| `code` | Code examples | `headline`, `code`, `language`, `filename` |
| `two_column` | Side-by-side comparison | `headline`, `left_title`, `left_bullets[]`, `right_title`, `right_bullets[]` |
| `numbered_steps` | Step-by-step procedures | `headline`, `steps[]` |
| `summary` | Key takeaways at the end | `headline`, `bullets[]` |
| `definition` | Single concept spotlight | `headline`, `term`, `definition` |
| `comparison` / `error_fix` | Before/after or wrong/right | `headline`, `left_*`, `right_*` |
| `terminal` | Shell command demos | `headline`, `commands[]` |

### Previewing a Layout

```bash
python scripts/preview_slide.py --layout terminal --output preview.png
python scripts/stress_test_layouts.py   # renders all 9 to output/_test_new_design/
```

---

## 5. Voice Options

The system uses **Edge TTS** (Microsoft Azure Neural voices, completely free, no API key).

| Voice ID | Name | Character |
|---|---|---|
| `en-US-AndrewNeural` | Andrew | Warm, engaging — default |
| `en-US-GuyNeural` | Guy | Neutral, clear American male |
| `en-US-EricNeural` | Eric | Deep, authoritative |
| `en-GB-RyanNeural` | Ryan | British, professional |
| `en-US-JennyNeural` | Jenny | Clear, friendly female |
| `en-AU-WilliamNeural` | William | Australian, relaxed |

Preview any voice for 10 seconds in the Testing Studio before committing to a full re-render.

---

## 6. Audio Pipeline

### Sidechain Audio Ducking

Background music automatically lowers during narration and rises during pauses. Implemented as an FFmpeg `sidechaincompress` filter:

```
[1:a]volume=0.5[bg_raw];
[0:a]asplit=2[sc][main];
[bg_raw][sc]sidechaincompress=threshold=0.02:ratio=8:attack=100:release=1000[bg_ducked];
[main][bg_ducked]amix=inputs=2:duration=first[out_a]
```

- `ducking_ratio` in the profile controls how aggressively music ducks (default: 8.0)
- `bg_volume` sets the baseline music level before ducking

### Intro / Outro

If `use_intro: true` and `assets/music/intro_sting.mp3` exists, the pipeline:
1. Renders a branded title-card PNG using the `title` slide layout.
2. Combines it with `intro_sting.mp3` into a 5-second intro MP4.
3. Concatenates: `intro.mp4 + main_video.mp4 + outro.mp4`.

If the audio file is missing, the step is silently skipped and the main video is used as-is.

---

## 7. Adding a New Slide Layout

1. **`agents/slide_agent.py`** — add the layout name to `KNOWN_LAYOUTS` and describe its required fields in the agent prompt.
2. **`services/slide_renderer/templates/slide.html`** — add a `{% elif layout == "your_layout" %}` block with its CSS and HTML.
3. **`scripts/stress_test_layouts.py`** — add a test fixture for the new layout and run to verify.

---

## 8. Environment Variables

All settings have sensible defaults and can be overridden in `.env`:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `LLM_MODEL` | `gemini-2.5-flash` | LLM model name |
| `SQLITE_PATH` | `data/twocubes.db` | SQLite database path |
| `OUTPUT_DIR` | `output` | Root folder for generated videos |
| `MAX_COST_USD_PER_RUN` | `0.50` | Hard cost cap per pipeline run |
| `KEN_BURNS_THRESHOLD_SECONDS` | `7.0` | Slides longer than this get Ken Burns |
| `SLIDE_WIDTH` / `SLIDE_HEIGHT` | `1920` / `1080` | Slide canvas resolution |

Note: Voice, music, animation, and quality settings are now controlled by profiles, not env vars (env vars serve as fallbacks only).

---

## 9. Database Schema

Three core tables in SQLite:

- **`knowledge_sources`** — ingested PDFs/URLs, their file path, section count, and processing status.
- **`courses`** — course metadata + curriculum JSON blob + reference to a `knowledge_source`.
- **`lessons`** — individual lesson rows with position, status (`pending` → `processing` → `done`/`failed`), and path to the output directory.

The DB is managed with SQLAlchemy (no migrations needed for dev; `init_db()` creates tables on startup).

---

## 10. Cost Tracking

Every Gemini API call is logged to `data/usage.sqlite`. View the report:

```bash
python scripts/cost_report.py
# or: GET /api/usage
```

The pipeline will raise a `CostLimitExceededError` if `MAX_COST_USD_PER_RUN` is exceeded mid-run.
