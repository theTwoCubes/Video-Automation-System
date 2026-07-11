import asyncio
import time
import edge_tts
from providers.tts.base import TTSProvider
from config.settings import settings

# edge-tts opens a websocket to Microsoft's service per call; that connection
# drops transiently under normal network conditions (and more often when
# several workers dial it at once, as VoiceAgent's ThreadPoolExecutor(8) does).
# A single dropped connection used to kill the entire pipeline run.
_MAX_RETRIES = 4
_RETRY_BACKOFF_SECONDS = 2.0


class EdgeTTSProvider(TTSProvider):
    """
    Microsoft Edge TTS - completely free, no API key needed.
    Uses neural voices from Azure Cognitive Services via edge-tts.
    """

    def __init__(self):
        self.voice = settings.VOICE_NAME
        self.rate = settings.VOICE_RATE
        self.pitch = settings.VOICE_PITCH

    async def synthesize(self, text: str, output_path: str) -> str:
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        await communicate.save(output_path)
        return output_path

    def synthesize_sync(self, text: str, output_path: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                asyncio.run(asyncio.wait_for(self.synthesize(text, output_path), timeout=60.0))
                return output_path
            except Exception as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF_SECONDS * attempt
                    print(f"    TTS attempt {attempt}/{_MAX_RETRIES} failed ({e!r}), retrying in {wait:.0f}s...")
                    time.sleep(wait)
        raise last_error

    @property
    def cost_per_thousand_chars(self) -> float:
        return 0.0

    @staticmethod
    async def list_voices() -> list[dict]:
        voices = await edge_tts.list_voices()
        return [v for v in voices if v["Locale"].startswith("en-")]


_provider: EdgeTTSProvider | None = None


def get_tts() -> EdgeTTSProvider:
    global _provider
    if _provider is None:
        _provider = EdgeTTSProvider()
    return _provider
