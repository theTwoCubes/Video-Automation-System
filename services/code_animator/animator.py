"""
Code reveal animator.
Takes a 'code' layout slide and produces a short MP4 where lines of code
appear one at a time (typewriter reveal), synchronized to the narration audio.

Flow:
  1. Split code_content into N lines
  2. Render N PNG frames (line 1 visible, lines 1-2 visible, ..., all visible)
  3. Assemble frames + audio into reveal.mp4 via FFmpeg concat
"""
import subprocess
import shutil
from pathlib import Path
from typing import Optional


def _fwd(p: Path) -> str:
    return str(p.resolve()).replace("\\", "/")


def _get_audio_duration(path: str, ffmpeg_exe: str) -> float:
    import re
    result = subprocess.run([ffmpeg_exe, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 5.0


def _render_reveal_frames(
    slide_data: dict,
    frames_dir: Path,
    renderer,
    slide_index: int = 0,
    total_slides: int = 0,
) -> list[str]:
    """
    Render N PNG frames for a code slide — each shows one more line.
    Returns list of frame PNG paths.
    """
    code = slide_data.get("code_content", "")
    raw_lines = code.split("\n")

    # group into logical "reveals" — skip completely blank separators
    # but keep blank lines that are part of the code
    reveals: list[str] = []
    for line in raw_lines:
        if reveals or line.strip():  # skip leading blanks
            reveals.append(line)

    if len(reveals) <= 1:
        return []

    frame_paths = []
    for n in range(1, len(reveals) + 1):
        partial = {
            **slide_data,
            "code_content": "\n".join(reveals[:n]),
        }
        out = str(frames_dir / f"frame_{n:04d}.png")
        try:
            renderer.render_slide(partial, out, slide_index=slide_index, total_slides=total_slides)
            frame_paths.append(out)
        except Exception as e:
            print(f"    Frame {n}/{len(reveals)} error: {e}")
            if frame_paths:
                # duplicate last good frame
                shutil.copy2(frame_paths[-1], out)
                frame_paths.append(out)

    return frame_paths


def create_code_reveal_segment(
    slide_data: dict,
    merged_audio: str,
    output_path: str,
    renderer,
    ffmpeg_exe: str,
    slide_index: int = 0,
    total_slides: int = 0,
    fps: int = 30,
) -> Optional[str]:
    """
    Create a code reveal video segment.
    Returns path to MP4 or None if creation fails (caller uses static image fallback).
    """
    output_abs = Path(output_path).resolve()
    frames_dir = output_abs.parent / f"reveal_{output_abs.stem}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    print(f"    Building code reveal animation...")
    frame_paths = _render_reveal_frames(
        slide_data, frames_dir, renderer, slide_index, total_slides
    )

    if len(frame_paths) < 2:
        return None

    audio_dur = _get_audio_duration(merged_audio, ffmpeg_exe)
    n = len(frame_paths)

    # give more time to later lines (progressive slow-down feels natural)
    # simple equal distribution for now
    dur_per_frame = audio_dur / n

    # write concat list with durations
    concat_file = frames_dir / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for fp in frame_paths:
            f.write(f"file '{_fwd(Path(fp))}'\n")
            f.write(f"duration {dur_per_frame:.4f}\n")
        # repeat last frame (FFmpeg concat needs a final file without duration)
        f.write(f"file '{_fwd(Path(frame_paths[-1]))}'\n")

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0", "-i", _fwd(concat_file),
        "-i", _fwd(Path(merged_audio)),
        "-vf", f"scale=1920:1080:flags=lanczos,fps={fps}",
        "-af", "apad=pad_dur=0.8",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        _fwd(output_abs),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and output_abs.exists():
        print(f"    Code reveal: {n} lines → {audio_dur:.1f}s")
        return str(output_abs)
    else:
        print(f"    Code reveal failed, using static: {result.stderr[-120:]}")
        return None
