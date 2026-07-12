"""
VoiceAgent - Synthesizes narration segments to MP3 using edge-tts.
"""

import re
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.base_agent import BaseAgent
from providers.tts.edge_tts_provider import get_tts
from config.pronunciation_lexicon import preprocess_for_tts
from services.media.ffmpeg import (
    get_ffmpeg as _get_ffmpeg,
    fwd as _fwd,
    get_audio_duration as _get_audio_duration,
)


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
        self._executor = ThreadPoolExecutor(max_workers=4)

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

        self._failed_indices: list[int] = []
        audio_paths = self._synthesize_parallel(tasks, len(narration_segments))
        if self._failed_indices:
            print(f"  WARNING: {len(self._failed_indices)} segment(s) fell back to "
                  f"silence after TTS failures: {self._failed_indices}")
            state["tts_failures"] = self._failed_indices

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

    def _synthesize_one(self, args: tuple) -> tuple[int, str, bool]:
        i, text, out_path, seg = args

        try:
            # Handle [PAUSE] markers by splitting into sub-segments with silence
            if "[PAUSE]" in text:
                return i, self._synthesize_with_pauses(i, text, out_path, seg), True
            self.tts.synthesize_sync(text, out_path)
            return i, out_path, True
        except Exception as e:
            # A single dropped segment must not discard a whole (paid) lesson.
            # Substitute a silence clip sized to the text so downstream audio↔
            # slide alignment stays intact, and flag it for review.
            print(f"  Segment {i} TTS failed after retries ({e}); inserting silence.")
            self._make_placeholder_silence(text, out_path)
            return i, out_path, False

    def _make_placeholder_silence(self, text: str, out_path: str) -> None:
        """Write a silence clip roughly as long as the text would have taken to
        speak (~2.5 words/sec), so the timeline doesn't collapse where a segment
        failed. Falls back to an empty file if ffmpeg is unavailable."""
        try:
            ffmpeg_exe = _get_ffmpeg()
        except Exception:
            Path(out_path).touch()
            return
        words = max(1, len((text or "").split()))
        dur_ms = int(min(20000, max(1500, words / 2.5 * 1000)))
        _make_silence(dur_ms, out_path, ffmpeg_exe)

    def _synthesize_with_pauses(self, i: int, text: str, out_path: str, seg: dict) -> str:
        """Synthesize text containing [PAUSE] markers, inserting 600ms silence."""
        try:
            ffmpeg_exe = _get_ffmpeg()
        except Exception:
            # No ffmpeg - just strip markers and synthesize normally
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
            self.tts.synthesize_sync(part, part_path)
            part_files.append(part_path)
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
                i, path, ok = future.result()
                results[idx] = path
                if not ok:
                    self._failed_indices.append(i)
            except Exception as e:
                # _synthesize_one already swallows TTS errors; this is a last-
                # resort guard so an unexpected thread error still can't abort
                # the run. Drop in a silence placeholder to preserve alignment.
                print(f"  Synthesis thread error on segment {idx}: {e}")
                _, text, out_path, _seg = tasks[idx]
                self._make_placeholder_silence(text, out_path)
                results[idx] = out_path
                self._failed_indices.append(idx)
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
        # don't strip [PAUSE] - handled by _synthesize_with_pauses
        return text.strip()
