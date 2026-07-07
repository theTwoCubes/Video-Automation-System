"""
Test Pipeline — runs the full rendering/audio/video pipeline
using pre-captured fixture data instead of calling any LLM or AI APIs.

This is the iteration harness: make a code change, run this, verify the
output video in seconds — no API cost, no rate limits.

Usage:
  python pipelines/test_pipeline.py
  python pipelines/test_pipeline.py --fixture tests/fixtures/cpp_variables_lesson.json
  python pipelines/test_pipeline.py --fixture tests/fixtures/cpp_variables_lesson.json --force-restart
"""
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime

from contracts.schemas import PipelineState
from config.settings import settings


def _load_fixture(fixture_path: str) -> dict:
    return json.loads(Path(fixture_path).read_text(encoding="utf-8"))


def run_test_pipeline(
    fixture_path: str = "tests/fixtures/cpp_variables_lesson.json",
    force_restart: bool = False,
    output_label: str = "test",
) -> PipelineState:
    """
    Run the full pipeline skipping all LLM agents (SlideAgent uses real Playwright,
    VoiceAgent uses real edge-tts, VideoAgent uses real FFmpeg).
    Returns the final PipelineState.
    """
    from agents.slide_agent import SlideAgent
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

    # build initial state from fixture (all LLM outputs pre-filled)
    state: PipelineState = {
        "source_id": fixture.get("source_id", "test_fixture"),
        "course_id": fixture.get("course_id", "test_course"),
        "course_title": fixture.get("course_title", "Test Course"),
        "lesson_id": lesson_id,
        "lesson_title": fixture["lesson_title"],
        "lesson_position": fixture.get("lesson_position", 1),
        "topic_tags": fixture.get("topic_tags", []),
        "prerequisites": fixture.get("prerequisites", []),
        "target_audience": fixture.get("target_audience", "beginners"),
        "estimated_duration_minutes": fixture.get("estimated_duration_minutes", 10),
        # pre-fill ALL LLM agent outputs from fixture
        "lesson_plan": fixture.get("lesson_plan"),
        "script": fixture.get("script"),
        "code_examples": fixture.get("code_examples", []),
        "diagrams": fixture.get("diagrams", []),
        "diagram_image_paths": fixture.get("diagram_image_paths", {}),
        "slide_contents": None,   # SlideAgent renders from fixture slide_contents
        "slide_image_paths": None,
        "slide_id_to_path": None,
        "audio_paths": None,
        "video_path": None,
        "thumbnail_path": None,
        "subtitle_srt": None,
        "qa_report": fixture.get("qa_report", {"score": 90, "passed": True}),
        "seo_metadata": fixture.get("seo_metadata", {}),
        "output_dir": output_dir,
        "error": None,
        "retry_count": 0,
    }

    print(f"\n[TestPipeline] Lesson: {state['lesson_title']}")
    print(f"[TestPipeline] Output: {output_dir}")
    print(f"[TestPipeline] Fixture: {fixture_path}")
    print(f"[TestPipeline] Slides in fixture: {len(fixture.get('slide_contents', []))}")
    print()

    # ── Step 1: Render slides (Playwright — no LLM) ─────────────────────────
    print("[Step 1/4] Rendering slides...")
    from services.slide_renderer.renderer import SlideRenderer
    renderer = SlideRenderer()
    slide_dir = str(Path(output_dir) / "slides")
    fixture_slides = fixture.get("slide_contents", [])
    slide_paths = renderer.render_slides(fixture_slides, slide_dir)
    slide_id_to_path = {s.get("id", ""): p for s, p in zip(fixture_slides, slide_paths)}
    state["slide_contents"] = fixture_slides
    state["slide_image_paths"] = slide_paths
    state["slide_id_to_path"] = slide_id_to_path
    print(f"  Rendered {len(slide_paths)} slides\n")

    # ── Step 2: Synthesize audio (edge-tts — no LLM) ────────────────────────
    print("[Step 2/4] Synthesizing audio (edge-tts)...")
    state = VoiceAgent().run(state)
    if state.get("error"):
        print(f"  Voice error: {state['error']}")
        return state
    print(f"  {len(state.get('audio_paths', []))} audio segments\n")

    # ── Step 3: Compose video (FFmpeg) ───────────────────────────────────────
    print("[Step 3/4] Composing video...")
    state = VideoAgent().run(state)
    if state.get("error"):
        print(f"  Video error: {state['error']}")
        return state
    print(f"  Video: {state.get('video_path')}\n")

    # ── Step 4: Generate thumbnail ────────────────────────────────────────────
    print("[Step 4/4] Generating thumbnail...")
    try:
        state = ThumbnailAgent().run(state)
    except Exception as e:
        print(f"  Thumbnail skipped: {e}")

    # save summary
    summary = {
        "fixture": fixture_path,
        "lesson_title": state["lesson_title"],
        "completed_at": datetime.utcnow().isoformat(),
        "video_path": state.get("video_path", ""),
        "thumbnail_path": state.get("thumbnail_path", ""),
        "slides": len(slide_paths),
        "audio_segments": len(state.get("audio_paths", [])),
        "has_subtitle": bool(state.get("subtitle_srt")),
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
    parser = argparse.ArgumentParser(description="Run test pipeline with fixture data")
    parser.add_argument("--fixture", default="tests/fixtures/cpp_variables_lesson.json",
                        help="Path to fixture JSON file")
    parser.add_argument("--force-restart", action="store_true",
                        help="Clear checkpoints and re-render everything")
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
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        run_test_pipeline(fixture_path=args.fixture, force_restart=args.force_restart)
