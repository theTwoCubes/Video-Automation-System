from abc import ABC, abstractmethod
from pathlib import Path
from providers.llm.gemini import get_llm


class BaseAgent(ABC):
    def __init__(self):
        self.llm = get_llm()

    def _load_prompt(self, prompt_file: str) -> str:
        path = Path("prompts") / prompt_file
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @abstractmethod
    def run(self, state: dict) -> dict:
        """Execute agent logic. Returns updated state dict."""
        ...
