"""
VideoAgent - composes the final lesson video from slides + audio.

Features:
- Per-layout slide transitions from slide_contents.transition_hint
- Video quality validation via ffprobe after composition
- Code reveal animation integration
- Subtitle .srt generation
"""
import subprocess
from collections import OrderedDict
from pathlib import Path
from agents.base_agent import BaseAgent
from services.video_composer.composer import compose_video_aligned
from services.slide_renderer.renderer import SlideRenderer

# A single slide_id should never hold the screen for longer than this - past it,
# audio keeps playing over a frozen frame with nothing changing on screen. Slide
# groups longer than this get split into multiple chunks of the same image, each
# getting its own Ken Burns zoom / transition instead of one dead-static hold.
MAX_SLIDE_SECONDS = 45.0


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

    def _build_pairs(
        self,
        segments: list,
        slide_id_to_path: dict,
        slide_contents: list,
        audio_paths: list,
        fallback_img: str = None,
    ) -> tuple:
        """
        Build (slide_image_path, [audio_paths]) pairs and transition hints.
        Also returns, in lockstep, the slide_id and diagram_ref (if any) each
        pair was built from - computed directly here rather than re-derived
        later by reverse-searching slide_id_to_path, which breaks silently
        whenever two slide_ids share an image path (e.g. both falling back to
        the same missing-image substitute).

        A slide_id whose combined audio exceeds MAX_SLIDE_SECONDS is split into
        multiple consecutive pairs (same image, chunked audio) so no single
        static frame holds the screen for minutes on end.

        Returns (aligned_pairs, transition_hints, pair_slide_ids, pair_diagram_refs).
        """
        from services.video_composer.composer import _get_ffmpeg, _get_audio_duration

        narration_segs = [
            s for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
        ]
        slide_content_map = {s.get("id", ""): s for s in slide_contents}
        slide_paths_list = list(slide_id_to_path.values())
        fb = fallback_img or (slide_paths_list[-1] if slide_paths_list else "")
        ffmpeg_exe = _get_ffmpeg()

        # group (audio_path, diagram_ref) tuples by slide_id, in script order
        slide_audio_map: dict = OrderedDict()
        for i, seg in enumerate(narration_segs):
            if i >= len(audio_paths):
                break
            sid = seg.get("slide_id", "slide_001")
            slide_audio_map.setdefault(sid, []).append((audio_paths[i], seg.get("diagram_ref", "")))

        aligned_pairs = []
        transition_hints = []
        pair_slide_ids = []
        pair_diagram_refs = []
        for slide_id, audio_diag_pairs in slide_audio_map.items():
            img = slide_id_to_path.get(slide_id, fb)
            if not Path(img).exists():
                print(f"  [WARNING] Rendered image missing for slide '{slide_id}' - "
                      f"substituting the fallback slide. Audio/visual will be mismatched "
                      f"for this segment until the slide render is fixed.")
                img = fb
            sd = slide_content_map.get(slide_id, {})
            hint = sd.get("transition_hint", "fade")

            for chunk in self._split_by_duration(audio_diag_pairs, ffmpeg_exe, MAX_SLIDE_SECONDS):
                chunk_audios = [a for a, _ in chunk]
                chunk_diagram_ref = next((d for _, d in chunk if d), "")
                aligned_pairs.append((img, chunk_audios))
                transition_hints.append(hint)
                pair_slide_ids.append(slide_id)
                pair_diagram_refs.append(chunk_diagram_ref)

        return aligned_pairs, transition_hints, pair_slide_ids, pair_diagram_refs

    def _split_by_duration(self, audio_diag_pairs: list, ffmpeg_exe: str, max_seconds: float) -> list:
        """Split a slide_id's ordered (audio_path, diagram_ref) list into chunks
        whose combined audio duration stays under max_seconds. Never splits a
        single segment, and never drops audio even if duration lookups fail."""
        from services.video_composer.composer import _get_audio_duration

        if not audio_diag_pairs:
            return []

        chunks, current, current_dur = [], [], 0.0
        for item in audio_diag_pairs:
            audio_path = item[0]
            try:
                dur = _get_audio_duration(audio_path, ffmpeg_exe) if Path(audio_path).exists() else 0.0
            except Exception:
                dur = 0.0
            if current and current_dur + dur > max_seconds:
                chunks.append(current)
                current, current_dur = [], 0.0
            current.append(item)
            current_dur += dur
        if current:
            chunks.append(current)
        return chunks

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

        slide_content_map = {s.get("id", ""): s for s in slide_contents}

        narration_segs = [
            s for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
        ]

        fallback_img = slide_paths[-1]
        aligned_pairs, transition_hints, pair_slide_ids, pair_diagram_refs = self._build_pairs(
            segments, slide_id_to_path, slide_contents, audio_paths, fallback_img
        )

        print(f"  {len(aligned_pairs)} slide groups, {len(audio_paths)} total audio segments")

        if not aligned_pairs:
            state["error"] = "Could not map audio to slides."
            return state

        # build code reveal animations
        prebuilt_segments = {}
        try:
            prebuilt_segments = self._build_code_reveals(
                aligned_pairs, pair_slide_ids, slide_content_map, output_dir
            )
        except Exception as e:
            print(f"  Code reveal skipped: {e}")

        # insert generated diagram videos wherever a segment referenced one
        try:
            diagram_segments = self._build_diagram_segments(
                aligned_pairs, pair_diagram_refs, state.get("diagram_image_paths") or {},
                output_dir, prebuilt_segments,
            )
            prebuilt_segments.update(diagram_segments)
        except Exception as e:
            print(f"  Diagram insertion skipped: {e}")

        output_path = str(Path(output_dir) / f"{lesson_id}_final.mp4")

        # expected duration for quality validation
        expected_dur = sum(
            self._audio_dur(a) for auds in [p[1] for p in aligned_pairs] for a in auds
        )

        try:
            profile = state.get("profile", {})
            p_music = profile.get("music", {})
            p_slides = profile.get("slides", {})
            p_rendering = profile.get("rendering", {})
            
            use_intro = p_music.get("use_intro", False)
            use_outro = p_music.get("use_outro", False)
            
            compose_video_aligned(
                aligned_pairs,
                output_path,
                fps=p_rendering.get("fps", 30),
                prebuilt_segments=prebuilt_segments,
                transition_hints=transition_hints,
                animation_preset=p_slides.get("animation_preset", "smooth"),
                ken_burns=p_slides.get("ken_burns", False),
                music_track=p_music.get("bg_track", ""),
                bg_volume=p_music.get("bg_volume", 0.5),
                ducking_ratio=p_music.get("ducking_ratio", 8.0),
                intro_sting=p_music.get("intro_sting", "") if use_intro else "",
                outro_music=p_music.get("outro_music", "") if use_outro else "",
                lesson_title=state.get("lesson_title", "Untitled Lesson"),
                renderer=self._get_renderer(),
            )
            state["video_path"] = output_path
            size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            print(f"  Video: {output_path} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  Video composition failed: {e}")
            state["error"] = str(e)
            return state

        # video quality validation
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
            sid = pair_slide_ids[i] if i < len(pair_slide_ids) else ""
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

    def _build_diagram_segments(
        self,
        aligned_pairs: list,
        pair_diagram_refs: list,
        diagram_paths: dict,
        output_dir: str,
        existing_prebuilt: dict,
    ) -> dict:
        """For any pair whose segment(s) referenced a diagram (via diagram_ref),
        loop the generated diagram video under that pair's narration audio so it
        actually appears in the final video instead of being generated and then
        never used. Skips pairs already claimed by a code-reveal segment."""
        if not diagram_paths:
            return {}

        from services.video_composer.composer import _get_ffmpeg, _concat_audio, _fwd

        ffmpeg_exe = _get_ffmpeg()
        segments_dir = Path(output_dir) / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        prebuilt = {}

        for i, (slide_img, audio_files) in enumerate(aligned_pairs):
            if i in existing_prebuilt:
                continue
            diagram_ref = pair_diagram_refs[i] if i < len(pair_diagram_refs) else ""
            if not diagram_ref:
                continue
            diagram_video = diagram_paths.get(diagram_ref)
            if not diagram_video or not Path(diagram_video).exists():
                continue

            valid_audios = [a for a in audio_files if Path(a).exists()]
            if not valid_audios:
                continue

            merged = segments_dir / f"diag_audio_{i:04d}.mp3"
            total_dur = _concat_audio(valid_audios, merged, ffmpeg_exe)

            out = segments_dir / f"diagram_{i:04d}.mp4"
            cmd = [
                ffmpeg_exe, "-y",
                "-stream_loop", "-1", "-i", _fwd(Path(diagram_video)),
                "-i", _fwd(merged),
                "-t", f"{total_dur:.3f}",
                "-vf", "scale=1920:1080:flags=lanczos",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                _fwd(out),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and out.exists():
                prebuilt[i] = str(out)
                print(f"  Diagram inserted for slide {i + 1}: {diagram_ref} ({total_dur:.1f}s)")
            else:
                print(f"  Diagram mux failed for {diagram_ref}: {result.stderr[-200:]}")

        return prebuilt
