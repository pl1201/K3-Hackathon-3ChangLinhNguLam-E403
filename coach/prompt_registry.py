from coach.config import get_settings


def compile_prompt(name: str, fallback: str, **variables: str) -> str:
    """Load the production prompt from Langfuse with an in-code availability fallback."""
    settings = get_settings()
    if not (settings.tracing_enabled and settings.enable_langfuse_prompts):
        return fallback.format(**variables)
    try:
        from langfuse import get_client

        langfuse_fallback = fallback
        for variable in variables:
            langfuse_fallback = langfuse_fallback.replace(
                f"{{{variable}}}",
                f"{{{{{variable}}}}}",
            )
        prompt = get_client().get_prompt(name, type="text", fallback=langfuse_fallback)
        return prompt.compile(**variables)
    except Exception:
        # Prompt availability must not take down the learning flow. The fallback is
        # versioned with the app and exercised by the same regression suite.
        return fallback.format(**variables)
