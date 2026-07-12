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

# Intro/outro cards are short branded bumpers, NOT the full length of their music
# sting. The sting is trimmed to these durations with a fade-out so a 2-3 minute
# music file can't inflate the video by minutes of a static logo card.
_INTRO_SECONDS = 4.0
_OUTRO_SECONDS = 5.0
_CARD_AUDIO_FADE = 0.6

# Canonical audio format for EVERY segment and card. All producers must encode to
# this exact rate/channel count so the final concat can stream-copy without the
# concat demuxer corrupting the audio timeline on a format change (which drifted
# narration by ~40s when the music cards were 44.1k stereo vs 48k mono segments).
_AUDIO_RATE = "48000"
_AUDIO_CH = "1"
_AUDIO_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", _AUDIO_RATE, "-ac", _AUDIO_CH]


def _lead_in_ms() -> int:
    """Per-slide lead-in silence (ms), from settings.SLIDE_LEAD_IN_MS. Read at call
    time so the env var is honoured without a module reload. Silence prepended to
    every slide's audio so the slide is on screen for a beat before narration
    begins, instead of the voice starting the instant it appears."""
    from config.settings import settings
    return max(0, int(settings.SLIDE_LEAD_IN_MS))


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
    """Concatenate a slide's MP3 clips into one track. A `_LEAD_IN_MS` silence is
    prepended so the slide holds for a beat before the voice starts, and a short
    silence gap is inserted between clips so cuts don't slam together (voice_agent
    trims silence at each clip's own edges). Returns total duration in seconds
    (including the lead-in), so the caller sizes the video segment to match.
    The lead-in and gap clips share the narration's 24 kHz mono format, so the
    stream-copy concat below stays clean."""
    lead_ms = _lead_in_ms()
    lead_in = _make_gap_silence(output_path.parent, ffmpeg_exe, lead_ms) if lead_ms > 0 else None
    gap = _make_gap_silence(output_path.parent, ffmpeg_exe)

    concat_list = output_path.parent / f"audio_concat_{output_path.stem}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        if lead_in and lead_in.exists():
            f.write(f"file '{_fwd(lead_in)}'\n")
        for idx, ap in enumerate(audio_paths):
            if idx > 0 and gap.exists():
                f.write(f"file '{_fwd(gap)}'\n")
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
        *_AUDIO_ARGS,
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


# Animation presets: name -> ken_burns default. Ken Burns is the only
# animation still applied; overlapping transitions were removed (they desynced
# audio/video - BUG-01; slides now dip via a short per-segment baked fade).
ANIMATION_PRESETS = {
    "minimal": {"ken_burns": False},
    "smooth":  {"ken_burns": False},
    "dynamic": {"ken_burns": False},
}


def _compose_intro_card(lesson_title: str, renderer, output_path: str, ffmpeg_exe: str, intro_sting: str) -> bool:
    print(f"  Generating intro card: {lesson_title}")
    out_dir = Path(output_path).parent
    slide_data = {
        "id": "intro_card",
        "layout": "intro",
    }
    try:
        renderer.render_slides([slide_data], str(out_dir), prefix="intro_")
    except Exception as e:
        print(f"  Intro rendering failed: {e}")
        return False
        
    img_path = out_dir / "intro_intro_card.png"
    if not img_path.exists():
        return False

    return _render_card_clip(img_path, intro_sting, output_path, ffmpeg_exe, _INTRO_SECONDS)


def _compose_outro_card(renderer, output_path: str, ffmpeg_exe: str, outro_music: str) -> bool:
    print("  Generating outro card...")
    out_dir = Path(output_path).parent
    slide_data = {
        "id": "outro_card",
        "layout": "outro",
    }
    try:
        renderer.render_slides([slide_data], str(out_dir), prefix="outro_")
    except Exception as e:
        print(f"  Outro rendering failed: {e}")
        return False
        
    img_path = out_dir / "outro_outro_card.png"
    if not img_path.exists():
        return False

    return _render_card_clip(img_path, outro_music, output_path, ffmpeg_exe, _OUTRO_SECONDS)


def _render_card_clip(img_path, music: str, output_path: str, ffmpeg_exe: str, seconds: float) -> bool:
    """Render a static card image into a short MP4 of exactly `seconds`, with the
    music sting trimmed to that length and faded out at the end. If the sting is
    missing/empty the card still renders with silent audio so the clip length is
    deterministic (never the full, possibly multi-minute, music file)."""
    fade_start = max(seconds - _CARD_AUDIO_FADE, 0.0)
    vf = f"scale=1920:1080:flags=lanczos,fps=30{_fade_suffix(seconds)}"
    cmd = [ffmpeg_exe, "-y", "-loop", "1", "-i", _fwd(img_path)]
    has_music = bool(music and str(music).strip() and Path(music).exists())
    if has_music:
        cmd += ["-i", _fwd(Path(music)),
                "-af", f"afade=t=out:st={fade_start:.2f}:d={_CARD_AUDIO_FADE}"]
    else:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r={_AUDIO_RATE}:cl=mono"]
    cmd += [
        "-t", f"{seconds:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
        *_AUDIO_ARGS,
        "-shortest",
        _fwd(Path(output_path)),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  Card clip failed: {res.stderr[-200:]}")
    return res.returncode == 0 and Path(output_path).exists()


def compose_video_aligned(
    slide_audio_pairs: List[Tuple[str, List[str]]],
    output_path: str,
    fps: int = 30,
    prebuilt_segments: dict = None,
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

    preset_cfg = ANIMATION_PRESETS.get(animation_preset, ANIMATION_PRESETS["smooth"])
    # ken_burns overrides preset if True
    ken_burns_enabled = ken_burns or preset_cfg.get("ken_burns", False)

    from config.settings import settings
    ken_threshold = settings.KEN_BURNS_THRESHOLD_SECONDS if ken_burns_enabled else 99999.0

    segment_files: List[Path] = []

    for i, (slide_path, audio_files) in enumerate(slide_audio_pairs):
        # use prebuilt segment if available (e.g. code reveal)
        if i in prebuilt_segments and Path(prebuilt_segments[i]).exists():
            pb = Path(prebuilt_segments[i])
            seg_out = segments_dir / f"seg_{i:04d}.mp4"
            shutil.copy2(pb, seg_out)
            dur = _get_audio_duration(_fwd(seg_out), ffmpeg_exe)
            segment_files.append(seg_out)
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
                    *_AUDIO_ARGS,
                    "-shortest",
                    _fwd(seg_out),
                ]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0 and seg_out.exists():
                    segment_files.append(seg_out)
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
            *_AUDIO_ARGS,
            "-shortest",
            _fwd(seg_out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and seg_out.exists():
            segment_files.append(seg_out)
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
    # Plain stream copy. This is only sync-safe because EVERY segment producer
    # (static, Ken Burns, code reveal, diagram, and the intro/outro cards) encodes
    # audio to the identical canonical format (_AUDIO_RATE Hz / _AUDIO_CH ch AAC).
    # A mismatched sample rate or channel count here silently corrupts the concat
    # demuxer's audio timeline and drifts narration by tens of seconds - the real
    # cause of the desync, not encoder priming (uniform-format copy drifts <50ms
    # across a whole lesson).
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0",
        "-i", _fwd(concat_file),
        "-c", "copy",
        _fwd(output_abs),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # A prebuilt segment (code reveal / diagram) can differ enough that even
        # stream copy fails. Full re-encode as a safety net so one odd segment
        # can't abort the whole compose.
        print("  Stream-copy concat failed; re-encoding segments...")
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", _fwd(concat_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
            *_AUDIO_ARGS,
            _fwd(output_abs),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Final concat failed: {result.stderr[-300:]}")

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
        # Stream copy - safe because the cards share the main body's canonical
        # audio format (see the segment-concat note above).
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
