"""
Code reveal animator - B.4 (weighted timing) from FuturePLAN.md.

Line timing weights:
  - Blank line:            0.05s
  - Comment (// or #):    0.30s
  - Simple closing line:   0.50s  (}, return, #include, using)
  - Complex line:          0.70 + (char_count/80)*0.60  capped at 1.8s

Total duration = audio_duration (forced by FFmpeg -shortest).
"""
import subprocess
import shutil
import re
from pathlib import Path
from typing import Optional

from services.media.ffmpeg import fwd as _fwd, get_audio_duration as _shared_audio_duration


def _get_audio_duration(path: str, ffmpeg_exe: str = None) -> float:
    """Defaults to 5.0s when unreadable, matching the code-reveal fallback."""
    return _shared_audio_duration(path, ffmpeg_exe, default=5.0)


#  B.4: Weighted per-line duration 

_SIMPLE_PATTERN = re.compile(
    r"^\s*("
    r"\}[,;]?|"           # closing brace
    r"return\s|"          # return statement
    r"#include|#pragma|"  # preprocessor
    r"using\s+namespace|" # using
    r"public:|private:|protected:|"  # access specifiers
    r"break;|continue;"   # flow control keywords
    r")"
)
_COMMENT_PATTERN = re.compile(r"^\s*(//|#|/\*|\*)")


def _line_weight(line: str) -> float:
    """Return relative weight (seconds) for one line in the reveal sequence."""
    s = line.strip()
    if not s:
        return 0.05
    if _COMMENT_PATTERN.match(s):
        return 0.30
    if _SIMPLE_PATTERN.match(s):
        return 0.50
    # complex line - scale by character count
    return min(0.70 + (len(s) / 80) * 0.60, 1.8)


def _compute_frame_durations(lines: list[str], total_duration: float) -> list[float]:
    """
    Compute per-frame durations proportional to line complexity,
    so the sum equals total_duration.
    """
    weights = [_line_weight(l) for l in lines]
    total_weight = sum(weights) or 1.0
    return [w / total_weight * total_duration for w in weights]


#  Frame rendering 

def _reveal_lines(code: str) -> list[str]:
    """The canonical list of lines used for a progressive reveal: strip leading
    blank lines only (interior/trailing blanks are kept so spacing is faithful).

    This is the SINGLE source of truth for which lines become reveal frames.
    Both the frame renderer and the per-line weight computation call it, so the
    two lists always have the same length - previously they used different
    filters, so the weighted-timing path silently fell back to uniform timing
    on nearly every slide."""
    reveals: list[str] = []
    for line in code.split("\n"):
        if reveals or line.strip():
            reveals.append(line)
    return reveals


def _render_reveal_frames(
    slide_data: dict,
    frames_dir: Path,
    renderer,
    slide_index: int = 0,
    total_slides: int = 0,
) -> list[str]:
    """Render one PNG per code line (progressive reveal)."""
    reveals = _reveal_lines(slide_data.get("code_content", ""))

    if len(reveals) <= 1:
        return []

    frame_paths = []
    for n in range(1, len(reveals) + 1):
        partial = {**slide_data, "code_content": "\n".join(reveals[:n])}
        out = str(frames_dir / f"frame_{n:04d}.png")
        try:
            renderer.render_slide(partial, out, slide_index=slide_index, total_slides=total_slides)
            frame_paths.append(out)
        except Exception as e:
            print(f"    Frame {n}/{len(reveals)} error: {e}")
            if frame_paths:
                shutil.copy2(frame_paths[-1], out)
                frame_paths.append(out)

    return frame_paths


#  Video assembly 

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
    Create a code reveal video segment with weighted per-line timing.
    Returns path to MP4 or None (caller uses static image fallback).
    """
    output_abs = Path(output_path).resolve()
    frames_dir = output_abs.parent / f"reveal_{output_abs.stem}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    print("    Building code reveal animation (weighted timing)...")
    frame_paths = _render_reveal_frames(
        slide_data, frames_dir, renderer, slide_index, total_slides
    )

    if len(frame_paths) < 2:
        return None

    audio_dur = _get_audio_duration(merged_audio, ffmpeg_exe)
    n = len(frame_paths)

    # Compute per-line weights from the SAME line list the frames were rendered
    # from, so counts match and the weighted timing actually applies. Equal
    # distribution remains only as a defensive fallback if they ever diverge.
    reveals = _reveal_lines(slide_data.get("code_content", ""))
    if len(reveals) != n:
        frame_durations = [audio_dur / n] * n
    else:
        frame_durations = _compute_frame_durations(reveals, audio_dur)

    # write concat list with per-frame durations
    concat_file = frames_dir / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for fp, dur in zip(frame_paths, frame_durations):
            f.write(f"file '{_fwd(Path(fp))}'\n")
            f.write(f"duration {dur:.4f}\n")
        # repeat last frame (FFmpeg concat requirement)
        f.write(f"file '{_fwd(Path(frame_paths[-1]))}'\n")

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0", "-i", _fwd(concat_file),
        "-i", _fwd(Path(merged_audio)),
        "-vf", f"scale=1920:1080:flags=lanczos,fps={fps}",
        "-af", "apad",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
        # Canonical audio format (48k mono) so this code-reveal segment
        # stream-copies cleanly with the static segments in the final concat.
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
        "-t", f"{audio_dur:.3f}",
        _fwd(output_abs),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and output_abs.exists():
        print(f"    Code reveal: {n} lines, {audio_dur:.1f}s (weighted)")
        return str(output_abs)
    else:
        print(f"    Code reveal failed, using static: {result.stderr[-120:]}")
        return None
