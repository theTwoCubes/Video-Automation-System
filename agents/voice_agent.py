import asyncio
import re
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
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


def _loudnorm(audio_path: str, ffmpeg_exe: str):
    """Apply loudnorm to normalize audio level in-place."""
    tmp = audio_path + "_norm_tmp.mp3"
    cmd = [
        ffmpeg_exe, "-y",
        "-i", audio_path,
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-c:a", "libmp3lame", "-q:a", "2",
        tmp,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and Path(tmp).exists():
        shutil.move(tmp, audio_path)
    else:
        if Path(tmp).exists():
            Path(tmp).unlink()


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

        # build (text, path) pairs
        tasks = []
        for i, seg in enumerate(narration_segments):
            text = seg.get("text", "").strip()
            if not text:
                continue
            text = preprocess_for_tts(text)
            text = self._clean_for_tts(text)
            out_path = str(audio_dir / f"seg_{i:04d}.mp3")
            tasks.append((i, text, out_path, seg))

        # run TTS in parallel via thread pool
        audio_paths = self._synthesize_parallel(tasks, len(narration_segments))

        # normalize all audio levels
        try:
            ffmpeg_exe = _get_ffmpeg()
            for path in audio_paths:
                if Path(path).exists() and path.endswith(".mp3"):
                    _loudnorm(path, ffmpeg_exe)
        except Exception as e:
            print(f"  Audio normalization skipped: {e}")

        state["audio_paths"] = audio_paths
        print(f"  Generated {len(audio_paths)} audio segments.")
        return state

    def _synthesize_one(self, args: tuple) -> tuple[int, str]:
        i, text, out_path, seg = args
        try:
            self.tts.synthesize_sync(text, out_path)
            return i, out_path
        except Exception as e:
            print(f"  TTS error on segment {i}: {e}")
            # write empty file as placeholder so pipeline continues
            Path(out_path).touch()
            return i, out_path

    def _synthesize_parallel(self, tasks: list, total: int) -> list[str]:
        results = [None] * len(tasks)
        futures = {self._executor.submit(self._synthesize_one, t): idx
                   for idx, t in enumerate(tasks)}

        completed = 0
        for future in _as_completed(futures):
            idx = futures[future]
            i, path = future.result()
            results[idx] = path
            completed += 1
            print(f"  Synthesized segment {completed}/{total}")

        return [r for r in results if r is not None]

    def _clean_for_tts(self, text: str) -> str:
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        text = text.replace("...", ", ")
        text = re.sub(r"\[REF:[^\]]+\]", "", text)
        return text.strip()


def _as_completed(futures_map: dict):
    """Yield futures as they complete."""
    import concurrent.futures
    for future in concurrent.futures.as_completed(futures_map):
        yield future
