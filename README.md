# theTwoCubes Learning — Video Automation

An AI-powered pipeline that converts technical books and PDFs into full-length educational YouTube videos.  
Each video includes a narrated script, synchronized slides, code examples, a thumbnail, and YouTube-ready SEO metadata — all generated automatically.

---

## How It Works

```
PDF Book ──► RAG Ingest ──► Curriculum ──► Per-Lesson Pipeline
                                                   │
                          ┌────────────────────────┤
                          │  LessonPlannerAgent     │ Structures 8-section lesson
                          │  ScriptAgent            │ ~1800 word narration script
                          │  CodeAgent              │ Validates runnable code
                          │  SlideAgent             │ Renders 10-14 PNG slides
                          │  VoiceAgent             │ Edge-TTS audio per segment
                          │  VideoAgent             │ Aligns slides + audio
                          │  ThumbnailAgent         │ 1280x720 JPEG thumbnail
                          │  QAAgent                │ Scores 0-100
                          │  SEOAgent               │ Title, description, tags
                          └─────────────────────────┘
                                    │
                            output/{course_id}/{lesson}/
                              ├── *_final.mp4
                              ├── thumbnail.jpg
                              ├── script.json
                              ├── youtube_metadata.txt
                              └── lesson_summary.json
```

---

## Requirements

- Python 3.10+
- `pip install -r requirements.txt`
- `playwright install chromium`
- `pip install imageio-ffmpeg` (bundles FFmpeg automatically)
- Gemini API key (free tier works)

---

## Quick Start

### 1. Setup

```bash
git clone <repo>
cd videoAutomation
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

### 2. Ingest a source book

```bash
python scripts/ingest.py --source-id cpp_book --path "path/to/book.pdf" --title "C++ Programming"
```

### 3. Generate a curriculum

```bash
python scripts/generate_curriculum.py \
  --source-id cpp_book \
  --course-title "C++ Programming Fundamentals" \
  --target-audience beginners \
  --num-lessons 100
```

### 4. Generate the next video

```bash
python scripts/generate_next_video.py --course-id <course-id-from-step-3>
```

Run this command once per video. Each call generates the next pending lesson.

---

## Configuration (`.env`)

| Key | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | required | Gemini API key |
| `VOICE_NAME` | `en-US-AndrewNeural` | Edge-TTS voice |
| `VOICE_RATE` | `+15%` | Speech speed |
| `TARGET_DURATION_MINUTES` | `12` | Target video length |
| `SLIDE_WIDTH` | `1920` | Slide resolution width |
| `SLIDE_HEIGHT` | `1080` | Slide resolution height |

## Logo Setup

Place PNG files with transparent backgrounds in `assets/logos/`:

| File | Used in |
|---|---|
| `SlidesLogo.png` | Top-right of every slide (300×100px) |
| `ThumbnailLogo.png` | Bottom-right of thumbnails (300×100px) |
| `MainScreenLogo.png` | Reserved for title cards |
| `EndSlideLogo.png` | Reserved for outro slide |

System falls back to text branding if files are missing.

---

## Output Structure

```
output/
└── {course_id}/
    └── 001_{lesson_id[:8]}/
        ├── {lesson_id}_final.mp4     ← upload this to YouTube
        ├── thumbnail.jpg              ← upload as custom thumbnail
        ├── youtube_metadata.txt       ← copy-paste title, description, tags
        ├── script.json                ← full narration script
        └── lesson_summary.json        ← pipeline summary + QA score
```

---

## Technology Stack

| Component | Technology | Cost |
|---|---|---|
| LLM | Gemini 2.5 Flash | Free tier / ~₹0.04/video paid |
| Embeddings | Gemini Embedding-001 | Free tier |
| TTS | Microsoft Edge-TTS | Free |
| Slide rendering | Playwright + Chromium | Free |
| Video encoding | FFmpeg (imageio-ffmpeg) | Free |
| Vector DB | ChromaDB | Free |
| Database | SQLite | Free |

---

## Project Structure

```
videoAutomation/
├── agents/          # AI agents (one per pipeline stage)
├── config/          # Settings + brand.json
├── contracts/       # TypedDict schemas (PipelineState)
├── db/              # SQLite models + migrations
├── pipelines/       # LangGraph pipeline orchestration
├── providers/       # LLM + Embedding + TTS adapters
├── scripts/         # CLI entry points
├── services/        # Slide renderer, video composer, thumbnail
├── assets/logos/    # Brand logo files (add your own)
└── output/          # Generated videos
```
