# theTwoCubes Video Automation

AI-powered pipeline that converts a textbook chapter into a production-ready YouTube video — with animated slides, synchronized narration, subtitles, thumbnail, and SEO metadata.

## Architecture

```
PDF / Book
    │
    ▼
[Ingestion Agent] ──── ChromaDB (vector store)
    │
    ▼
[LessonPlannerAgent] → lesson_plan.json (Uses Previous Lesson Summary)
    │
    ▼
[Cost Guard] ───────── Budget verification before LLM calls
    │
    ▼
[ScriptAgent] ──────── script.json (2-Pass Generation)
    │
[CodeAgent] ─────────  code_examples[] ──> [CodeValidator]
    │
[DiagramAgent] ──────  animated MP4 diagrams (HTML+CSS via Playwright)
    │
[SlideAgent] ────────  slide specs ──> [SlideValidator] ──> PNGs
    │
[VoiceAgent] ────────  edge-tts, parallel 8 workers, loudnorm normalized + silence trimmed
    │
[VideoAgent] ────────  weighted code animation + subtitles .srt
    │
[Composer] ──────────  xfade/Ken Burns + bg music ──> [VideoValidator]
    │
[ThumbnailAgent]
    │
[QuizAgent] ─────────  quiz.json (3-5 MCQs)
    │
[QAAgent] + [SEOAgent]
    │
    ▼
output/<course_id>/<lesson_id>/
  ├── <lesson_id>_final.mp4
  ├── subtitles.srt
  ├── thumbnail.png
  ├── youtube_metadata.txt
  ├── lesson_summary.json
  ├── script.json
  ├── quiz.json
  ├── FAILED.txt            ← (if pipeline crashed)
  └── checkpoints/          ← resume from crash
```

## Slide Layouts

| Layout             | Description                                           |
| ------------------ | ----------------------------------------------------- |
| `title`          | Lesson opener — gradient headline + eyebrow          |
| `content`        | Bullets with accent dots                              |
| `code`           | Syntax-highlighted code + typewriter reveal animation |
| `numbered_steps` | Numbered circles for ordered procedures               |
| `checklist`      | Check boxes for requirements / constraints            |
| `comparison`     | Side-by-side wrong/correct code panels                |
| `error_fix`      | Red error panel + green fix panel                     |
| `terminal`       | macOS-style terminal window with green output         |
| `summary`        | 3-bullet key takeaway slide                           |
| `two_column`     | Two labeled bullet columns                            |
| `exercise`       | Challenge box with sub-bullets                        |

## Setup

* [ ] 
  ```bash
  # 1. Clone
  git clone https://github.com/theTwoCubes/videoAutomation
  cd videoAutomation

  # 2. Install Python deps
  pip install -r requirements.txt
  playwright install chromium

  # 3. Configure
  cp .env.example .env
  # Set GEMINI_API_KEY in .env

  # 4. (Optional) Install GUI deps
  cd gui && npm install && cd ..
  ```

## Running the Pipeline

```bash
# Full pipeline for a single lesson (with LLM)
python main.py --course-id cpp_beginner --lesson-id vars_001

# Batch generate an entire course (sequential, checkpoint-safe)
python scripts/generate_course.py --course-id cpp_beginner

# Test pipeline (zero LLM cost — uses fixture)
python pipelines/test_pipeline.py

# Test with specific fixture starting from a specific step (slides, audio, video, thumbnail)
python pipelines/test_pipeline.py --fixture tests/fixtures/cpp_variables_lesson.json --from-step video

# GUI dashboard (API + React)
python scripts/start_dashboard.py
# → open http://localhost:5173
```

## Test Runner

The test pipeline runs the **full rendering stack** (Playwright slides, edge-tts audio, FFmpeg video) using pre-captured LLM outputs — zero API calls:

```bash
# List available fixtures
python pipelines/test_pipeline.py --list

# Run test
python pipelines/test_pipeline.py

# Run test starting from video composition (skips slide rendering and audio synthesis)
python pipelines/test_pipeline.py --from-step video

# Capture a new fixture from a completed pipeline run
python scripts/capture_fixtures.py --lesson-id <id>

# Force re-render (ignore cached slides/audio)
python pipelines/test_pipeline.py --force-restart
```

In the **GUI**, navigate to **Test Runner** in the sidebar to run tests visually and monitor progress.

## CLI Tools

| Script                                                  | Purpose                                             |
| ------------------------------------------------------- | --------------------------------------------------- |
| `python scripts/generate_course.py`                   | Batch run all pending lessons for a course          |
| `python scripts/cost_report.py`                       | Show total API spend from SQLite log                |
| `python scripts/cost_report.py --clear`               | Reset usage log                                     |
| `python scripts/review_slides.py --lesson-id <id>`    | Human-review each slide before audio                |
| `python scripts/capture_fixtures.py --lesson-id <id>` | Save LLM outputs as test fixture                    |
| `python scripts/preview_slide.py`                     | Hot-reload visual preview for slide layouts         |
| `python scripts/stress_test_layouts.py`               | Renders all layout combinations to check boundaries |
| `python scripts/start_dashboard.py`                   | Launch GUI dashboard                                |

## Checkpoint / Resume

Every pipeline stage writes a checkpoint JSON to `output/<course>/<lesson>/checkpoints/`. If a run crashes, restarting it skips already-completed stages — no repeat LLM calls.

```bash
# Resume crashed run
python main.py --course-id cpp --lesson-id vars_001
# (completed stages auto-detected and skipped)

# Force full restart
python main.py --course-id cpp --lesson-id vars_001 --force-restart
```

## Background Music

Drop MP3 files into `assets/music/`:

- `bg_track.mp3` — mixed at 8% volume under narration
- `intro_music.mp3` — plays during intro slide
- `outro_music.mp3` — plays during outro slide

## Configuration

Key settings in `.env`:

```env
GEMINI_API_KEY=...
LLM_MODEL=gemini-2.5-flash-preview-04-17
SLIDE_WIDTH=1920
SLIDE_HEIGHT=1080
OUTPUT_DIR=output
SQLITE_PATH=db/usage.sqlite
```

## Project Structure

```
videoAutomation/
├── agents/              # LLM orchestration agents
├── api/                 # FastAPI backend for GUI
├── config/              # Settings + pronunciation lexicon
├── contracts/           # PipelineState TypedDict schema
├── db/                  # SQLite usage log
├── gui/                 # React+Vite dashboard
├── pipelines/           # full_video_pipeline.py + test_pipeline.py
├── providers/           # LLM + TTS providers
├── scripts/             # CLI tools
├── services/
│   ├── code_animator/   # Typewriter code reveal
│   ├── diagram_renderer/# HTML+CSS animated diagrams
│   ├── slide_renderer/  # Playwright → PNG slides
│   └── video_composer/  # FFmpeg assembly
└── tests/
    └── fixtures/        # Pre-captured LLM outputs for testing
```
