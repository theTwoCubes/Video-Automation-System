import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from services.media.ffmpeg import (
    get_ffmpeg as _get_ffmpeg,
    fwd as _fwd,
    get_audio_duration as _shared_audio_duration,
)


def _get_audio_duration(audio_path: str, ffmpeg_exe: str = None) -> float:
    """Composer defaults to 5.0s when a duration can't be read, so a segment
    still gets a non-zero length rather than being dropped. Delegates to the
    shared probe (services/media/ffmpeg.py); the name is kept because other
    modules import it from here."""
    return _shared_audio_duration(audio_path, ffmpeg_exe, default=5.0)


def _fade_suffix(total_dur: float, fade: float = None) -> str:
    """Return a ',fade=in,fade=out' filter suffix for a segment of the given
    duration, or '' when the segment is too short to fade cleanly. Applied to
    the video stream only, inside the segment's own timeline, so it never
    shortens the segment or desyncs the audio."""
    if fade is None:
        fade = _FADE_DUR
    if total_dur <= 2 * fade + 0.2:
        return ""
    return (f",fade=t=in:st=0:d={fade:.2f}"
            f",fade=t=out:st={total_dur - fade:.3f}:d={fade:.2f}")


_SILENCE_GAP_MS = 500

# Short fade baked into each slide segment's own timeline so consecutive slides
# dip softly into one another. Because it lives INSIDE each segment (rather than
# overlapping neighbours like xfade did), the video and audio timelines stay the
# same length and never drift out of sync - the fix for BUG-01.
_FADE_DUR = 0.18


def _make_gap_silence(reference_dir: Path, ffmpeg_exe: str, gap_ms: int = _SILENCE_GAP_MS) -> Path:
    """Create (or reuse) a short silence clip used to pad between concatenated
    narration segments, so cuts don't slam together with zero gap. Cached per
    directory since every call within a lesson needs the same clip."""
    silence_path = reference_dir / f"_gap_silence_{gap_ms}ms.mp3"
    if not silence_path.exists():
        subprocess.run(
            [
                ffmpeg_exe, "-y",
                "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-t", f"{gap_ms / 1000:.3f}",
                "-q:a", "9",
                _fwd(silence_path),
            ],
            capture_output=True, text=True,
        )
    return silence_path


def _concat_audio(audio_paths: List[str], output_path: Path, ffmpeg_exe: str) -> float:
    """Concatenate MP3 files into one, with a short silence gap inserted between
    each clip so segments don't slam together with a hard, zero-padding cut
    (voice_agent.py trims silence at each segment's own edges, so without this
    gap the concatenation is a raw back-to-back splice). Returns total duration
    in seconds."""
    if len(audio_paths) == 1:
        shutil.copy2(audio_paths[0], output_path)
        return _get_audio_duration(audio_paths[0], ffmpeg_exe)

    silence_path = _make_gap_silence(output_path.parent, ffmpeg_exe)

    concat_list = output_path.parent / f"audio_concat_{output_path.stem}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for idx, ap in enumerate(audio_paths):
            if idx > 0 and silence_path.exists():
                f.write(f"file '{_fwd(silence_path)}'\n")
            f.write(f"file '{_fwd(Path(ap))}'\n")

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0",
        "-i", _fwd(concat_list),
        "-c", "copy",
        _fwd(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        cmd2 = [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
                "-i", _fwd(concat_list), "-c:a", "aac", _fwd(output_path)]
        subprocess.run(cmd2, capture_output=True, text=True)

    concat_list.unlink(missing_ok=True)
    return _get_audio_duration(str(output_path), ffmpeg_exe)


def _apply_ducked_music(
    video_path: str,
    output_path: str,
    ffmpeg_exe: str,
    bg_track: str = "assets/music/bg_track.mp3",
    bg_volume: float = 0.15,
    ducking_ratio: float = 14.0,
) -> str:
    """
    Mix background music with sidechain ducking.
    Music automatically ducks when narration plays, rises during pauses.
    Uses -stream_loop -1 to loop music without loading it all into memory.
    """
    # An empty/whitespace track (e.g. the no_music profile) must be treated as
    # "no music" - Path("") resolves to the current directory, which exists, so
    # a naive .exists() check would try to mux the cwd and fail the whole step.
    if not bg_track or not str(bg_track).strip():
        return video_path
    bg = Path(bg_track)
    if not bg.exists():
        print(f"  Background music not found: {bg_track}")
        return video_path

    print("  Mixing background music with sidechain ducking...")
    tmp = str(Path(output_path).parent / "_music_tmp.mp4")
    filter_complex = (
        f"[1:a]volume={bg_volume}[bg_raw];"
        f"[0:a]asplit=2[sc][main];"
        f"[bg_raw][sc]sidechaincompress=threshold=0.015:ratio={ducking_ratio}:attack=50:release=800[bg_ducked];"
        f"[main][bg_ducked]amix=inputs=2:duration=first:dropout_transition=2[out_a]"
    )
    cmd = [
        ffmpeg_exe, "-y",
        "-i", _fwd(Path(video_path)),
        "-stream_loop", "-1", "-i", _fwd(bg),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[out_a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        tmp,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and Path(tmp).exists():
        shutil.move(tmp, output_path)
        print("  Background music mixed successfully.")
        return output_path
    print(f"  Music mix failed (ffmpeg rc={result.returncode}): {result.stderr[-300:]}")
    if Path(tmp).exists():
        Path(tmp).unlink()
    return video_path


def _apply_xfade_transitions(
    segment_files: List[Path],
    durations: List[float],
    output_path: Path,
    ffmpeg_exe: str,
    transition_duration: float = 0.5,
    transition_hints: Optional[List[str]] = None,
) -> bool:
    """
    Apply per-layout xfade transitions between video segments. (B.2)
    transition_hints[i] = transition type for segment i coming in.
    Returns True on success, False if fallback to simple concat.

    RETAINED BUT UNUSED: overlapping xfade shortens the video timeline while the
    per-segment audio does not, which desynced narration (BUG-01). Composition
    now concatenates on a single shared timeline with per-segment baked fades.
    A future layout-aware transition system (blueprint §17) must overlap audio
    and video by the SAME amount before this can be re-enabled.
    """
    n = len(segment_files)
    if n <= 1:
        return False

    hints = transition_hints or ["fade"] * n
    # pad hints to match segment count
    while len(hints) < n:
        hints.append("fade")

    inputs = []
    for seg in segment_files:
        inputs += ["-i", _fwd(seg)]

    vf_parts = []
    af_parts = []
    offset = 0.0
    last_v = "[0:v]"
    last_a = "[0:a]"

    for i in range(1, n):
        offset += max(durations[i - 1] - transition_duration, 0.1)
        out_v = f"[v{i}]"
        out_a = f"[a{i}]"
        trans = hints[i] if hints[i] in _VALID_TRANSITIONS else "fade"
        vf_parts.append(
            f"{last_v}[{i}:v]xfade=transition={trans}:duration={transition_duration}:offset={offset:.3f}{out_v}"
        )
        # Clean audio concat with short fade-out/fade-in instead of crossfade
        # which blends two narration segments together and sounds garbled
        fade_ms = int(transition_duration * 1000)
        af_parts.append(
            f"{last_a}[{i}:a]concat=n=2:v=0:a=1{out_a}"
        )
        last_v = out_v
        last_a = out_a

    filter_complex = ";".join(vf_parts + af_parts)
    cmd = (
        [ffmpeg_exe, "-y"]
        + inputs
        + [
            "-filter_complex", filter_complex,
            "-map", last_v,
            "-map", last_a,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            _fwd(output_path),
        ]
    )
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and output_path.exists()


_VALID_TRANSITIONS = {
    "fade", "fadeblack", "fadewhite", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown", "zoomin", "smoothleft",
    "circlecrop", "dissolve",
}


def _apply_ken_burns(
    img_path: str,
    duration: float,
    output_path: str,
    ffmpeg_exe: str,
    fps: int = 30,
) -> Optional[str]:
    """
    Apply a slow zoom-in (Ken Burns) effect to a static slide. (B.1)
    Only used for slides where duration > KEN_BURNS_THRESHOLD.
    Returns path to created MP4 or None on failure.
    """
    # scale up first to avoid zoompan pixel shortage. Fade is baked in here
    # because the caller muxes this clip with -c:v copy (can't add it later).
    cmd = [
        ffmpeg_exe, "-y",
        "-loop", "1",
        "-i", _fwd(Path(img_path)),
        "-t", f"{duration:.3f}",
        "-vf", (
            f"scale=3840:2160:flags=lanczos,"
            f"zoompan=z='min(zoom+0.0002,1.06)':d={int(duration * fps)}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080,"
            f"fps={fps}{_fade_suffix(duration)}"
        ),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
        "-an",
        _fwd(Path(output_path)),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and Path(output_path).exists():
        return output_path
    return None


# Animation presets: name -> (transition_duration_seconds, ken_burns_enabled)
ANIMATION_PRESETS = {
    "minimal": {"transition_duration": 0.3, "ken_burns": False},
    "smooth":  {"transition_duration": 0.5, "ken_burns": False},
    "dynamic": {"transition_duration": 0.5, "ken_burns": False},
}

# Layout-aware transition mapping: gives each layout type a visually fitting transition
_LAYOUT_TRANSITIONS = {
    "title": "fadeblack",
    "chapter_title": "fadeblack",
    "agenda": "slideleft",
    "content": "fade",
    "prose": "fade",
    "analogy": "smoothleft",
    "timeline": "slideleft",
    "code": "wipedown",
    "code_output": "wipedown",
    "two_column": "wipeleft",
    "comparison": "wipeleft",
    "big_number": "zoomin",
    "quote": "dissolve",
    "key_insight": "dissolve",
    "hook": "fadeblack",
    "summary": "fadeblack",
    "quiz": "slideup",
    "bar_chart": "slideup",
    "think_pause": "dissolve",
    "warning": "fade",
    "tip": "fade",
    "definition": "fade",
    "mental_model": "smoothleft",
    "numbered_steps": "slideleft",
    "cycle": "circlecrop",
    "checkpoint": "fade",
}


def _compose_intro_card(lesson_title: str, renderer, output_path: str, ffmpeg_exe: str, intro_sting: str) -> bool:
    print(f"  Generating intro card: {lesson_title}")
    out_dir = Path(output_path).parent
    slide_data = {
        "id": "intro_card",
        "layout": "title",
        "headline": lesson_title,
        "subtitle": "theTwoCubes Learning",
        "lesson_number": "INTRO"
    }
    try:
        renderer.render_slides([slide_data], str(out_dir), prefix="intro_")
    except Exception as e:
        print(f"  Intro rendering failed: {e}")
        return False
        
    img_path = out_dir / "intro_intro_card.png"
    if not img_path.exists():
        return False
        
    dur = _get_audio_duration(intro_sting, ffmpeg_exe)
    cmd = [
        ffmpeg_exe, "-y",
        "-loop", "1",
        "-i", _fwd(img_path),
        "-i", _fwd(Path(intro_sting)),
        "-t", f"{dur:.3f}",
        "-vf", "scale=1920:1080:flags=lanczos,fps=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        _fwd(Path(output_path))
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0 and Path(output_path).exists()


def _compose_outro_card(renderer, output_path: str, ffmpeg_exe: str, outro_music: str) -> bool:
    print("  Generating outro card...")
    out_dir = Path(output_path).parent
    slide_data = {
        "id": "outro_card",
        "layout": "summary",
        "headline": "Thanks for watching!",
        "bullets": [
            "Subscribe for more technical deep dives",
            "Check the description for resources"
        ],
        "lesson_number": ""
    }
    try:
        renderer.render_slides([slide_data], str(out_dir), prefix="outro_")
    except Exception as e:
        print(f"  Outro rendering failed: {e}")
        return False
        
    img_path = out_dir / "outro_outro_card.png"
    if not img_path.exists():
        return False
        
    dur = _get_audio_duration(outro_music, ffmpeg_exe)
    cmd = [
        ffmpeg_exe, "-y",
        "-loop", "1",
        "-i", _fwd(img_path),
        "-i", _fwd(Path(outro_music)),
        "-t", f"{dur:.3f}",
        "-vf", "scale=1920:1080:flags=lanczos,fps=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        _fwd(Path(output_path))
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0 and Path(output_path).exists()


def compose_video_aligned(
    slide_audio_pairs: List[Tuple[str, List[str]]],
    output_path: str,
    fps: int = 30,
    use_transitions: bool = True,
    prebuilt_segments: dict = None,
    transition_hints: List[str] = None,
    animation_preset: str = "smooth",
    ken_burns: bool = False,
    music_track: str = "assets/music/bg_track.mp3",
    bg_volume: float = 0.15,
    ducking_ratio: float = 14.0,
    intro_sting: str = "",
    outro_music: str = "",
    lesson_title: str = "",
    renderer = None,
) -> str:
    """
    Compose a video where each slide is displayed for the combined duration
    of its audio segments.

    slide_audio_pairs: [(slide_image_path, [audio_files]), ...]
    prebuilt_segments: optional {pair_index: prebuilt_mp4_path}
      - for pairs with a prebuilt video (e.g. code reveal), that video is
        used directly instead of encoding a static slide + audio.
    """
    print(f"  Composing {len(slide_audio_pairs)} slide groups...")

    ffmpeg_exe = _get_ffmpeg()
    output_abs = Path(output_path).resolve()
    segments_dir = output_abs.parent / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    prebuilt_segments = prebuilt_segments or {}
    transition_hints = list(transition_hints or []) or ["fade"] * len(slide_audio_pairs)

    preset_cfg = ANIMATION_PRESETS.get(animation_preset, ANIMATION_PRESETS["smooth"])
    transition_duration = preset_cfg["transition_duration"]
    # ken_burns overrides preset if True
    ken_burns_enabled = ken_burns or preset_cfg.get("ken_burns", False)

    from config.settings import settings
    ken_threshold = settings.KEN_BURNS_THRESHOLD_SECONDS if ken_burns_enabled else 99999.0

    segment_files: List[Path] = []
    segment_durations: List[float] = []
    used_transition_hints: List[str] = []

    for i, (slide_path, audio_files) in enumerate(slide_audio_pairs):
        hint = transition_hints[i] if i < len(transition_hints) else "fade"

        # use prebuilt segment if available (e.g. code reveal)
        if i in prebuilt_segments and Path(prebuilt_segments[i]).exists():
            pb = Path(prebuilt_segments[i])
            seg_out = segments_dir / f"seg_{i:04d}.mp4"
            shutil.copy2(pb, seg_out)
            dur = _get_audio_duration(_fwd(seg_out), ffmpeg_exe)
            segment_files.append(seg_out)
            segment_durations.append(dur)
            used_transition_hints.append(hint)
            print(f"  Slide {i+1}/{len(slide_audio_pairs)}: code reveal {dur:.1f}s")
            continue

        slide_abs = Path(slide_path).resolve()
        valid_audios = [a for a in audio_files if Path(a).exists()]

        if not valid_audios or not slide_abs.exists():
            print(f"  Group {i+1}: skipped (missing files).")
            continue

        merged_audio = segments_dir / f"merged_{i:04d}.mp3"
        total_dur = _concat_audio(valid_audios, merged_audio, ffmpeg_exe)

        seg_out = segments_dir / f"seg_{i:04d}.mp4"

        # Ken Burns for long static slides - uses exact duration, no apad drift
        if total_dur > ken_threshold:
            kb_video = str(segments_dir / f"kb_{i:04d}.mp4")
            # Ken Burns: use exact total_dur (no +1.0 overshoot)
            kb_result = _apply_ken_burns(str(slide_abs), total_dur, kb_video, ffmpeg_exe, fps)
            if kb_result:
                cmd = [
                    ffmpeg_exe, "-y",
                    "-i", _fwd(Path(kb_video)),
                    "-i", _fwd(merged_audio),
                    "-t", f"{total_dur:.3f}",
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",
                    _fwd(seg_out),
                ]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0 and seg_out.exists():
                    actual_dur = _get_audio_duration(_fwd(seg_out), ffmpeg_exe)
                    segment_files.append(seg_out)
                    segment_durations.append(actual_dur)
                    used_transition_hints.append(hint)
                    print(f"  Slide {i+1}/{len(slide_audio_pairs)}: Ken Burns {total_dur:.1f}s")
                    continue

        # Standard: loop static image for exact audio duration - no apad.
        # The fade suffix gives a soft in/out dip within this segment's own
        # timeline (BUG-01: no cross-segment overlap, so audio stays in sync).
        cmd = [
            ffmpeg_exe, "-y",
            "-loop", "1",
            "-i", _fwd(slide_abs),
            "-i", _fwd(merged_audio),
            "-t", f"{total_dur:.3f}",
            "-vf", f"scale=1920:1080:flags=lanczos,fps={fps}{_fade_suffix(total_dur)}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            _fwd(seg_out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and seg_out.exists():
            actual_dur = _get_audio_duration(_fwd(seg_out), ffmpeg_exe)
            segment_files.append(seg_out)
            segment_durations.append(actual_dur)
            used_transition_hints.append(hint)
            print(f"  Slide {i+1}/{len(slide_audio_pairs)}: {len(valid_audios)} audio clip(s), {total_dur:.1f}s")
        else:
            print(f"  Segment {i+1} failed: {result.stderr[-200:]}")

    if not segment_files:
        raise RuntimeError("No video segments produced.")

    # Concatenate on a SINGLE shared timeline. We intentionally no longer use
    # overlapping xfade transitions here: xfade shortens the video timeline by
    # the overlap while the concatenated per-segment audio does not, so narration
    # drifts progressively ahead of the visuals (BUG-01). Each segment already
    # carries a short baked-in fade in/out, so slides still dip softly while
    # audio and video advance in lockstep.
    concat_file = segments_dir / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for seg in segment_files:
            f.write(f"file '{_fwd(seg)}'\n")
    print(f"  Concatenating {len(segment_files)} segments (shared timeline)...")
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0",
        "-i", _fwd(concat_file),
        "-c", "copy",
        _fwd(output_abs),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # -c copy needs identical params across segments; a prebuilt segment
        # (code reveal / diagram) can differ. Re-encode as a safety net so one
        # odd segment can't abort the whole compose.
        print("  Stream-copy concat failed; re-encoding segments...")
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", _fwd(concat_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            _fwd(output_abs),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Final concat failed: {result.stderr[-300:]}")
    final_pre_music = output_abs

    # mix background music (with sidechain ducking)
    final_path = _apply_ducked_music(
        str(output_abs), str(output_abs), ffmpeg_exe,
        bg_track=music_track, bg_volume=bg_volume, ducking_ratio=ducking_ratio,
    )

    # Prepend Intro and Append Outro
    concat_list = []
    
    if intro_sting and renderer and lesson_title:
        intro_out = output_abs.parent / "intro_rendered.mp4"
        if _compose_intro_card(lesson_title, renderer, str(intro_out), ffmpeg_exe, intro_sting):
            concat_list.append(intro_out)
            
    concat_list.append(output_abs)
    
    if outro_music and renderer:
        outro_out = output_abs.parent / "outro_rendered.mp4"
        if _compose_outro_card(renderer, str(outro_out), ffmpeg_exe, outro_music):
            concat_list.append(outro_out)
            
    if len(concat_list) > 1:
        print("  Concatenating intro/outro with main video...")
        list_file = output_abs.parent / "final_concat_list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for c in concat_list:
                f.write(f"file '{_fwd(c)}'\n")
                
        final_out = output_abs.parent / f"{output_abs.stem}_with_io.mp4"
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", _fwd(list_file),
            "-c", "copy",
            _fwd(final_out)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and final_out.exists():
            shutil.move(str(final_out), str(output_abs))
        else:
            print(f"  Intro/Outro concat failed: {result.stderr[-200:]}")

    size_mb = output_abs.stat().st_size / (1024 * 1024)
    print(f"  Video saved: {output_abs} ({size_mb:.1f} MB)")
    return str(output_abs)
