"""LangSmith tracing bootstrap.

LangChain / LangGraph emit traces to LangSmith automatically when the standard
``LANGCHAIN_*`` environment variables are set. This configures them from Settings
so every agent LLM call, the detector fan-out, and the review pipeline are traced
under one project — without touching any agent code. The API key is read from the
environment (``LANGSMITH_API_KEY``) and never logged or stored.
"""
from __future__ import annotations

import os

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.logging import get_logger

_logger = get_logger(__name__)


def configure_tracing(settings: Settings) -> bool:
    """Enable LangSmith tracing if requested and an API key is present. Returns enabled."""
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if not settings.langsmith_tracing:
        return False
    if not api_key:
        _logger.warning("LANGSMITH_TRACING is on but no LANGSMITH_API_KEY in env; tracing disabled")
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    # Newer LangSmith SDKs read the LANGSMITH_* aliases too.
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    _logger.info("LangSmith tracing enabled", extra={"context": {"project": settings.langsmith_project}})
    return True
