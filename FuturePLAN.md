# theTwoCubes — Production-Grade Video Automation Roadmap

> **Status:** Iteration 4 complete. The UI has been completely rebuilt using professional, monochrome Tailwind CSS, and the Knowledge Base workflow is now strictly isolated and accessible per course.

This document tracks the next phase of enterprise-grade features needed to scale the system for fully automated, high-volume production.

---

## ✅ Already Implemented (V4)
- **Course-Scoped Knowledge Base:** True 1-to-1 relationships allowing users to dynamically upload PDFs or URLs into an already created course.
- **UI Redesign (Tailwind CSS):** Rebuilt the React frontend from scratch using a strict, monochrome design system (blacks, zinc-900, crisp typography) without clumsy gradients.
- **Knowledge Base Retrieval UI:** Added an interactive ChromaDB query tool directly inside the UI to let instructors test whether the LLM is fetching the correct chunks before starting rendering.
- **Granular Error Recovery:** Node-level try-catch blocks in LangGraph to gracefully handle agent crashes without halting the server thread.
- **Strict RAG Chunking:** Semantic chunker strictly enforces character limits to prevent data truncation mid-word.
- **CSR URL Extraction:** Integration with Playwright to extract content from modern JavaScript-heavy documentation websites.
- **Disk Bloat Prevention:** Automatic media file cleanup (`.mp4`, `.png`, etc.) on forced fresh restarts.

---

## Phase A — Orchestration & Scaling (Highest Priority)

> Move from an in-memory script runner to an enterprise task queue.

### A.1 Distributed Task Queue (Celery/Redis)
**Problem:** Currently, the FastAPI backend tracks running LangGraph jobs using in-memory dictionaries. If the server restarts or crashes, all job states are lost and frontend updates halt.
**Fix:** Migrate all background processing to Celery workers using Redis as a message broker. Track task status strictly in the `lessons` and `knowledge_sources` database tables.

### A.2 Automated Retry with Exponential Backoff
**Problem:** While the LLM provider has `tenacity` retries, pipeline-level failures (e.g. FFmpeg crash, Playwright timeout) cause the job to fail permanently.
**Fix:** Implement Celery task retries for transient non-LLM errors (like network timeouts or temporary disk locks).

---

## Phase B — Advanced Media & Aesthetics

> Enhance viewer retention with dynamic, cinematic editing.

### B.1 Dynamic B-Roll Injection
**Problem:** Long stretches of talking-head narration or text slides can become monotonous.
**Fix:** Integrate with the Pexels or Unsplash APIs. During long `narration` segments without code or diagrams, fetch context-relevant stock video clips and overlay them as B-Roll.

### B.2 Advanced Audio Ducking
**Problem:** Background music remains at a constant volume.
**Fix:** Implement dynamic audio ducking in FFmpeg so the background music drops in volume when the TTS voice speaks, and swells during transitions or slide changes.

### B.3 Remotion Code Animations
**Problem:** Playwright typewriter animations are clean but basic.
**Fix:** Export code segments to a dedicated animation engine (like Remotion) to highlight AST changes, arrows pointing to variables, and complex flow diagrams.

---

## Phase C — Curriculum Intelligence

> Let the AI critique and adapt its own teaching style.

### C.1 Self-Correcting Feedback Loops
**Problem:** The system generates a `QA Score` via the `QAAgent`, but this score doesn't influence future generation.
**Fix:** If a lesson scores poorly (e.g., too fast-paced, dense concepts), automatically log this in the `Course` metadata. When generating the *next* lesson, inject a prompt: *"Warning: The previous lesson was flagged as too fast-paced. Spend 20% more time explaining foundational concepts."*
