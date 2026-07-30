from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Langfuse and model integrations read credentials from the process environment.
# Load local configuration before either SDK is imported elsewhere.
load_dotenv()


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    llm_provider: Literal["openai", "deepseek"] = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    fast_openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"
    fast_deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    llama_cloud_api_key: str | None = Field(default=None, env="LLAMA_CLOUD_API_KEY")
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    enable_llm: bool = True
    enable_tracing: bool = True
    enable_langfuse_prompts: bool = False
    llm_timeout_seconds: float = 30
    max_context_chars: int = 12_000
    enable_mock_fallback: bool = True
    retrieval_mode: str = "hybrid"  # hybrid | semantic | keyword | legacy

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def llm_enabled(self) -> bool:
        return self.enable_llm and bool(self.llm_api_key)

    @property
    def llm_api_key(self) -> str | None:
        return self.deepseek_api_key if self.llm_provider == "deepseek" else self.openai_api_key

    @property
    def llm_model(self) -> str:
        return self.deepseek_model if self.llm_provider == "deepseek" else self.openai_model

    @property
    def fast_llm_model(self) -> str:
        return self.fast_deepseek_model if self.llm_provider == "deepseek" else self.fast_openai_model

    @property
    def llm_base_url(self) -> str | None:
        return self.deepseek_base_url if self.llm_provider == "deepseek" else None

    @property
    def tracing_enabled(self) -> bool:
        return self.enable_tracing and bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
