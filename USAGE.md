# Usage & Future Improvements

## 1. Local Testing System

To rapidly iterate on the video generation logic (such as transitions, slide rendering, or audio padding) without incurring API costs or waiting for LLM generation, the system includes an **Automated Test Pipeline**.

### Running Tests from the GUI
1. Navigate to the **Pipeline Monitor** tab in the Dashboard.
2. Click **Run Test (C++ Variables)** under the "Run Automated Test" section.
3. The system will use cached LLM outputs (`tests/fixtures/cpp_variables_lesson.json`) to bypass the planning/scripting phases and directly execute the FFmpeg compilation and slide rendering.

### Benefits of the Test System
- **Speed**: Renders a complete video in seconds instead of minutes.
- **Cost**: No LLM API calls are made.
- **Stability**: Provides a deterministic baseline to verify FFmpeg transition math and visual styling.

---

## 2. Roadmap to a Production-Grade System

While the current architecture is robust, the following improvements are planned to scale the system for enterprise-grade video production:

### Phase A: Resiliency & Recovery
- **Idempotent Pipeline Steps**: Currently, a failure in FFmpeg requires restarting the entire lesson generation. We will implement granular checkpointing so that if `VideoAgent` fails, it resumes exactly at the failed segment rather than re-rendering all slides.
- **Task Queues (Celery/Redis)**: Replace the in-memory FastAPI `BackgroundTasks` with a robust task queue to handle distributed rendering and survive server restarts.

### Phase B: Advanced Media & Animation
- **Dynamic B-Roll**: Integrate Pexels or Unsplash APIs to inject contextual B-Roll video during long stretches of talking head or summary slides.
- **Complex Code Animations**: Migrate from static code highlights to dynamic AST-based typing animations (e.g., using Remotion or Manim).
- **Audio Ducking**: Implement advanced audio ducking in `composer.py` to lower background music dynamically when the TTS voice speaks, and raise it during transitions.

### Phase C: Curriculum Intelligence
- **Feedback Loops**: Allow the LLM to review the output of `test_summary.json` (QA scores) and self-correct subsequent lessons in the curriculum if they are too short or too dense.
- **Multi-Modal Generation**: Use Gemini 2.5 Flash's native multi-modal capabilities to generate diagrams directly as SVG instead of relying on Mermaid.js string generation.
