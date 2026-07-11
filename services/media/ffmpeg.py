"""
Shared FFmpeg / ffprobe utilities - the single source of truth for locating the
binary, building filesystem paths FFmpeg accepts on Windows, probing media
duration, generating silence, and running commands with structured errors.

Historically composer.py, voice_agent.py, video_agent.py, code_animator.py and
diagram_renderer/html_animator.py each re-implemented these helpers, and they
drifted apart (three different "duration could not be read" defaults, two path
quoting styles). Everything now delegates here.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Sequence


class FFmpegError(RuntimeError):
    """Raised when an ffmpeg invocation exits non-zero and check=True."""

    def __init__(self, cmd: Sequence[str], returncode: int, stderr: str):
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stderr = stderr or ""
        super().__init__(f"ffmpeg exited {returncode}: {self.stderr[-400:]}")


_FFMPEG_CACHE: Optional[str] = None


def get_ffmpeg() -> str:
    """Locate the ffmpeg binary once and cache it. Prefers the imageio-ffmpeg
    bundled build (always present as a dependency), then a system ffmpeg."""
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE:
        return _FFMPEG_CACHE
    exe = None
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("FFmpeg not found. Run: pip install imageio-ffmpeg")
    _FFMPEG_CACHE = exe
    return exe


def fwd(p) -> str:
    """Absolute, forward-slash path - the form FFmpeg accepts on Windows."""
    return str(Path(p).resolve()).replace("\\", "/")


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")


def get_audio_duration(path, ffmpeg_exe: Optional[str] = None, default: float = 0.0) -> float:
    """Return media duration in seconds by parsing `ffmpeg -i` stderr (no ffprobe
    dependency). Returns `default` when the duration can't be determined - call
    sites that must never see a zero-length clip pass default=5.0."""
    exe = ffmpeg_exe or get_ffmpeg()
    r = subprocess.run([exe, "-i", str(path)], capture_output=True, text=True)
    m = _DUR_RE.search(r.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return default


def run_ffmpeg(args: Sequence, *, ffmpeg_exe: Optional[str] = None,
               check: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with `args` (exclude the exe and the leading -y, both added
    here). Captures stdout/stderr. Raises FFmpegError on non-zero exit when
    check=True, instead of returning a silently-falsy result the caller forgets
    to inspect."""
    exe = ffmpeg_exe or get_ffmpeg()
    cmd = [exe, "-y", *[str(a) for a in args]]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise FFmpegError(cmd, proc.returncode, proc.stderr)
    return proc


def make_silence(duration_ms: int, out_path, ffmpeg_exe: Optional[str] = None,
                 rate: int = 24000) -> None:
    """Generate a silent mono MP3 of the given duration."""
    exe = ffmpeg_exe or get_ffmpeg()
    run_ffmpeg(
        ["-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=mono",
         "-t", f"{duration_ms / 1000:.3f}", "-q:a", "9", fwd(out_path)],
        ffmpeg_exe=exe, check=False,
    )


def seconds_to_srt_time(s: float) -> str:
    """Format seconds as an SRT timestamp: HH:MM:SS,mmm."""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{int(sec):02d},{ms:03d}"
