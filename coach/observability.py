from contextlib import nullcontext
import re
from typing import Any

from coach.config import get_settings


class _NoopObservation:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def update(self, **_kwargs):
        return None


_CLIENT_READY = False
_CLIENT = None
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.-]?\d){9,10}(?!\d)")


def _mask_otel_spans(*, params):
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    patches = {}
    for identifier, span in params.spans.items():
        replacements = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                masked = _PHONE.sub("[PHONE_REDACTED]", _EMAIL.sub("[EMAIL_REDACTED]", value))
                if masked != value:
                    replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(
                set_attributes={**replacements, "masking.applied": True}
            )
    return MaskOtelSpansResult(span_patches=patches) if patches else None


def _ensure_client():
    global _CLIENT_READY, _CLIENT
    from langfuse import Langfuse

    if not _CLIENT_READY:
        _CLIENT = Langfuse(mask_otel_spans=_mask_otel_spans)
        _CLIENT_READY = True
    return _CLIENT


def typed_observation(as_type: str, name: str):
    if not get_settings().tracing_enabled:
        return _NoopObservation()
    return _ensure_client().start_as_current_observation(as_type=as_type, name=name)


def langchain_callbacks() -> list[Any]:
    if not get_settings().tracing_enabled:
        return []
    _ensure_client()
    from langfuse.langchain import CallbackHandler

    return [CallbackHandler()]


def _safe_text(value: str | None, limit: int = 2000) -> str | None:
    if not value:
        return value
    # Avoid accidental control-character / oversized payload capture. The app
    # does not need full raw request objects in traces.
    return "".join(char for char in value if char.isprintable())[:limit]


def invocation_context(
    *,
    trace_id: str,
    session_id: str,
    user_id: str,
    operation: str,
    trace_input: dict[str, Any],
) -> Any:
    settings = get_settings()
    if not settings.tracing_enabled:
        return nullcontext()

    from langfuse import propagate_attributes

    langfuse = _ensure_client()
    root = langfuse.start_as_current_observation(
        as_type="agent",
        name=f"active-recall-{operation}",
        trace_context={"trace_id": trace_id},
    )
    attributes = propagate_attributes(
        trace_name="Active Recall Coach",
        user_id=user_id,
        session_id=session_id,
        version="0.1.0",
        tags=["active-recall", "langgraph", operation],
        metadata={
            "feature": "active-recall",
            "operation": operation,
            "framework": "langgraph",
            "app_version": "0.1.0",
        },
    )

    class CombinedContext:
        def __enter__(self):
            self.span = root.__enter__()
            attributes.__enter__()
            self.span.update(
                input={
                    key: _safe_text(value) if isinstance(value, str) else value
                    for key, value in trace_input.items()
                }
            )
            return self.span

        def __exit__(self, exc_type, exc, tb):
            attributes.__exit__(exc_type, exc, tb)
            return root.__exit__(exc_type, exc, tb)

    return CombinedContext()


def score_feedback(trace_id: str, value: bool, comment: str | None) -> bool:
    if not get_settings().tracing_enabled:
        return False
    _ensure_client().create_score(
        trace_id=trace_id,
        name="user-thumbs",
        value=1 if value else 0,
        data_type="BOOLEAN",
        comment=comment,
    )
    return True
