import time
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential
from providers.embeddings.base import EmbeddingProvider
from config.settings import settings


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.EMBEDDING_MODEL

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def embed(self, text: str) -> list[float]:
        result = self.client.models.embed_content(
            model=self.model,
            contents=text,
        )
        # new SDK returns EmbedContentResponse with a list of ContentEmbedding
        return result.embeddings[0].values

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for text in batch:
                embeddings.append(self.embed(text))
                time.sleep(0.05)  # 50ms delay - safe for free tier
        return embeddings


_provider: GeminiEmbeddingProvider | None = None


def get_embedder() -> GeminiEmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = GeminiEmbeddingProvider()
    return _provider
