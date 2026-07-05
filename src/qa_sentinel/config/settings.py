from pathlib import Path

from decouple import Config, RepositoryEnv
from pydantic_settings import BaseSettings

_REPO_ROOT = Path(__file__).resolve().parents[3]
config = Config(RepositoryEnv(str(_REPO_ROOT / ".env")))


class Settings(BaseSettings):
    GEMINI_API_KEY             : str = config("GEMINI_API_KEY", cast=str)
    GITHUB_TOKEN               : str | None = config("GITHUB_TOKEN", default=None, cast=str)
    GITHUB_REPO                : str | None = config("GITHUB_REPO", default=None, cast=str)
    DATABASE_URL: str = config(
        "DATABASE_URL",
        default="postgresql://qa_sentinel:qa_sentinel@localhost:5432/qa_sentinel",
        cast=str,
    )

    ANTIGRAVITY_AGENT_ID: str = "antigravity-preview-05-2026"
    COMPUTER_USE_MODEL  : str = "gemini-3.5-flash"


settings = Settings()
