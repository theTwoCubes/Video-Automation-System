from abc import ABC, abstractmethod
from providers.llm.gemini import get_llm


class BaseAgent(ABC):
    def __init__(self):
        self.llm = get_llm()

    @abstractmethod
    def run(self, state: dict) -> dict:
        """Execute agent logic. Returns updated state dict."""
        ...
