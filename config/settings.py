from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""

    OUTPUT_DIR: str = "output"
    SQLITE_PATH: str = "data/twocubes.db"
    ASSETS_DIR: str = "assets"

    VOICE_NAME: str = "en-US-GuyNeural"
    VOICE_RATE: str = "+0%"
    VOICE_PITCH: str = "+0Hz"

    SLIDE_WIDTH: int = 1920
    SLIDE_HEIGHT: int = 1080

    # Gemini model names (free tier)
    LLM_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # Cost guard - set 0 to disable
    MAX_COST_USD_PER_RUN: float = 0.50

    # Ken Burns threshold (seconds): slides longer than this get slow zoom
    KEN_BURNS_THRESHOLD_SECONDS: float = 7.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Tolerate stray keys in .env that don't map to a field (e.g. left over
        # after a setting is retired) instead of hard-failing startup on them.
        extra = "ignore"

    def ensure_dirs(self):
        for d in [self.OUTPUT_DIR, "data", self.ASSETS_DIR]:
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
