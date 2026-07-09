from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0.7) -> str:
        """Return text completion."""
        ...

    @abstractmethod
    def complete_json(self, system: str, user: str) -> dict:
        """Return JSON-parsed completion."""
        ...
