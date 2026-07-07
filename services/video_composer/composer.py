import subprocess
import shutil
import tempfile
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
    # Duration appears in stderr: "Duration: HH:MM:SS.ss"
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
    """
    Concatenate multiple MP3 audio files into one using FFmpeg.
    Returns total duration in seconds.
    """
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
        # fallback: re-encode concat
        cmd[-4] = "-c:a"
        cmd[-3] = "aac"
        subprocess.run(cmd, capture_output=True, text=True)

    return _get_audio_duration(str(output_path), ffmpeg_exe)


def compose_video_aligned(
    slide_audio_pairs: List[Tuple[str, List[str]]],
    output_path: str,
    fps: int = 30,
) -> str:
    """
    Compose a video where each slide is shown for the combined duration
    of all its audio segments.

    slide_audio_pairs: [(slide_image_path, [audio_file1, audio_file2, ...]), ...]
    Each slide is displayed for the exact combined duration of its audio files.
    """
    print(f"  Composing {len(slide_audio_pairs)} slide groups...")

    ffmpeg_exe = _get_ffmpeg()
    output_abs = Path(output_path).resolve()
    segments_dir = output_abs.parent / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    segment_files: List[Path] = []

    for i, (slide_path, audio_files) in enumerate(slide_audio_pairs):
        slide_abs = Path(slide_path).resolve()
        valid_audios = [a for a in audio_files if Path(a).exists()]

        if not valid_audios:
            print(f"  Group {i+1}: no valid audio, skipping.")
            continue
        if not slide_abs.exists():
            print(f"  Group {i+1}: slide image missing, skipping.")
            continue

        # concatenate all audio for this slide
        merged_audio = segments_dir / f"merged_{i:04d}.mp3"
        total_dur = _concat_audio(valid_audios, merged_audio, ffmpeg_exe)

        # add 200ms tail so last word isn't clipped
        display_dur = total_dur + 0.2

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
            segment_files.append(seg_out)
            n_audio = len(valid_audios)
            print(f"  Slide {i+1}/{len(slide_audio_pairs)}: {n_audio} audio clip(s), {total_dur:.1f}s")
        else:
            print(f"  Segment {i+1} failed: {result.stderr[-150:]}")

    if not segment_files:
        raise RuntimeError("No video segments produced.")

    # concatenate all segments
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

    size_mb = output_abs.stat().st_size / (1024 * 1024)
    print(f"  Video saved: {output_abs} ({size_mb:.1f} MB)")
    return str(output_abs)


# keep old function for backward compat
def compose_video(slide_paths, audio_paths, output_path, fps=30):
    pairs = [(s, [a]) for s, a in zip(slide_paths, audio_paths)]
    return compose_video_aligned(pairs, output_path, fps)
