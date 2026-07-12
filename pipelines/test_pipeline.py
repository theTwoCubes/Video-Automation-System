"""
Test Pipeline - D.4 from FuturePLAN.md (partial replay via --from-step)

Runs the full rendering/audio/video pipeline using pre-captured fixture data.
No LLM calls, no API cost - ideal for iterating on templates, transitions, timing.

Usage:
    python pipelines/test_pipeline.py
    python pipelines/test_pipeline.py --force-restart
    python pipelines/test_pipeline.py --from-step video     # skip slides + audio
    python pipelines/test_pipeline.py --from-step audio     # skip slides only
    python pipelines/test_pipeline.py --list                # list available fixtures
"""
import json
import uuid
import argparse
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import shutil
from pathlib import Path
from datetime import datetime, timezone

from contracts.schemas import PipelineState
from config.settings import settings

STEPS = ["slides", "audio", "video", "thumbnail"]


def _load_fixture(fixture_path: str) -> dict:
    return json.loads(Path(fixture_path).read_text(encoding="utf-8"))


def run_test_pipeline(
    fixture_path: str = "tests/fixtures/cpp_variables_lesson.json",
    force_restart: bool = False,
    output_label: str = "test",
    from_step: str = "slides",
) -> PipelineState:
    """
    Run the rendering pipeline with fixture data.

    from_step: One of 'slides', 'audio', 'video', 'thumbnail'.
      - 'slides'   - run everything (default)
      - 'audio'    - skip slide rendering, load existing PNGs
      - 'video'    - skip slides + audio, load existing MP3s
      - 'thumbnail'- skip slides + audio + video composition
    """
    from agents.voice_agent import VoiceAgent
    from agents.video_agent import VideoAgent
    from agents.thumbnail_agent import ThumbnailAgent

    fixture = _load_fixture(fixture_path)

    lesson_id = fixture.get("lesson_id", f"test_{uuid.uuid4().hex[:8]}")
    output_dir = str(
        Path(settings.OUTPUT_DIR) / fixture.get("course_id", "test_course") / f"test_{lesson_id[:12]}"
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    if force_restart:
        cp_dir = Path(output_dir) / "checkpoints"
        if cp_dir.exists():
            shutil.rmtree(cp_dir)
        print("[TestPipeline] Cleared checkpoints.")

    # add transition hints from slide_contents (from validator/SlideAgent)
    fixture_slides = fixture.get("slide_contents", [])
    from agents.slide_agent import LAYOUT_TRANSITIONS
    for slide in fixture_slides:
        if "transition_hint" not in slide:
            layout = slide.get("layout", "content")
            slide["transition_hint"] = LAYOUT_TRANSITIONS.get(layout, "fade")

    state: PipelineState = {
        "source_id": fixture.get("source_id", "test_fixture"),
        "proc_source_id": fixture.get("proc_source_id", "test_fixture"),
        "primary_sections": fixture.get("primary_sections", []),
        "reference_sections": fixture.get("reference_sections", []),
        "section_text": fixture.get("section_text", ""),
        "course_id": fixture.get("course_id", "test_course"),
        "course_title": fixture.get("course_title", "Test Course"),
        "lesson_id": lesson_id,
        "lesson_title": fixture["lesson_title"],
        "lesson_position": fixture.get("lesson_position", 1),
        "topic_tags": fixture.get("topic_tags", []),
        "prerequisites": fixture.get("prerequisites", []),
        "target_audience": fixture.get("target_audience", "beginners"),
        "estimated_duration_minutes": fixture.get("estimated_duration_minutes", 10),
        "difficulty": fixture.get("difficulty", "beginner"),
        "past_lessons_history": None,
        "next_lesson_title": fixture.get("next_lesson_title", ""),
        "profile": fixture.get("profile", None),
        "lesson_plan": fixture.get("lesson_plan"),
        "script": fixture.get("script"),
        "code_examples": fixture.get("code_examples", []),
        "diagrams": fixture.get("diagrams", []),
        "diagram_image_paths": fixture.get("diagram_image_paths", {}),
        "slide_contents": None,
        "slide_image_paths": None,
        "slide_id_to_path": None,
        "audio_paths": None,
        "video_path": None,
        "thumbnail_path": None,
        "subtitle_srt": None,
        "quiz_questions": fixture.get("quiz_questions", []),
        "qa_report": fixture.get("qa_report", {"score": 90, "passed": True}),
        "seo_metadata": fixture.get("seo_metadata", {}),
        "output_dir": output_dir,
        "error": None,
        "retry_count": 0,
    }

    from_step_idx = STEPS.index(from_step) if from_step in STEPS else 0

    print(f"\n[TestPipeline] Lesson: {state['lesson_title']}")
    print(f"[TestPipeline] Output: {output_dir}")
    print(f"[TestPipeline] Fixture: {fixture_path}")
    print(f"[TestPipeline] Slides in fixture: {len(fixture_slides)}")
    print(f"[TestPipeline] Starting from step: {from_step}")
    print()

    #  Step 1: Render slides 
    slide_dir = Path(output_dir) / "slides"
    if from_step_idx == 0:
        print("[Step 1/4] Rendering slides (Playwright)...")
        from services.slide_renderer.renderer import SlideRenderer
        renderer = SlideRenderer()
        slide_paths = renderer.render_slides(fixture_slides, str(slide_dir))
        slide_id_to_path = {s.get("id", ""): p for s, p in zip(fixture_slides, slide_paths)}
        state["slide_contents"] = fixture_slides
        state["slide_image_paths"] = slide_paths
        state["slide_id_to_path"] = slide_id_to_path
        print(f"  Rendered {len(slide_paths)} slides\n")
    else:
        print("[Step 1/4] Slides: loading existing PNGs...")
        existing = sorted(slide_dir.glob("*.png")) if slide_dir.exists() else []
        if not existing:
            print("  No existing slides found - running slide render anyway.")
            from services.slide_renderer.renderer import SlideRenderer
            renderer = SlideRenderer()
            slide_paths = renderer.render_slides(fixture_slides, str(slide_dir))
        else:
            slide_paths = [str(p) for p in existing]
        slide_id_to_path = {s.get("id", ""): slide_paths[i] for i, s in enumerate(fixture_slides) if i < len(slide_paths)}
        state["slide_contents"] = fixture_slides
        state["slide_image_paths"] = slide_paths
        state["slide_id_to_path"] = slide_id_to_path
        print(f"  Loaded {len(slide_paths)} slides\n")

    #  Step 2: Synthesize audio 
    audio_dir = Path(output_dir) / "audio"
    if from_step_idx <= 1:
        print("[Step 2/4] Synthesizing audio (edge-tts)...")
        state = VoiceAgent().run(state)
        if state.get("error"):
            print(f"  Voice error: {state['error']}")
            return state
        print(f"  {len(state.get('audio_paths', []))} audio segments\n")
    else:
        print("[Step 2/4] Audio: loading existing MP3s...")
        existing_audio = sorted(audio_dir.glob("seg_*.mp3")) if audio_dir.exists() else []
        if not existing_audio:
            print("  No existing audio - running TTS anyway.")
            state = VoiceAgent().run(state)
        else:
            state["audio_paths"] = [str(p) for p in existing_audio]
        print(f"  Loaded {len(state.get('audio_paths', []))} audio segments\n")

    #  Step 3: Compose video 
    if from_step_idx <= 2:
        print("[Step 3/4] Composing video (FFmpeg)...")
        state = VideoAgent().run(state)
        if state.get("error"):
            print(f"  Video error: {state['error']}")
            return state
        print(f"  Video: {state.get('video_path')}\n")
    else:
        print("[Step 3/4] Video: skipping composition.\n")
        existing_vids = list(Path(output_dir).glob("*_final.mp4"))
        if existing_vids:
            state["video_path"] = str(existing_vids[0])

    #  Step 4: Generate thumbnail 
    print("[Step 4/4] Generating thumbnail...")
    try:
        state = ThumbnailAgent().run(state)
    except Exception as e:
        print(f"  Thumbnail skipped: {e}")

    # validate video quality
    if state.get("video_path"):
        try:
            from services.video_composer.validator import validate_video
            from services.video_composer.composer import _get_ffmpeg
            vq = validate_video(state["video_path"], ffmpeg_exe=_get_ffmpeg())
            state["video_quality"] = vq
            if not vq["passed"]:
                print(f"  Video quality issues: {vq['issues']}")
            else:
                print(f"  Video quality OK: {vq['metrics']['duration_s']:.1f}s")
        except Exception:
            pass

    summary = {
        "fixture": fixture_path,
        "from_step": from_step,
        "lesson_title": state["lesson_title"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "video_path": state.get("video_path", ""),
        "thumbnail_path": state.get("thumbnail_path", ""),
        "slides": len(state.get("slide_image_paths") or []),
        "audio_segments": len(state.get("audio_paths") or []),
        "has_subtitle": bool(state.get("subtitle_srt")),
        "video_quality": state.get("video_quality", {}),
        "output_dir": output_dir,
    }
    summary_path = Path(output_dir) / "test_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n[TestPipeline] Done!")
    print(f"  Video:     {state.get('video_path', 'N/A')}")
    print(f"  Thumbnail: {state.get('thumbnail_path', 'N/A')}")
    print(f"  Summary:   {summary_path}")

    return state


def list_fixtures() -> list[dict]:
    """Return all available fixture files."""
    fixtures_dir = Path("tests/fixtures")
    results = []
    for f in sorted(fixtures_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "path": str(f),
                "name": f.stem,
                "lesson_title": data.get("lesson_title", "Unknown"),
                "slides": len(data.get("slide_contents", [])),
                "script_segments": len(data.get("script", {}).get("segments", [])),
            })
        except Exception:
            pass
    return results


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Run test pipeline with fixture data")
    parser.add_argument("--fixture", default="tests/fixtures/cpp_variables_lesson.json",
                        help="Path to fixture JSON file")
    parser.add_argument("--force-restart", action="store_true",
                        help="Clear checkpoints and re-render everything")
    parser.add_argument("--from-step", default="slides", choices=STEPS,
                        help="Start pipeline from this step (D.4 partial replay)")
    parser.add_argument("--list", action="store_true",
                        help="List available fixtures")
    args = parser.parse_args()

    if args.list:
        fixtures = list_fixtures()
        if not fixtures:
            print("No fixtures found in tests/fixtures/")
        for fx in fixtures:
            print(f"  {fx['name']}: {fx['lesson_title']} ({fx['slides']} slides)")
    else:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        run_test_pipeline(
            fixture_path=args.fixture,
            force_restart=args.force_restart,
            from_step=args.from_step,
        )
