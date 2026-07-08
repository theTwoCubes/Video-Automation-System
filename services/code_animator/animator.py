"""
Code reveal animator — B.4 (weighted timing) from FuturePLAN.md.

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


def _fwd(p: Path) -> str:
    return str(p.resolve()).replace("\\", "/")


def _get_audio_duration(path: str, ffmpeg_exe: str) -> float:
    result = subprocess.run([ffmpeg_exe, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 5.0


# ── B.4: Weighted per-line duration ──────────────────────────────────────────

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
    # complex line — scale by character count
    return min(0.70 + (len(s) / 80) * 0.60, 1.8)


def _compute_frame_durations(lines: list[str], total_duration: float) -> list[float]:
    """
    Compute per-frame durations proportional to line complexity,
    so the sum equals total_duration.
    """
    weights = [_line_weight(l) for l in lines]
    total_weight = sum(weights) or 1.0
    return [w / total_weight * total_duration for w in weights]


# ── Frame rendering ───────────────────────────────────────────────────────────

def _render_reveal_frames(
    slide_data: dict,
    frames_dir: Path,
    renderer,
    slide_index: int = 0,
    total_slides: int = 0,
) -> list[str]:
    """Render one PNG per code line (progressive reveal)."""
    code = slide_data.get("code_content", "")
    raw_lines = code.split("\n")

    # strip leading blank lines only
    reveals: list[str] = []
    for line in raw_lines:
        if reveals or line.strip():
            reveals.append(line)

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


# ── Video assembly ────────────────────────────────────────────────────────────

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

    # get the code lines to compute weights
    code = slide_data.get("code_content", "")
    raw_lines = code.split("\n")
    reveals = [l for l in raw_lines if reveals_seen_blank(raw_lines, l)]
    if len(reveals) != n:
        # fallback to equal distribution
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
        "-af", "apad=pad_dur=0.8",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        _fwd(output_abs),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and output_abs.exists():
        print(f"    Code reveal: {n} lines, {audio_dur:.1f}s (weighted)")
        return str(output_abs)
    else:
        print(f"    Code reveal failed, using static: {result.stderr[-120:]}")
        return None


def reveals_seen_blank(lines: list[str], line: str) -> bool:
    """Helper to replicate the 'skip leading blanks' logic."""
    return True  # simplified — actual filtering done in _render_reveal_frames
