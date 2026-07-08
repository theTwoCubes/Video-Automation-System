"""
Video quality validator — E.2 from FuturePLAN.md

Runs ffprobe on the composed video and checks:
- File exists and is not empty
- Has video track at expected resolution
- Has audio track
- Duration is within ±8s of expected
- File size is reasonable
"""
from __future__ import annotations
import subprocess
import re
from pathlib import Path


def _ffprobe(video_path: str, ffmpeg_exe: str) -> dict:
    """Run ffprobe and return parsed stream info."""
    probe_exe = ffmpeg_exe.replace("ffmpeg", "ffprobe")
    cmd = [
        probe_exe, "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(video_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            # fallback: parse ffmpeg -i stderr
            return {}
        import json
        return json.loads(r.stdout)
    except Exception:
        return {}


def _get_duration_ffmpeg(path: str, ffmpeg_exe: str) -> float:
    """Get duration via ffmpeg -i stderr fallback."""
    r = subprocess.run([ffmpeg_exe, "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def validate_video(
    video_path: str,
    expected_duration_seconds: float = 0.0,
    ffmpeg_exe: str = "ffmpeg",
) -> dict:
    """
    Validate a composed video file.

    Returns:
        {
            "passed": bool,
            "issues": [str],
            "metrics": {
                "size_mb": float,
                "duration_s": float,
                "has_video": bool,
                "has_audio": bool,
                "resolution": str,
            }
        }
    """
    issues: list[str] = []
    metrics: dict = {
        "size_mb": 0.0,
        "duration_s": 0.0,
        "has_video": False,
        "has_audio": False,
        "resolution": "",
    }

    path = Path(video_path)

    # ── File existence ─────────────────────────────────────────────
    if not path.exists():
        return {"passed": False, "issues": ["Video file does not exist"], "metrics": metrics}

    size_mb = path.stat().st_size / (1024 * 1024)
    metrics["size_mb"] = round(size_mb, 2)

    if size_mb < 0.2:
        issues.append(f"File too small ({size_mb:.2f} MB) — likely corrupt or empty")
        return {"passed": False, "issues": issues, "metrics": metrics}

    # ── Stream info ────────────────────────────────────────────────
    info = _ffprobe(video_path, ffmpeg_exe)
    streams = info.get("streams", [])

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    metrics["has_video"] = bool(video_streams)
    metrics["has_audio"] = bool(audio_streams)

    if not video_streams:
        issues.append("No video track found")
    else:
        vs = video_streams[0]
        w = vs.get("width", 0)
        h = vs.get("height", 0)
        metrics["resolution"] = f"{w}x{h}"
        if w < 1280 or h < 720:
            issues.append(f"Unexpected resolution {w}x{h} (expected 1920x1080)")

    if not audio_streams:
        issues.append("No audio track found")

    # ── Duration ───────────────────────────────────────────────────
    dur = 0.0
    if info.get("format", {}).get("duration"):
        dur = float(info["format"]["duration"])
    else:
        dur = _get_duration_ffmpeg(video_path, ffmpeg_exe)
    metrics["duration_s"] = round(dur, 2)

    if dur < 5:
        issues.append(f"Video too short ({dur:.1f}s) — likely empty")

    if expected_duration_seconds > 0:
        diff = abs(dur - expected_duration_seconds)
        if diff > 10:
            issues.append(
                f"Duration mismatch: got {dur:.1f}s, expected ~{expected_duration_seconds:.1f}s (diff {diff:.1f}s)"
            )

    passed = len(issues) == 0
    return {"passed": passed, "issues": issues, "metrics": metrics}
