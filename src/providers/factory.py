"""
Factory module for initializing LLM providers.
"""

from typing import Optional
from src.config import get_llm_config, LLMConfig
from src.providers.base import BaseProvider, ProviderTestResult
from src.providers.openai_compatible import OpenAICompatibleProvider


def get_provider(provider_override: Optional[str] = None, config: Optional[LLMConfig] = None) -> BaseProvider:
    """
    Instantiate and return the configured LLM provider adapter.
    All supported providers (nvidia, ollama, openai) use the OpenAI-compatible adapter.
    """
    effective_config = config or get_llm_config(provider_override)
    return OpenAICompatibleProvider(effective_config)


def test_provider_connectivity(provider_override: Optional[str] = None) -> ProviderTestResult:
    """
    Convenience function to run a connectivity test against the active or specified provider.
    """
    provider = get_provider(provider_override)
    return provider.test_connection()
