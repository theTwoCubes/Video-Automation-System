import json
import re
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_random_exponential
from providers.llm.base import LLMProvider
from config.settings import settings

_usage_log: list[dict] = []


def get_usage_log() -> list[dict]:
    return _usage_log


def clear_usage_log():
    _usage_log.clear()


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.LLM_MODEL

    @retry(stop=stop_after_attempt(8), wait=wait_random_exponential(multiplier=2, min=5, max=120))
    def complete(self, system: str, user: str, temperature: float = 0.7) -> str:
        prompt = f"{system}\n\n{user}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        self._log_usage("complete", response)
        return response.text.strip()

    @retry(stop=stop_after_attempt(8), wait=wait_random_exponential(multiplier=2, min=5, max=120))
    def complete_json(self, system: str, user: str) -> dict:
        prompt = f"{system}\n\n{user}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        self._log_usage("complete_json", response)
        text = response.text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    def _log_usage(self, method: str, response):
        try:
            meta = response.usage_metadata
            entry = {
                "method": method,
                "model": self.model,
                "input_tokens": getattr(meta, "prompt_token_count", 0),
                "output_tokens": getattr(meta, "candidates_token_count", 0),
                "thinking_tokens": getattr(meta, "thoughts_token_count", 0),
            }
            _usage_log.append(entry)

            # also persist to SQLite if db is available
            try:
                from db.usage_log import log_token_usage
                log_token_usage(
                    model=entry["model"],
                    input_tokens=entry["input_tokens"],
                    output_tokens=entry["output_tokens"],
                    thinking_tokens=entry["thinking_tokens"],
                )
            except Exception:
                pass
        except Exception:
            pass


_provider: GeminiProvider | None = None


def get_llm() -> GeminiProvider:
    global _provider
    if _provider is None:
        _provider = GeminiProvider()
    return _provider
