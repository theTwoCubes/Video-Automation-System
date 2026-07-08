"""
VoiceAgent — Synthesizes narration segments to MP3 using edge-tts.

Improvements implemented:
- A.6: [PAUSE] tag handling — inserts 600ms silence between sub-segments
- C.3: Silence trimming — strips leading/trailing silence > 200ms
- A.5: Pacing score — logs WPM per segment, flags outliers
- Parallel synthesis via ThreadPoolExecutor(8)
- loudnorm audio normalization on all segments
"""
import re
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.base_agent import BaseAgent
from providers.tts.edge_tts_provider import get_tts
from config.pronunciation_lexicon import preprocess_for_tts


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    f = shutil.which("ffmpeg")
    if f:
        return f
    raise RuntimeError("FFmpeg not found.")


def _fwd(p) -> str:
    return str(Path(p).resolve()).replace("\\", "/")


def _loudnorm(audio_path: str, ffmpeg_exe: str) -> None:
    """Normalize audio level in-place using loudnorm."""
    tmp = audio_path + "_norm.mp3"
    cmd = [
        ffmpeg_exe, "-y", "-i", audio_path,
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-c:a", "libmp3lame", "-q:a", "2", tmp,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0 and Path(tmp).exists():
        shutil.move(tmp, audio_path)
    elif Path(tmp).exists():
        Path(tmp).unlink()


def _trim_silence(audio_path: str, ffmpeg_exe: str) -> None:
    """Strip leading and trailing silence > 200ms (C.3)."""
    tmp = audio_path + "_trim.mp3"
    cmd = [
        ffmpeg_exe, "-y", "-i", audio_path,
        "-af", (
            "silenceremove=start_periods=1:start_silence=0.2:start_threshold=-50dB"
            ":stop_periods=-1:stop_silence=0.2:stop_threshold=-50dB"
        ),
        "-c:a", "libmp3lame", "-q:a", "2", tmp,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0 and Path(tmp).exists():
        # Only replace if output is non-trivially large (avoid empty file bug)
        if Path(tmp).stat().st_size > 1024:
            shutil.move(tmp, audio_path)
        else:
            Path(tmp).unlink()
    elif Path(tmp).exists():
        Path(tmp).unlink()


def _get_audio_duration(path: str, ffmpeg_exe: str) -> float:
    r = subprocess.run([ffmpeg_exe, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def _concat_mp3s(parts: list[str], out: str, ffmpeg_exe: str) -> None:
    """Concatenate multiple MP3 files into one."""
    concat_file = out + ".concat.txt"
    with open(concat_file, "w") as f:
        for p in parts:
            f.write(f"file '{_fwd(p)}'\n")
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c", "copy", out,
    ]
    subprocess.run(cmd, capture_output=True)
    Path(concat_file).unlink(missing_ok=True)


def _make_silence(duration_ms: int, out_path: str, ffmpeg_exe: str) -> None:
    """Generate a silent MP3 segment of given duration."""
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=22050:cl=mono",
        "-t", str(duration_ms / 1000),
        "-c:a", "libmp3lame", "-q:a", "2",
        out_path,
    ]
    subprocess.run(cmd, capture_output=True)


class VoiceAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.tts = get_tts()
        self._executor = ThreadPoolExecutor(max_workers=8)

    def run(self, state: dict) -> dict:
        print("[VoiceAgent] Synthesizing audio...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        output_dir = state["output_dir"]
        audio_dir = Path(output_dir) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        narration_segments = [
            s for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
        ]

        tasks = []
        for i, seg in enumerate(narration_segments):
            text = seg.get("text", "").strip()
            if not text:
                continue
            text = preprocess_for_tts(text)
            text = self._clean_for_tts(text)
            out_path = str(audio_dir / f"seg_{i:04d}.mp3")
            tasks.append((i, text, out_path, seg))

        audio_paths = self._synthesize_parallel(tasks, len(narration_segments))

        # process: trim silence, then normalize
        try:
            ffmpeg_exe = _get_ffmpeg()
            for path in audio_paths:
                if Path(path).exists() and Path(path).stat().st_size > 1024:
                    _trim_silence(path, ffmpeg_exe)
                    _loudnorm(path, ffmpeg_exe)
        except Exception as e:
            print(f"  Post-processing skipped: {e}")

        # pacing score
        self._compute_pacing_scores(narration_segments, audio_paths, state)

        state["audio_paths"] = audio_paths
        print(f"  Generated {len(audio_paths)} audio segments.")
        return state

    def _synthesize_one(self, args: tuple) -> tuple[int, str]:
        i, text, out_path, seg = args

        # Handle [PAUSE] markers by splitting into sub-segments with silence
        if "[PAUSE]" in text:
            return i, self._synthesize_with_pauses(i, text, out_path, seg)

        try:
            self.tts.synthesize_sync(text, out_path)
            return i, out_path
        except Exception as e:
            print(f"  TTS error on segment {i}: {e}")
            Path(out_path).touch()
            return i, out_path

    def _synthesize_with_pauses(self, i: int, text: str, out_path: str, seg: dict) -> str:
        """Synthesize text containing [PAUSE] markers, inserting 600ms silence."""
        try:
            ffmpeg_exe = _get_ffmpeg()
        except Exception:
            # No ffmpeg — just strip markers and synthesize normally
            clean = text.replace("[PAUSE]", ". ")
            self.tts.synthesize_sync(clean, out_path)
            return out_path

        parts_text = [p.strip() for p in text.split("[PAUSE]") if p.strip()]
        part_files = []
        tmp_dir = Path(out_path).parent / f"_pause_tmp_{i}"
        tmp_dir.mkdir(exist_ok=True)

        for j, part in enumerate(parts_text):
            part_path = str(tmp_dir / f"part_{j:02d}.mp3")
            silence_path = str(tmp_dir / f"silence_{j:02d}.mp3")
            try:
                self.tts.synthesize_sync(part, part_path)
                part_files.append(part_path)
            except Exception:
                pass
            if j < len(parts_text) - 1:
                _make_silence(600, silence_path, ffmpeg_exe)
                part_files.append(silence_path)

        if part_files:
            _concat_mp3s(part_files, out_path, ffmpeg_exe)
        else:
            Path(out_path).touch()

        # cleanup temp files
        for f in tmp_dir.iterdir():
            f.unlink(missing_ok=True)
        tmp_dir.rmdir()

        return out_path

    def _synthesize_parallel(self, tasks: list, total: int) -> list[str]:
        results = [None] * len(tasks)
        futures = {self._executor.submit(self._synthesize_one, t): idx
                   for idx, t in enumerate(tasks)}

        completed = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                i, path = future.result()
                results[idx] = path
            except Exception as e:
                print(f"  Synthesis thread error: {e}")
            completed += 1
            print(f"  Synthesized {completed}/{total}")

        return [r for r in results if r is not None]

    def _compute_pacing_scores(
        self,
        segments: list[dict],
        audio_paths: list[str],
        state: dict,
    ) -> None:
        """Compute words-per-minute for each segment. Flag outliers. (A.5)"""
        try:
            ffmpeg_exe = _get_ffmpeg()
        except Exception:
            return

        flagged = []
        for seg, path in zip(segments, audio_paths):
            if not path or not Path(path).exists():
                continue
            dur = _get_audio_duration(path, ffmpeg_exe)
            if dur < 0.5:
                continue
            words = len(seg.get("text", "").split())
            wpm = int(words / (dur / 60))
            if wpm < 80 or wpm > 200:
                flagged.append({
                    "seg_id": seg.get("id", "?"),
                    "wpm": wpm,
                    "words": words,
                    "duration_s": round(dur, 1),
                })

        if flagged:
            print(f"  Pacing flags ({len(flagged)} segments outside 80-200 wpm):")
            for f in flagged:
                print(f"    {f['seg_id']}: {f['wpm']} wpm ({f['words']}w in {f['duration_s']}s)")
            state["pacing_flags"] = flagged

    def _clean_for_tts(self, text: str) -> str:
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        text = text.replace("...", ", ")
        text = re.sub(r"\[REF:[^\]]+\]", "", text)
        # don't strip [PAUSE] — handled by _synthesize_with_pauses
        return text.strip()
