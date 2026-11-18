"""
Unit tests for Phase 1: LLM Provider Configuration, Adapters, and Connectivity.
"""

import os
from unittest.mock import MagicMock, patch
import pytest
from src.config import get_llm_config, LLMConfig, SUPPORTED_PROVIDERS
from src.providers.factory import get_provider, test_provider_connectivity as run_provider_connectivity
from src.providers.openai_compatible import OpenAICompatibleProvider
from src.providers.base import ProviderTestResult, ProviderResponse


def test_supported_providers_list():
    """Verify supported providers include nvidia, ollama, and openai."""
    assert "nvidia" in SUPPORTED_PROVIDERS
    assert "ollama" in SUPPORTED_PROVIDERS
    assert "openai" in SUPPORTED_PROVIDERS


def test_default_config_loading():
    """Test default configuration values when env vars are unset."""
    with patch.dict(os.environ, {}, clear=True):
        config = get_llm_config()
        # Default is nvidia as requested for prototype
        assert config.provider == "nvidia"
        assert "nemotron" in config.model
        assert "integrate.api.nvidia.com" in config.base_url
        assert config.timeout == 30.0
        assert config.temperature == 0.2


def test_provider_overrides():
    """Test loading configs for each specific provider."""
    # NVIDIA
    nv_config = get_llm_config("nvidia")
    assert nv_config.provider == "nvidia"
    assert "nemotron" in nv_config.model

    # Ollama
    ol_config = get_llm_config("ollama")
    assert ol_config.provider == "ollama"
    assert "qwen" in ol_config.model or "2.5" in ol_config.model
    assert "11434" in ol_config.base_url

    # OpenAI
    oa_config = get_llm_config("openai")
    assert oa_config.provider == "openai"
    assert "gpt" in oa_config.model


def test_masked_api_key_security():
    """Test that API keys are never exposed in plaintext."""
    config_real = LLMConfig(
        provider="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3.5-bolt-e4b",
        api_key="nvapi-super-secret-key-123456789",
    )
    masked = config_real.masked_api_key
    assert "super-secret" not in masked
    assert masked.startswith("nvap")
    assert masked.endswith("6789")

    # Ollama has no secret to hide
    config_ollama = LLMConfig(
        provider="ollama",
        base_url="http://localhost:11434/v1",
        model="qwen2.5:3b",
        api_key="ollama",
    )
    assert "Local" in config_ollama.masked_api_key or "N/A" in config_ollama.masked_api_key


def test_missing_credentials_graceful_handling():
    """Test that missing API keys return clear diagnostic failure without crashing."""
    config_missing = LLMConfig(
        provider="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3.5-bolt-e4b",
        api_key="",
    )
    provider = OpenAICompatibleProvider(config_missing)
    result = provider.test_connection()

    assert isinstance(result, ProviderTestResult)
    assert not result.success
    assert result.error_type == "MissingCredentials"
    assert "NVIDIA_API_KEY" in result.message
    assert result.troubleshooting_tip is not None
    assert "build.nvidia.com" in result.troubleshooting_tip or ".env" in result.troubleshooting_tip


def test_unreachable_endpoint_graceful_handling():
    """Test that network connection errors are caught gracefully."""
    config_bad_url = LLMConfig(
        provider="ollama",
        base_url="http://127.0.0.1:54321/v1",  # Unused port
        model="qwen2.5:3b",
        api_key="test",
        timeout=1.0,
    )
    provider = OpenAICompatibleProvider(config_bad_url)
    result = provider.test_connection()

    assert isinstance(result, ProviderTestResult)
    assert not result.success
    assert "failed" in result.message.lower() or "connection" in result.message.lower()
    assert result.troubleshooting_tip is not None


def test_mocked_successful_connection():
    """Test successful connection response parsing with mocked client."""
    config = LLMConfig(
        provider="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3.5-bolt-e4b",
        api_key="nvapi-valid-mock-key",
    )
    provider = OpenAICompatibleProvider(config)

    # Mock OpenAI client completions
    mock_choice = MagicMock()
    mock_choice.message.content = "pong"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch.object(provider.client.chat.completions, "create", return_value=mock_response):
        result = provider.test_connection()
        assert result.success is True
        assert result.sample_response == "pong"
        assert result.latency_ms is not None
        assert result.latency_ms >= 0


def test_mocked_completion_call():
    """Test standard complete() call with mocked client."""
    config = LLMConfig(
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-valid-mock-key",
    )
    provider = OpenAICompatibleProvider(config)

    mock_choice = MagicMock()
    mock_choice.message.content = "Hello from AI"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch.object(provider.client.chat.completions, "create", return_value=mock_response):
        res = provider.complete("Hi there")
        assert isinstance(res, ProviderResponse)
        assert res.success is True
        assert res.content == "Hello from AI"
        assert res.model == "gpt-4o-mini"
        assert res.provider == "openai"


def test_factory_get_provider():
    """Verify factory returns functional provider instances."""
    provider = get_provider("nvidia")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.provider == "nvidia"


def test_convenience_run_provider_connectivity():
    """Verify convenience test function returns a ProviderTestResult."""
    # When credentials are missing, should return handled diagnostic failure
    result = run_provider_connectivity("nvidia")
    assert isinstance(result, ProviderTestResult)
    assert result.provider == "nvidia"

