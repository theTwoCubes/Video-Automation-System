# theTwoCubes Video Automation System

An advanced, agentic pipeline for generating high-quality programming tutorial videos entirely autonomously. The system uses RAG to ingest knowledge (PDFs, URLs), plans curricula, writes scripts, generates code animations via headless browsers (Playwright), synthesizes voice (Edge TTS), and composites final videos with FFmpeg.

## Features

- **Knowledge Ingestion**: Ingest PDFs, Markdown directories, or web pages into a ChromaDB vector store.
- **Agentic Curriculum Generation**: LLM-driven generation of comprehensive multi-lesson courses with structured learning paths.
- **Automated Video Production**: 
  - Generates scripts and slide content.
  - Renders professional, high-contrast, Vercel/Stripe-styled slides.
  - Automatically times audio (TTS) and composites transitions.
- **GUI Dashboard**: A unified React frontend (Vite) and FastAPI backend to monitor pipelines, view logs, and manage curricula in real-time.

## Tech Stack

- **Backend Pipeline**: Python 3.12, FastAPI, LangGraph, ChromaDB, SQLAlchemy.
- **Video Rendering**: Playwright (HTML to PNG), FFmpeg (Composition, Transitions, Audio Mixing).
- **LLM / AI**: Google Gemini 2.5 Flash, Edge TTS.
- **Frontend**: React 19, React Router, Vite, Vanilla CSS.

## Getting Started

### 1. Requirements

- **Python 3.12+**
- **Node.js** (for running the React GUI)
- **FFmpeg**: Must be installed and available in your system `PATH`.
- **API Key**: Ensure `GEMINI_API_KEY` is set in your `.env` file.

### 2. Setup

Install Python dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

Install GUI dependencies:
```bash
cd gui
npm install
```

### 3. Running the System

Start the FastAPI Backend:
```bash
uvicorn api.server:app --reload --port 8000
```

Start the React Frontend:
```bash
cd gui
npm run dev
```

Navigate to `http://localhost:5173` to access the Dashboard. You can ingest knowledge, generate a curriculum, and monitor the automated video production pipeline directly from the UI.
