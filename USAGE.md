# Usage & Features

## 1. Testing Studio (No-LLM Iteration)

The system includes a dedicated **Testing Studio** in the GUI to rapidly iterate on video generation without incurring LLM API costs or waiting for text generation. 

### Features of the Testing Studio
1. **Checkpoint Resumption**: Select any previously generated lesson and reload its exact state (script, slide contents) from disk.
2. **Granular Re-rendering**: Choose to re-render only the slides, re-synthesize the voice, or re-compose the final video.
3. **Voice Previews**: Listen to 10-second previews of any configured Edge TTS voice before applying it to the full lesson.
4. **Live Logs & Gallery**: Watch the FFmpeg compilation logs in real-time and review a gallery of generated slide images before finalizing.

## 2. Configuration Profiles

You can control nearly every aspect of the final video using YAML Configuration Profiles located in `config/profiles/`. 
Profiles allow you to set:
- **Voice**: Azure/Edge TTS voice ID, pitch, and rate.
- **Music**: Background tracks, intro stings, outro music, and sidechain ducking ratios.
- **Slides**: Visual themes, layout rules, animation presets (e.g. `smooth`, `dynamic`), and Ken Burns effects.
- **Rendering**: Target FPS and CRF quality.

## 3. Advanced Media Pipeline

The `video_composer` implements several advanced FFmpeg techniques:
- **Sidechain Audio Ducking**: Background music automatically lowers its volume when the TTS voice is speaking and rises during pauses.
- **Intros & Outros**: Automated generation of branded title cards and subscribe screens, mixed with dedicated intro/outro audio stings.
- **Slide Transitions**: Per-layout crossfades and dynamic wipes (e.g., sliding code panels).
- **Code Reveals**: Syntax-highlighted code panels animate in progressively to match the narrator's pacing.

---

## 4. Roadmap to a Production-Grade System

While the current architecture is robust, the following improvements are planned to scale the system for enterprise-grade video production:

### Phase A: Resiliency & Distributed Computing
- **Task Queues (Celery/Redis)**: Replace the in-memory FastAPI `BackgroundTasks` with a robust task queue to handle distributed rendering and survive server restarts.
- **Cloud Rendering**: Offload FFmpeg composition and Playwright rendering to scalable serverless workers.

### Phase B: Advanced Media & Animation
- **Dynamic B-Roll**: Integrate Pexels or Unsplash APIs to inject contextual B-Roll video during long stretches of talking head or summary slides.
- **Complex Code Animations**: Migrate from static code highlights to dynamic AST-based typing animations (e.g., using Remotion or Manim).

### Phase C: Curriculum Intelligence
- **Feedback Loops**: Allow the LLM to review the output of `test_summary.json` (QA scores) and self-correct subsequent lessons in the curriculum if they are too short or too dense.
- **Multi-Modal Generation**: Use Gemini 2.5 Flash's native multi-modal capabilities to generate diagrams directly as SVG instead of relying on Mermaid.js string generation.
