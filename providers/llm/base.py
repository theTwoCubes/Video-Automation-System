from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0.7,
                 thinking_budget: Optional[int] = None) -> str:
        """Return text completion. thinking_budget overrides the provider default
        for this call (None = use the configured default; 0 = disable reasoning)."""
        ...

    @abstractmethod
    def complete_json(self, system: str, user: str,
                      thinking_budget: Optional[int] = None) -> dict:
        """Return JSON-parsed completion. See complete() for thinking_budget."""
        ...
