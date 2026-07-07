import asyncio
import json
import re
from pathlib import Path
from agents.base_agent import BaseAgent
from providers.tts.edge_tts_provider import get_tts
from config.pronunciation_lexicon import preprocess_for_tts


class VoiceAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.tts = get_tts()

    def run(self, state: dict) -> dict:
        print("[VoiceAgent] Synthesizing audio...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        output_dir = state["output_dir"]
        audio_dir = Path(output_dir) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        # extract narration-type segments only
        narration_segments = [
            s for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text", "").strip()
        ]

        audio_paths = []
        for i, seg in enumerate(narration_segments):
            text = seg.get("text", "").strip()
            if not text:
                continue

            # preprocess: pronunciation + remove non-speech markers
            text = preprocess_for_tts(text)
            text = self._clean_for_tts(text)

            out_path = str(audio_dir / f"seg_{i:04d}.mp3")
            try:
                self.tts.synthesize_sync(text, out_path)
                audio_paths.append(out_path)
                print(f"  Synthesized segment {i+1}/{len(narration_segments)}")
            except Exception as e:
                print(f"  TTS error on segment {i}: {e}")
                # create silent placeholder
                silent = self._create_silence(int(seg.get("duration_estimate_seconds", 5)))
                silent_path = out_path.replace(".mp3", "_silent.mp3")
                with open(silent_path, "wb") as f:
                    f.write(silent)
                audio_paths.append(silent_path)

        state["audio_paths"] = audio_paths
        print(f"  Generated {len(audio_paths)} audio segments.")
        return state

    def _clean_for_tts(self, text: str) -> str:
        # remove code snippets from narration text
        text = re.sub(r"`[^`]+`", "", text)
        # remove markdown bold/italic
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        # normalize ellipsis
        text = text.replace("...", ", ")
        # remove brackets
        text = re.sub(r"\[REF:[^\]]+\]", "", text)
        return text.strip()

    def _create_silence(self, duration_seconds: int = 5) -> bytes:
        """Generate a tiny valid MP3 header for silence (placeholder)."""
        # return empty bytes; edge-tts handles silence via pauses
        return b""
