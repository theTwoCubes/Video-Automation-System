from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, output_path: str) -> str:
        """Synthesize text to audio. Returns output_path."""
        ...

    @property
    @abstractmethod
    def cost_per_thousand_chars(self) -> float:
        ...
