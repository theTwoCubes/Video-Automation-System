import asyncio
import edge_tts
from providers.tts.base import TTSProvider
from config.settings import settings


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
        asyncio.run(asyncio.wait_for(self.synthesize(text, output_path), timeout=60.0))
        return output_path

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
