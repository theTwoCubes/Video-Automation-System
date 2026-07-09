from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""

    DEFAULT_TOPIC: str = "C Programming"
    TARGET_DURATION_MINUTES: int = 12
    TARGET_AUDIENCE: str = "beginners"

    OUTPUT_DIR: str = "output"
    SQLITE_PATH: str = "data/twocubes.db"
    USAGE_LOG_PATH: str = "data/usage.sqlite"
    PROMPTS_DIR: str = "prompts"
    ASSETS_DIR: str = "assets"

    VOICE_NAME: str = "en-US-GuyNeural"
    VOICE_RATE: str = "+0%"
    VOICE_PITCH: str = "+0Hz"

    SLIDE_WIDTH: int = 1920
    SLIDE_HEIGHT: int = 1080

    VIDEO_FPS: int = 30
    VIDEO_BITRATE: str = "8000k"

    LOG_LEVEL: str = "INFO"

    # Gemini model names (free tier)
    LLM_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # Cost guard — set 0 to disable
    MAX_COST_USD_PER_RUN: float = 0.50

    # Ken Burns threshold (seconds): slides longer than this get slow zoom
    KEN_BURNS_THRESHOLD_SECONDS: float = 7.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_dirs(self):
        for d in [self.OUTPUT_DIR, "data", self.ASSETS_DIR]:
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
