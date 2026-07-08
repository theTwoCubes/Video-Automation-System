"""
VideoAgent — composes the final lesson video from slides + audio.

New features:
- B.2: Per-layout slide transitions from slide_contents.transition_hint
- E.2: Video quality validation via ffprobe after composition
- Code reveal animation integration
- Subtitle .srt generation
"""
from collections import OrderedDict
from pathlib import Path
from agents.base_agent import BaseAgent
from services.video_composer.composer import compose_video_aligned
from services.slide_renderer.renderer import SlideRenderer


def _seconds_to_srt_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{int(sec):02d},{ms:03d}"


def _generate_srt(narration_segs: list, audio_paths: list, ffmpeg_exe: str) -> str:
    from services.video_composer.composer import _get_audio_duration
    srt_lines = []
    cursor = 0.0

    for idx, (seg, audio_path) in enumerate(zip(narration_segs, audio_paths)):
        if not Path(audio_path).exists():
            continue
        try:
            dur = _get_audio_duration(audio_path, ffmpeg_exe)
        except Exception as e:
            raise RuntimeError(f"Corrupt or unreadable audio file: {audio_path}. ffprobe failed: {e}")

        start = _seconds_to_srt_time(cursor)
        end   = _seconds_to_srt_time(cursor + dur)
        text  = seg.get("text", "").strip().replace("[PAUSE]", "")

        # wrap at ~80 chars
        if len(text) > 80:
            words = text.split()
            lines, cur_line, cur_len = [], [], 0
            for w in words:
                if cur_len + len(w) + 1 > 80:
                    lines.append(" ".join(cur_line))
                    cur_line, cur_len = [w], len(w)
                else:
                    cur_line.append(w)
                    cur_len += len(w) + 1
            if cur_line:
                lines.append(" ".join(cur_line))
            text = "\n".join(lines[:3])

        srt_lines.append(f"{idx + 1}\n{start} --> {end}\n{text}\n")
        cursor += dur

    return "\n".join(srt_lines)


class VideoAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self._renderer = None

    def _get_renderer(self):
        if self._renderer is None:
            self._renderer = SlideRenderer()
        return self._renderer

    def run(self, state: dict) -> dict:
        print("[VideoAgent] Composing final video...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        audio_paths = state.get("audio_paths", [])
        slide_id_to_path = state.get("slide_id_to_path") or {}
        slide_contents = state.get("slide_contents", []) or []
        slide_paths = state.get("slide_image_paths", []) or []
        output_dir = state["output_dir"]
        lesson_id = state["lesson_id"]

        # rebuild slide mapping
        if slide_contents and slide_paths:
            slide_id_to_path = {}
            for slide_data, img_path in zip(slide_contents, slide_paths):
                sid = slide_data.get("id", "")
                if sid:
                    slide_id_to_path[sid] = img_path
            print(f"  Slide mapping: {len(slide_id_to_path)} entries")

        if not slide_paths:
            state["error"] = "No slides to render."
            return state
        if not audio_paths:
            state["error"] = "No audio segments."
            return state

        # build quick lookups
        slide_content_map = {s.get("id", ""): s for s in slide_contents}

        narration_segs = [
            s for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
        ]

        # group audio by slide_id
        slide_audio_map = OrderedDict()
        for i, seg in enumerate(narration_segs):
            if i >= len(audio_paths):
                break
            sid = seg.get("slide_id", "slide_001")
            slide_audio_map.setdefault(sid, []).append(audio_paths[i])

        if not slide_audio_map:
            state["error"] = "Could not map audio to slides."
            return state

        fallback_img = slide_paths[-1]
        aligned_pairs = []
        pair_slide_ids = []
        transition_hints = []

        for slide_id, audios in slide_audio_map.items():
            img = slide_id_to_path.get(slide_id, fallback_img)
            if not Path(img).exists():
                img = fallback_img
            aligned_pairs.append((img, audios))
            pair_slide_ids.append(slide_id)
            # pull transition_hint from slide_contents
            slide_data = slide_content_map.get(slide_id, {})
            transition_hints.append(slide_data.get("transition_hint", "fade"))

        print(f"  {len(aligned_pairs)} slide groups, {len(audio_paths)} total audio segments")

        # build code reveal animations
        prebuilt_segments = {}
        try:
            prebuilt_segments = self._build_code_reveals(
                aligned_pairs, pair_slide_ids, slide_content_map, output_dir
            )
        except Exception as e:
            print(f"  Code reveal skipped: {e}")

        output_path = str(Path(output_dir) / f"{lesson_id}_final.mp4")

        # compute expected duration from audio files for quality validation
        expected_dur = sum(
            self._audio_dur(a) for auds in [p[1] for p in aligned_pairs] for a in auds
        )

        try:
            compose_video_aligned(
                aligned_pairs,
                output_path,
                prebuilt_segments=prebuilt_segments,
                transition_hints=transition_hints,
            )
            state["video_path"] = output_path
            size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            print(f"  Video: {output_path} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  Video composition failed: {e}")
            state["error"] = str(e)
            return state

        # E.2: video quality validation
        try:
            from services.video_composer.validator import validate_video
            from services.video_composer.composer import _get_ffmpeg
            vq = validate_video(output_path, expected_dur, _get_ffmpeg())
            state["video_quality"] = vq
            if not vq["passed"]:
                print(f"  Video quality issues: {vq['issues']}")
            else:
                print(f"  Video quality OK: {vq['metrics']['duration_s']:.1f}s, {vq['metrics']['resolution']}")
        except Exception as e:
            print(f"  Video quality check skipped: {e}")

        # subtitle generation
        try:
            from services.video_composer.composer import _get_ffmpeg
            ffmpeg_exe = _get_ffmpeg()
            srt_content = _generate_srt(narration_segs, audio_paths, ffmpeg_exe)
            if srt_content:
                srt_path = Path(output_dir) / "subtitles.srt"
                srt_path.write_text(srt_content, encoding="utf-8")
                state["subtitle_srt"] = srt_content
                print(f"  Subtitles: {srt_path}")
        except Exception as e:
            print(f"  Subtitle generation skipped: {e}")

        return state

    def _audio_dur(self, path: str) -> float:
        import re, subprocess, shutil
        try:
            f = shutil.which("ffmpeg") or "ffmpeg"
            r = subprocess.run([f, "-i", path], capture_output=True, text=True)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
            if m:
                return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except Exception:
            pass
        return 0.0

    def _build_code_reveals(
        self,
        aligned_pairs: list,
        pair_slide_ids: list,
        slide_content_map: dict,
        output_dir: str,
    ) -> dict:
        from services.video_composer.composer import _get_ffmpeg, _concat_audio
        from services.code_animator.animator import create_code_reveal_segment

        ffmpeg_exe = _get_ffmpeg()
        segments_dir = Path(output_dir) / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        renderer = self._get_renderer()
        total_slides = len(aligned_pairs)
        prebuilt = {}

        for i, (slide_img, audio_files) in enumerate(aligned_pairs):
            sid = pair_slide_ids[i]
            slide_data = slide_content_map.get(sid, {})

            if slide_data.get("layout") != "code":
                continue
            code = slide_data.get("code_content", "").strip()
            if not code or code.count("\n") < 2:
                continue

            valid_audios = [a for a in audio_files if Path(a).exists()]
            if not valid_audios:
                continue

            merged = segments_dir / f"merged_{i:04d}.mp3"
            _concat_audio(valid_audios, merged, ffmpeg_exe)

            reveal_out = str(segments_dir / f"reveal_{i:04d}.mp4")
            result = create_code_reveal_segment(
                slide_data=slide_data,
                merged_audio=str(merged),
                output_path=reveal_out,
                renderer=renderer,
                ffmpeg_exe=ffmpeg_exe,
                slide_index=i,
                total_slides=total_slides,
            )
            if result:
                prebuilt[i] = result
                print(f"  Code reveal ready for slide {i + 1}")

        return prebuilt
