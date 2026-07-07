import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    raise RuntimeError("FFmpeg not found. Run: pip install imageio-ffmpeg")


def _get_audio_duration(audio_path: str, ffmpeg_exe: str) -> float:
    """Get audio duration using ffmpeg -i (no ffprobe needed)."""
    import re
    result = subprocess.run(
        [ffmpeg_exe, "-i", audio_path],
        capture_output=True, text=True,
    )
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', result.stderr)
    if match:
        h = int(match.group(1))
        m = int(match.group(2))
        s = float(match.group(3))
        return h * 3600 + m * 60 + s
    return 5.0


def _fwd(p: Path) -> str:
    """Absolute forward-slash path for FFmpeg on Windows."""
    return str(p.resolve()).replace("\\", "/")


def _concat_audio(audio_paths: List[str], output_path: Path, ffmpeg_exe: str) -> float:
    """Concatenate MP3 files into one. Returns total duration in seconds."""
    if len(audio_paths) == 1:
        shutil.copy2(audio_paths[0], output_path)
        return _get_audio_duration(audio_paths[0], ffmpeg_exe)

    concat_list = output_path.parent / f"audio_concat_{output_path.stem}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for ap in audio_paths:
            f.write(f"file '{_fwd(Path(ap))}'\n")

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0",
        "-i", _fwd(concat_list),
        "-c", "copy",
        _fwd(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    concat_list.unlink(missing_ok=True)

    if result.returncode != 0:
        cmd2 = [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
                "-i", _fwd(concat_list), "-c:a", "aac", _fwd(output_path)]
        subprocess.run(cmd2, capture_output=True, text=True)

    return _get_audio_duration(str(output_path), ffmpeg_exe)


def _mix_background_music(video_path: str, output_path: str, ffmpeg_exe: str) -> str:
    """Mix background music under narration at 8% volume, if bg_track.mp3 exists."""
    bg = Path("assets/music/bg_track.mp3")
    if not bg.exists():
        return video_path

    print("  Mixing background music...")
    tmp = video_path + "_music_tmp.mp4"
    cmd = [
        ffmpeg_exe, "-y",
        "-i", _fwd(Path(video_path)),
        "-i", _fwd(bg),
        "-filter_complex",
        "[1:a]volume=0.08,aloop=loop=-1:size=2000000000[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        tmp,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and Path(tmp).exists():
        shutil.move(tmp, output_path)
        return output_path
    if Path(tmp).exists():
        Path(tmp).unlink()
    return video_path


def _apply_xfade_transitions(
    segment_files: List[Path],
    durations: List[float],
    output_path: Path,
    ffmpeg_exe: str,
    transition_duration: float = 0.4,
) -> bool:
    """
    Apply xfade transitions between all video segments.
    Returns True on success, False if fallback to simple concat.
    """
    n = len(segment_files)
    if n <= 1:
        return False

    # build filter_complex
    inputs = []
    for seg in segment_files:
        inputs += ["-i", _fwd(seg)]

    # chain xfade for video, acrossfade for audio
    vf_parts = []
    af_parts = []
    offset = 0.0
    last_v = "[0:v]"
    last_a = "[0:a]"

    for i in range(1, n):
        offset += max(durations[i - 1] - transition_duration, 0.1)
        out_v = f"[v{i}]"
        out_a = f"[a{i}]"
        vf_parts.append(
            f"{last_v}[{i}:v]xfade=transition=fade:duration={transition_duration}:offset={offset:.3f}{out_v}"
        )
        af_parts.append(
            f"{last_a}[{i}:a]acrossfade=d={transition_duration}{out_a}"
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
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            _fwd(output_path),
        ]
    )
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and output_path.exists()


def compose_video_aligned(
    slide_audio_pairs: List[Tuple[str, List[str]]],
    output_path: str,
    fps: int = 30,
    use_transitions: bool = True,
    prebuilt_segments: dict = None,
) -> str:
    """
    Compose a video where each slide is displayed for the combined duration
    of its audio segments.

    slide_audio_pairs: [(slide_image_path, [audio_files]), ...]
    prebuilt_segments: optional {pair_index: prebuilt_mp4_path}
      — for pairs with a prebuilt video (e.g. code reveal), that video is
        used directly instead of encoding a static slide + audio.
    """
    print(f"  Composing {len(slide_audio_pairs)} slide groups...")

    ffmpeg_exe = _get_ffmpeg()
    output_abs = Path(output_path).resolve()
    segments_dir = output_abs.parent / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    prebuilt_segments = prebuilt_segments or {}

    segment_files: List[Path] = []
    segment_durations: List[float] = []

    for i, (slide_path, audio_files) in enumerate(slide_audio_pairs):
        # use prebuilt segment if available (e.g. code reveal)
        if i in prebuilt_segments and Path(prebuilt_segments[i]).exists():
            pb = Path(prebuilt_segments[i])
            seg_out = segments_dir / f"seg_{i:04d}.mp4"
            shutil.copy2(pb, seg_out)
            dur = _get_audio_duration(_fwd(seg_out), ffmpeg_exe)
            segment_files.append(seg_out)
            segment_durations.append(dur)
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
        cmd = [
            ffmpeg_exe, "-y",
            "-loop", "1",
            "-i", _fwd(slide_abs),
            "-i", _fwd(merged_audio),
            "-vf", f"scale=1920:1080:flags=lanczos,fps={fps}",
            "-af", "apad=pad_dur=0.8",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            _fwd(seg_out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and seg_out.exists():
            actual_dur = _get_audio_duration(_fwd(seg_out), ffmpeg_exe)
            segment_files.append(seg_out)
            segment_durations.append(actual_dur)
            print(f"  Slide {i+1}/{len(slide_audio_pairs)}: {len(valid_audios)} audio clip(s), {total_dur:.1f}s")
        else:
            print(f"  Segment {i+1} failed: {result.stderr[-200:]}")

    if not segment_files:
        raise RuntimeError("No video segments produced.")

    # apply xfade transitions
    transitioned_path = output_abs.parent / "segments" / "with_transitions.mp4"
    used_transitions = False

    if use_transitions and len(segment_files) > 1:
        print("  Applying slide transitions...")
        success = _apply_xfade_transitions(
            segment_files, segment_durations, transitioned_path, ffmpeg_exe
        )
        if success:
            used_transitions = True
            print("  Transitions applied.")
        else:
            print("  Transitions failed, using simple concat.")

    if used_transitions:
        final_pre_music = transitioned_path
    else:
        concat_file = segments_dir / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in segment_files:
                f.write(f"file '{_fwd(seg)}'\n")
        print(f"  Concatenating {len(segment_files)} segments...")
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", _fwd(concat_file),
            "-c", "copy",
            _fwd(output_abs),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Final concat failed: {result.stderr[-300:]}")
        final_pre_music = output_abs

    # mix background music
    final_path = _mix_background_music(str(final_pre_music), str(output_abs), ffmpeg_exe)

    if used_transitions and final_path == str(final_pre_music) and not output_abs.exists():
        shutil.copy2(str(final_pre_music), str(output_abs))

    size_mb = output_abs.stat().st_size / (1024 * 1024)
    print(f"  Video saved: {output_abs} ({size_mb:.1f} MB)")
    return str(output_abs)


# backward compat
def compose_video(slide_paths, audio_paths, output_path, fps=30):
    pairs = [(s, [a]) for s, a in zip(slide_paths, audio_paths)]
    return compose_video_aligned(pairs, output_path, fps)

# backward compat
def compose_video(slide_paths, audio_paths, output_path, fps=30):
    pairs = [(s, [a]) for s, a in zip(slide_paths, audio_paths)]
    return compose_video_aligned(pairs, output_path, fps)
