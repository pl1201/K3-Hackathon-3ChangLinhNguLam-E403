from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Langfuse and model integrations read credentials from the process environment.
# Load local configuration before either SDK is imported elsewhere.
load_dotenv()


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    enable_llm: bool = True
    enable_tracing: bool = True
    enable_langfuse_prompts: bool = False
    llm_timeout_seconds: float = 30
    max_context_chars: int = 12_000
    enable_mock_fallback: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def llm_enabled(self) -> bool:
        return self.enable_llm and bool(self.openai_api_key)

    @property
    def tracing_enabled(self) -> bool:
        return self.enable_tracing and bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
