# theTwoCubes Video Automation System

An agentic pipeline that autonomously generates professional programming tutorial videos from source material (PDFs, web pages, Markdown). The system ingests knowledge, plans a curriculum, writes narration scripts, renders slides, synthesizes voice, and composites finished MP4 videos — all without manual intervention.

---

## How It Works

```
PDF / URL ──► Knowledge Ingestion ──► ChromaDB Vector Store
                                            │
                                     CurriculumAgent
                                      (30+ lessons)
                                            │
                              ┌─────────────▼─────────────┐
                              │     Full Video Pipeline    │
                              │                           │
                              │  LessonPlannerAgent       │
                              │  ScriptAgent              │
                              │  CodeAgent                │
                              │  DiagramAgent             │  ──► Animated diagram MP4s
                              │  SlideAgent               │  ──► PNG slides (1920×1080)
                              │  VoiceAgent (Edge TTS)    │  ──► MP3 audio segments
                              │  VideoAgent               │  ──► Final MP4
                              │  ThumbnailAgent           │  ──► thumbnail.jpg
                              │  QAAgent                  │  ──► qa_report.json
                              │  SEOAgent                 │  ──► youtube_metadata.txt
                              │  QuizAgent                │  ──► quiz_questions.json
                              └───────────────────────────┘
```

Each pipeline step saves a **checkpoint** to disk. If a step is re-run, the checkpoint is loaded instantly and the step is skipped — no LLM call is repeated.

---

## Features

- **Knowledge Ingestion**: Ingest PDFs, Markdown directories, or web pages into a ChromaDB vector store and SQLite-backed catalog.
- **Agentic Curriculum Planning**: Gemini 2.5 Flash generates a structured, prerequisite-aware multi-lesson curriculum from the ingested material.
- **Slide Diversity**: 35 distinct slide layouts spanning opening/structural, concept, code, comparison, process, data, engagement, warning, and summary categories (title, content, prose, split_code, quiz, warning, tip, big_number, timeline, and more) — with enforced variety rules and per-section layout recommendations from the LessonPlannerAgent.
- **Animated Diagrams**: 8 diagram types (pipeline, memory layout, call stack, iteration, flow, tree, state machine, layered architecture) rendered as animated MP4s from structured LLM content, not freehand HTML.
- **Professional Slide Rendering**: Dark-themed, brand-token-driven (no hardcoded colors), 1920×1080 slides rendered via Playwright with embedded fonts — no CDN dependency.
- **Voice Synthesis**: 6 curated Edge TTS voices (free, no API key). Sidechain audio ducking automatically lowers background music when narration plays.
- **Video Composition**: FFmpeg composites slides + audio into MP4, with configurable xfade transitions, Ken Burns slow-zoom, and optional branded intro/outro cards.
- **Testing Studio GUI**: Iterate on visuals and audio for free by re-rendering from checkpoints — no LLM calls. Live log streaming, slide gallery, and voice preview included.
- **Configuration Profiles**: All rendering parameters (voice, music, animation, FPS) live in shareable YAML files.
- **React Dashboard**: Unified frontend to manage courses, curricula, monitor pipelines, and access the Testing Studio.
- **Usage Tracking**: Per-run LLM cost tracking with configurable spend limits.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM / AI** | Google Gemini 2.5 Flash, Edge TTS |
| **Backend Pipeline** | Python 3.12, FastAPI, LangGraph, SQLAlchemy (SQLite) |
| **Knowledge Store** | ChromaDB (vector), SQLite (catalog) |
| **Slide Rendering** | Playwright → 1920×1080 PNG, Jinja2 HTML templates |
| **Video Composition** | FFmpeg (transitions, ducking, intros, Ken Burns) |
| **Voice Synthesis** | edge-tts (Azure Neural voices, free tier) |
| **Frontend** | React 19, React Router, Vite, Vanilla CSS |

---

## Project Structure

```
videoAutomation/
├── agents/                  # One agent per pipeline step
│   ├── curriculum_agent.py  # Generates the full course curriculum
│   ├── lesson_planner_agent.py  # Plans sections + recommends slide/diagram layouts
│   ├── script_agent.py      # Writes narration with engineering persona
│   ├── code_agent.py        # Generates runnable code examples
│   ├── diagram_agent.py     # Structured content → animated diagram MP4
│   ├── slide_agent.py       # Maps script to slide layout objects
│   ├── voice_agent.py       # Synthesizes TTS audio segments
│   ├── video_agent.py       # Composes final video via FFmpeg
│   ├── thumbnail_agent.py
│   ├── qa_agent.py
│   ├── seo_agent.py
│   └── quiz_agent.py
│
├── pipelines/
│   ├── full_video_pipeline.py   # LangGraph DAG: lesson → finished video
│   └── test_pipeline.py         # Fixture-based pipeline (no LLM)
│
├── services/
│   ├── video_composer/
│   │   └── composer.py          # FFmpeg: segments, transitions, ducking, intro/outro
│   ├── slide_renderer/
│   │   ├── renderer.py          # Playwright HTML → PNG
│   │   └── templates/slide.html # 35 slide layouts, brand-token-driven CSS
│   ├── diagram_renderer/
│   │   ├── renderer.py          # Structured content → animated diagram HTML
│   │   ├── html_animator.py     # Playwright frame capture → FFmpeg → MP4
│   │   └── templates/           # One file per diagram type, extends _base.html
│   ├── slide_validator/
│   │   └── validator.py         # Pre-render content validation + auto-fix
│   ├── knowledge/
│   │   └── pdf_processor.py     # PDF → sections, ChromaDB ingestion
│   ├── thumbnail/               # Pillow thumbnail generator
│   └── code_animator/           # Code reveal animation builder
│
├── config/
│   ├── settings.py              # Pydantic-settings from .env
│   ├── profile_loader.py        # Load/save YAML rendering profiles
│   ├── profiles/
│   │   ├── default.yaml         # Balanced quality + music + intro/outro
│   │   ├── no_music.yaml        # Silent rendering
│   │   └── testing.yaml         # Fast settings for iteration
│   └── brand.json               # Brand colors, channel name, and semantic tokens
│
├── api/
│   └── server.py                # FastAPI: all REST and SSE endpoints
│
├── gui/src/
│   ├── pages/
│   │   ├── Dashboard.jsx        # Knowledge ingest, course setup
│   │   ├── Curricula.jsx        # Curriculum editor
│   │   ├── PipelineMonitor.jsx  # Live generation monitor
│   │   └── TestingStudio.jsx    # No-LLM re-render + voice preview
│   └── components/
│       └── Sidebar.jsx
│
├── db/
│   ├── models.py                # KnowledgeSource, Course, Lesson ORM models
│   └── database.py              # SQLAlchemy session factory
│
├── scripts/
│   ├── generate_next_video.py   # CLI: render next pending lesson for a course
│   ├── rerender_lesson.py       # CLI: re-render slides/voice/video from checkpoints
│   ├── preview_slide.py         # CLI: render a single test slide to PNG
│   ├── review_slides.py         # CLI: batch review all slides in an output dir
│   └── stress_test_layouts.py   # CLI: render layouts with maximal content as a smoke test
│
├── assets/
│   ├── fonts/                   # Embedded base64 fonts (Outfit, FiraCode)
│   └── music/
│       ├── bg_track.mp3
│       ├── intro_sting.mp3
│       └── outro_music.mp3
│
├── contracts/schemas.py         # TypedDict: PipelineState
├── requirements.txt
└── .env.example
```

---

## Getting Started

### 1. Prerequisites

- **Python 3.12+**
- **Node.js 18+** (for the React GUI)
- **FFmpeg** — install via `winget install ffmpeg` or `brew install ffmpeg`, must be in PATH
- **Gemini API Key** — get one free at [aistudio.google.com](https://aistudio.google.com)

### 2. Install

```bash
# Python dependencies
pip install -r requirements.txt

# Install Playwright's Chromium browser
playwright install chromium

# GUI dependencies
cd gui && npm install
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

### 4. Run

```bash
# Terminal 1: Start the FastAPI backend
uvicorn api.server:app --reload --port 8000

# Terminal 2: Start the React frontend
cd gui && npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Workflow

### GUI Workflow (recommended)

1. **Dashboard** → Upload a PDF → wait for ingestion.
2. **Dashboard** → Create a Course and attach the PDF.
3. **Curricula** → Generate Curriculum → review and edit lesson list.
4. **Pipeline Monitor** → Select course → click **Generate Next Lesson**.
5. **Testing Studio** → Select the generated lesson → re-render slides/voice/video without LLM cost.

### CLI Workflow

```bash
# Generate the next pending lesson for a course
python scripts/generate_next_video.py --course-id <UUID>

# Re-render just the video for a specific lesson (no LLM)
python scripts/rerender_lesson.py --lesson-id <UUID> --steps video --profile default

# Preview a single slide layout
python scripts/preview_slide.py --layout code --output /tmp/test.png

# Smoke-test slide layouts with maximal content (overflow/clipping checks)
python scripts/stress_test_layouts.py
```

---

## Output Structure

Each generated lesson produces a self-contained folder:

```
output/<course_shortid>/<lesson_id>/
├── slides/              # PNG frames (slide_001.png … slide_NNN.png)
├── audio/               # MP3 segments per narration chunk
├── segments/            # Intermediate per-slide MP4 segments
├── checkpoints/         # JSON state snapshots for each pipeline step
├── <lesson_id>_final.mp4
├── thumbnail.jpg
├── subtitles.srt
├── quiz_questions.json
└── youtube_metadata.txt
```

---

## Configuration Profiles

Profiles live in `config/profiles/` and control all rendering parameters without code changes.

```yaml
# config/profiles/default.yaml
name: "default"
voice:
  name: "en-US-AndrewNeural"   # Edge TTS voice ID
  rate: "+0%"
  pitch: "+0Hz"
music:
  bg_track: "assets/music/bg_track.mp3"
  intro_sting: "assets/music/intro_sting.mp3"
  outro_music: "assets/music/outro_music.mp3"
  bg_volume: 0.5
  ducking_ratio: 8.0           # Sidechain compression ratio
  use_intro: true
  use_outro: true
slides:
  animation_preset: "smooth"   # minimal | smooth | dynamic
  ken_burns: false
rendering:
  fps: 30
  crf: 22
  preset: "fast"
```

Profiles can be loaded, edited, and saved from the **Testing Studio** in the GUI.

---

## API Overview

The FastAPI server exposes:

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ingest` | Ingest a PDF or URL |
| GET | `/api/courses` | List all courses |
| POST | `/api/courses` | Create a course |
| POST | `/api/curricula/generate` | Generate curriculum for a course |
| GET | `/api/courses/{id}/lessons` | List lessons with statuses |
| POST | `/api/lessons/{id}/generate` | Start video generation (background) |
| GET | `/api/logs/lessons/{id}` | SSE stream of live pipeline logs |
| POST | `/api/lessons/{id}/rerender` | Re-render from checkpoints (no LLM) |
| GET | `/api/lessons/{id}/slides` | List rendered slide image paths |
| POST | `/api/voices/preview` | Synthesize a short TTS preview clip |
| GET | `/api/profiles` | List available profiles |
| PUT | `/api/profiles/{name}` | Save a profile |
| GET | `/api/usage` | LLM token/cost usage report |
