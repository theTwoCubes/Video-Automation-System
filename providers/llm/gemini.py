import json
import re
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_random_exponential
from providers.llm.base import LLMProvider
from config.settings import settings

# Per-million token prices for gemini-2.5-flash. Thinking tokens are billed at
# the output rate, so the guard/report account for them accurately now that
# reasoning is enabled by default (see settings.LLM_THINKING_BUDGET).
_PRICE_INPUT_PER_M  = 0.075
_PRICE_OUTPUT_PER_M = 0.30
_PRICE_THINK_PER_M  = 0.30

_usage_log: list[dict] = []


def _loads_tolerant(text: str) -> dict:
    """Parse model JSON, tolerating the two failure modes Gemini exhibits even
    with response_mime_type=application/json: trailing prose after the closing
    brace, and a truncated tail. A strict json.loads failure used to trigger a
    full (billed) 8x retry of the whole call; this recovers the common cases
    first and only re-raises when the payload is genuinely unparseable."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Slice to the outermost JSON object/array and retry.
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start != -1:
        opener = text[start]
        closer = "}" if opener == "{" else "]"
        end = text.rfind(closer)
        if end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    # Last resort: let the original error surface so the caller/retry can act.
    return json.loads(text)


def get_usage_log() -> list[dict]:
    return _usage_log


def clear_usage_log():
    _usage_log.clear()


def _session_cost() -> float:
    """Compute total USD cost for the current in-memory session."""
    total = 0.0
    for e in _usage_log:
        total += (
            (e.get("input_tokens") or 0) * _PRICE_INPUT_PER_M  / 1_000_000
            + (e.get("output_tokens") or 0) * _PRICE_OUTPUT_PER_M / 1_000_000
            + (e.get("thinking_tokens") or 0) * _PRICE_THINK_PER_M / 1_000_000
        )
    return total


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.LLM_MODEL

    def _check_budget(self) -> None:
        """Abort if session cost exceeds MAX_COST_USD_PER_RUN (E.4)."""
        budget = settings.MAX_COST_USD_PER_RUN
        if budget <= 0:
            return
        cost = _session_cost()
        if cost > budget:
            raise RuntimeError(
                f"[BudgetGuard] Session cost ${cost:.4f} exceeds "
                f"MAX_COST_USD_PER_RUN=${budget:.2f}. "
                f"Set MAX_COST_USD_PER_RUN=0 to disable or increase the limit in .env"
            )

    def _resolve_thinking(self, thinking_budget: int | None) -> int:
        """Resolve the thinking budget for a call: explicit override wins,
        otherwise the configured default. Reasoning-heavy agents (plan, script,
        slide selection) inherit the default; cheap mechanical callers pass 0."""
        if thinking_budget is not None:
            return max(0, thinking_budget)
        return max(0, settings.LLM_THINKING_BUDGET)

    @retry(stop=stop_after_attempt(8), wait=wait_random_exponential(multiplier=2, min=5, max=120))
    def complete(self, system: str, user: str, temperature: float = 0.7,
                 thinking_budget: int | None = None) -> str:
        self._check_budget()
        prompt = f"{system}\n\n{user}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=self._resolve_thinking(thinking_budget)
                ),
            ),
        )
        self._log_usage("complete", response)
        return response.text.strip()

    @retry(stop=stop_after_attempt(8), wait=wait_random_exponential(multiplier=2, min=5, max=120))
    def complete_json(self, system: str, user: str,
                      thinking_budget: int | None = None) -> dict:
        self._check_budget()
        prompt = f"{system}\n\n{user}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(
                    thinking_budget=self._resolve_thinking(thinking_budget)
                ),
            ),
        )
        self._log_usage("complete_json", response)
        text = response.text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return _loads_tolerant(text)

    def _log_usage(self, method: str, response):
        try:
            meta = response.usage_metadata
            entry = {
                "method": method,
                "model": self.model,
                "input_tokens":   getattr(meta, "prompt_token_count",     0),
                "output_tokens":  getattr(meta, "candidates_token_count", 0),
                "thinking_tokens": getattr(meta, "thoughts_token_count",  0),
            }
            _usage_log.append(entry)

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
