"""
VideoAgent - composes the final lesson video from slides + audio.

Features:
- Single-timeline composition with per-segment baked fades (sync-safe)
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
from services.media.ffmpeg import (
    get_audio_duration,
    seconds_to_srt_time as _seconds_to_srt_time,
)

# A single slide_id should never hold the screen for longer than this - past it,
# audio keeps playing over a frozen frame with nothing changing on screen. Slide
# groups longer than this get split into multiple chunks of the same image, each
# getting its own Ken Burns zoom / transition instead of one dead-static hold.
MAX_SLIDE_SECONDS = 45.0


def _wrap_srt_text(text: str) -> str:
    """Trim narration to a subtitle: drop [PAUSE] markers and wrap to <=3 lines
    of ~80 chars so a long sentence doesn't overflow the caption area."""
    text = (text or "").strip().replace("[PAUSE]", "")
    if len(text) <= 80:
        return text
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
    return "\n".join(lines[:3])


def _generate_srt(aligned_pairs: list, text_by_audio: dict, segments_dir,
                  intro_offset: float, lead_s: float, gap_s: float) -> str:
    """Build .srt timings that mirror the composed timeline exactly, so captions
    line up with the voice:

      - `intro_offset` seconds for a prepended intro card (no captions there);
      - a `lead_s` lead-in silence at the START of every slide's segment;
      - a `gap_s` silence BETWEEN clips within a slide;
      - each segment advances by its ACTUAL rendered duration (read from the
        seg_NNNN.mp4 the composer produced), which also absorbs the code-reveal
        trailing pad and any fade, so later captions don't drift.

    Walking `aligned_pairs` (the same structure the composer builds segments from)
    guarantees the caption order and grouping match what's on screen."""
    srt_lines = []
    cursor = float(intro_offset)
    idx = 0
    for i, (_img, clips) in enumerate(aligned_pairs):
        seg_file = Path(segments_dir) / f"seg_{i:04d}.mp4"
        seg_dur = get_audio_duration(str(seg_file), default=0.0) if seg_file.exists() else 0.0
        seg_end = cursor + seg_dur if seg_dur > 0 else None

        t = cursor + lead_s
        for j, ap in enumerate(clips):
            if j > 0:
                t += gap_s
            dur = get_audio_duration(ap, default=0.0) if Path(ap).exists() else 0.0
            text = _wrap_srt_text(text_by_audio.get(ap, ""))
            if text and dur > 0:
                end_s = t + dur
                if seg_end is not None:
                    end_s = min(end_s, seg_end)
                idx += 1
                srt_lines.append(
                    f"{idx}\n{_seconds_to_srt_time(t)} --> {_seconds_to_srt_time(end_s)}\n{text}\n"
                )
            t += dur

        # advance by the true segment length; fall back to the summed audio
        # timeline if the segment file couldn't be measured.
        cursor += seg_dur if seg_dur > 0 else (t - cursor)

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
        Build (slide_image_path, [audio_paths]) pairs.
        Also returns, in lockstep, the slide_id and diagram_ref (if any) each
        pair was built from - computed directly here rather than re-derived
        later by reverse-searching slide_id_to_path, which breaks silently
        whenever two slide_ids share an image path (e.g. both falling back to
        the same missing-image substitute).

        A slide_id whose combined audio exceeds MAX_SLIDE_SECONDS is split into
        multiple consecutive pairs (same image, chunked audio) so no single
        static frame holds the screen for minutes on end.

        Returns (aligned_pairs, pair_slide_ids, pair_diagram_refs).
        """
        from services.video_composer.composer import _get_ffmpeg, _get_audio_duration

        narration_segs = [
            s for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
        ]
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
        pair_slide_ids = []
        pair_diagram_refs = []
        for slide_id, audio_diag_pairs in slide_audio_map.items():
            img = slide_id_to_path.get(slide_id, fb)
            if not Path(img).exists():
                print(f"  [WARNING] Rendered image missing for slide '{slide_id}' - "
                      f"substituting the fallback slide. Audio/visual will be mismatched "
                      f"for this segment until the slide render is fixed.")
                img = fb

            # Split first by diagram_ref, so when a single slide's narration
            # references TWO different diagrams (one segment each), each diagram
            # gets its own on-screen pair instead of only the first being shown.
            for ref_group in self._split_by_diagram_ref(audio_diag_pairs):
                for chunk in self._split_by_duration(ref_group, ffmpeg_exe, MAX_SLIDE_SECONDS):
                    chunk_audios = [a for a, _ in chunk]
                    chunk_diagram_ref = next((d for _, d in chunk if d), "")
                    aligned_pairs.append((img, chunk_audios))
                    pair_slide_ids.append(slide_id)
                    pair_diagram_refs.append(chunk_diagram_ref)

        return aligned_pairs, pair_slide_ids, pair_diagram_refs

    @staticmethod
    def _split_by_diagram_ref(audio_diag_pairs: list) -> list:
        """Group a slide's ordered (audio_path, diagram_ref) items into runs of a
        constant diagram_ref. Consecutive segments sharing a ref (or sharing no
        ref) stay together; a change in ref starts a new group. This keeps each
        diagram on screen only during the narration that describes it."""
        groups, current, current_ref = [], [], None
        for item in audio_diag_pairs:
            ref = item[1] or ""
            if current and ref != current_ref:
                groups.append(current)
                current = []
            current.append(item)
            current_ref = ref
        if current:
            groups.append(current)
        return groups

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
        aligned_pairs, pair_slide_ids, pair_diagram_refs = self._build_pairs(
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

        # subtitle generation - timings mirror the composed timeline (intro
        # offset + per-slide lead-in + inter-clip gaps + true segment durations)
        # so captions line up with the voice.
        try:
            from services.video_composer.composer import (
                _INTRO_SECONDS, _SILENCE_GAP_MS, _lead_in_ms,
            )
            p_music = state.get("profile", {}).get("music", {})
            intro_added = bool(p_music.get("use_intro", False) and p_music.get("intro_sting"))
            text_by_audio = {
                audio_paths[i]: narration_segs[i].get("text", "")
                for i in range(min(len(audio_paths), len(narration_segs)))
            }
            srt_content = _generate_srt(
                aligned_pairs, text_by_audio,
                Path(output_dir) / "segments",
                intro_offset=_INTRO_SECONDS if intro_added else 0.0,
                lead_s=_lead_in_ms() / 1000.0,
                gap_s=_SILENCE_GAP_MS / 1000.0,
            )
            if srt_content:
                srt_path = Path(output_dir) / "subtitles.srt"
                srt_path.write_text(srt_content, encoding="utf-8")
                state["subtitle_srt"] = srt_content
                print(f"  Subtitles: {srt_path}")
        except Exception as e:
            print(f"  Subtitle generation skipped: {e}")

        return state

    def _audio_dur(self, path: str) -> float:
        try:
            return get_audio_duration(path, default=0.0)
        except Exception:
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
                "-i", _fwd(Path(diagram_video)),
                "-i", _fwd(merged),
                "-t", f"{total_dur:.3f}",
                "-vf", f"scale=1920:1080:flags=lanczos,tpad=stop_mode=clone:stop_duration={total_dur:.3f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
                # Canonical audio format so this prebuilt segment stream-copies
                # cleanly alongside the static segments in the final concat.
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
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
