"""
Re-render a lesson from existing checkpoints without any LLM calls.

Usage:
    python scripts/rerender_lesson.py --lesson-id <UUID> [options]

Options:
    --lesson-id     Lesson UUID (matches the output folder name prefix)
    --steps         Comma-separated list of steps to re-run: slides,voice,video,all
    --profile       Profile name from config/profiles/ (default: testing)
    --voice         Override voice name (e.g. en-US-AndrewNeural)
    --music         Override music track path (relative to project root)
    --output-dir    Override output directory (auto-detected if omitted)
"""
import argparse
import json
import sys
from pathlib import Path

# ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.profile_loader import load_profile


def find_output_dir(lesson_id: str) -> Path:
    """Find the output directory for a given lesson ID prefix."""
    output_root = Path("output")
    # search for lesson_id anywhere in directory name
    for course_dir in output_root.iterdir():
        if not course_dir.is_dir():
            continue
        for lesson_dir in course_dir.iterdir():
            if lesson_id in lesson_dir.name:
                return lesson_dir
    raise FileNotFoundError(f"No output directory found for lesson {lesson_id}")


def load_checkpoint(output_dir: Path, step: str) -> dict:
    cp = output_dir / "checkpoints" / f"{step}.json"
    if not cp.exists():
        raise FileNotFoundError(f"Checkpoint not found: {cp}")
    return json.loads(cp.read_text(encoding="utf-8"))


def save_checkpoint(output_dir: Path, step: str, data: dict):
    cp_dir = output_dir / "checkpoints"
    cp_dir.mkdir(exist_ok=True)
    (cp_dir / f"{step}.json").write_text(
        json.dumps(data, default=str, indent=2), encoding="utf-8"
    )


def rerender_slides(output_dir: Path, profile: dict) -> list[str]:
    """Re-render slides from checkpoint using new template.

    Outputs to slides_rerender/ to preserve the original slides/ directory.
    """
    print("\n[Rerender] Re-rendering slides...")
    cp = load_checkpoint(output_dir, "generate_slides")
    slides = cp.get("slide_contents", [])
    print(f"  Loaded {len(slides)} slides from checkpoint")

    from services.slide_renderer.renderer import SlideRenderer
    renderer = SlideRenderer()
    slide_dir = str(output_dir / "slides_rerender")
    paths = renderer.render_slides(slides, slide_dir)
    print(f"  Rendered {len(paths)} slides -> {slide_dir}")

    # persist the rerender paths in a dedicated checkpoint key
    cp["rerender_slide_paths"] = paths
    cp["rerender_slide_id_to_path"] = {
        s.get("id", f"slide_{i:04d}"): p
        for i, (s, p) in enumerate(zip(slides, paths))
    }
    save_checkpoint(output_dir, "generate_slides", cp)
    return paths


def rerender_voice(output_dir: Path, profile: dict, voice_override: str = None) -> list[str]:
    """Re-synthesize audio using a (possibly different) voice."""
    voice_name = voice_override or profile["voice"]["name"]
    rate = profile["voice"].get("rate", "+0%")
    pitch = profile["voice"].get("pitch", "+0Hz")

    print(f"\n[Rerender] Re-synthesizing voice with {voice_name}...")
    cp_script = load_checkpoint(output_dir, "write_script")
    segments = cp_script.get("script", {}).get("segments", [])
    print(f"  {len(segments)} segments to synthesize")

    from providers.tts.edge_tts_provider import EdgeTTSProvider
    tts = EdgeTTSProvider()

    # Write to isolated folder to preserve original audio
    audio_dir = output_dir / "audio_rerender"
    audio_dir.mkdir(exist_ok=True)

    audio_paths = []
    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if not text:
            continue
        out_path = str(audio_dir / f"seg_{i:04d}.mp3")
        try:
            tts.synthesize(text, out_path, voice=voice_name, rate=rate, pitch=pitch)
            audio_paths.append(out_path)
            print(f"  Segment {i + 1}/{len(segments)}: {len(text)} chars")
        except Exception as e:
            print(f"  Segment {i + 1} failed: {e}")

    save_checkpoint(output_dir, "synthesize_voice", {"audio_paths": audio_paths})
    print(f"  Synthesized {len(audio_paths)} audio files")
    return audio_paths


def rerender_video(output_dir: Path, profile: dict, music_override: str = None) -> str:
    """Re-compose the final video from existing slides + audio."""
    print("\n[Rerender] Re-composing video...")

    slides_cp = load_checkpoint(output_dir, "generate_slides")
    audio_cp = load_checkpoint(output_dir, "synthesize_voice")

    slide_id_to_path = slides_cp.get("slide_id_to_path", {})
    slide_contents = slides_cp.get("slide_contents", [])
    audio_paths = audio_cp.get("audio_paths", [])
    script_cp = load_checkpoint(output_dir, "write_script")
    segments = script_cp.get("script", {}).get("segments", [])

    # re-build slide_audio_pairs same way as video_agent
    from agents.video_agent import VideoAgent
    va = VideoAgent()
    pairs, hints = va._build_pairs(segments, slide_id_to_path, slide_contents, audio_paths)

    music = music_override or profile["music"].get("bg_track", "")
    anim = profile["slides"].get("animation_preset", "smooth")

    from services.video_composer.composer import compose_video_aligned
    from services.slide_renderer.renderer import SlideRenderer
    renderer = SlideRenderer()
    
    use_intro = profile["music"].get("use_intro", False)
    use_outro = profile["music"].get("use_outro", False)
    
    lesson_title = "Untitled Lesson"
    plan_cp = output_dir / "checkpoints" / "lesson_planner.json"
    if plan_cp.exists():
        plan = json.loads(plan_cp.read_text(encoding="utf-8"))
        lesson_title = plan.get("lesson_title", plan.get("title", lesson_title))

    output_path = str(output_dir / "lesson_rerendered.mp4")
    result = compose_video_aligned(
        pairs, output_path,
        fps=profile["rendering"].get("fps", 30),
        use_transitions=True,
        transition_hints=hints,
        animation_preset=anim,
        ken_burns=profile["slides"].get("ken_burns", False),
        music_track=music,
        bg_volume=profile["music"].get("bg_volume", 0.5),
        ducking_ratio=profile["music"].get("ducking_ratio", 8.0),
        intro_sting=profile["music"].get("intro_sting", "") if use_intro else "",
        outro_music=profile["music"].get("outro_music", "") if use_outro else "",
        lesson_title=lesson_title,
        renderer=renderer,
    )
    save_checkpoint(output_dir, "compose_video", {"video_path": result})
    print(f"  Video saved: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Re-render a lesson from checkpoints")
    parser.add_argument("--lesson-id", required=True, help="Lesson UUID")
    parser.add_argument("--steps", default="all",
                        help="Comma-separated: slides,voice,video,all")
    parser.add_argument("--profile", default="testing", help="Profile name")
    parser.add_argument("--voice", default=None, help="Override voice name")
    parser.add_argument("--music", default=None, help="Override music track path")
    parser.add_argument("--output-dir", default=None, help="Override output directory")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    steps = [s.strip() for s in args.steps.split(",")]
    do_all = "all" in steps

    try:
        output_dir = Path(args.output_dir) if args.output_dir else find_output_dir(args.lesson_id)
        print(f"[Rerender] Output dir: {output_dir}")
    except FileNotFoundError as e:
        print(f"[Error] {e}")
        sys.exit(1)

    if do_all or "slides" in steps:
        rerender_slides(output_dir, profile)

    if do_all or "voice" in steps:
        rerender_voice(output_dir, profile, voice_override=args.voice)

    if do_all or "video" in steps:
        rerender_video(output_dir, profile, music_override=args.music)

    print("\n[Rerender] Done!")


if __name__ == "__main__":
    main()
