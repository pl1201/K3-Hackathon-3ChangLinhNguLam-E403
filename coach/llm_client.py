"""Provider-aware clients shared by Instructor integrations."""

from openai import OpenAI

from coach.config import Settings


def create_openai_compatible_client(settings: Settings) -> OpenAI:
    """Create an SDK client for OpenAI or DeepSeek's compatible endpoint."""
    if not settings.llm_api_key:
        raise RuntimeError(f"API key for LLM_PROVIDER={settings.llm_provider} is required")
    kwargs: dict[str, str] = {"api_key": settings.llm_api_key}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return OpenAI(**kwargs)
