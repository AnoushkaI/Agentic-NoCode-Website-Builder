"""
Configuration module for SitePilot AI.
Loads provider and model configurations from environment variables or .env file.
Supports NVIDIA NIM, Ollama, and OpenAI providers with clear validation.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

SUPPORTED_PROVIDERS = ("nvidia", "ollama", "openai")

DEFAULT_MODELS = {
    "nvidia": "nvidia/nemotron-3.5-bolt-e4b",
    "ollama": "qwen2.5:3b",
    "openai": "gpt-4o-mini",
}

DEFAULT_BASE_URLS = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "ollama": "http://localhost:11434/v1",
    "openai": "https://api.openai.com/v1",
}


@dataclass
class LLMConfig:
    provider: str
    base_url: str
    model: str
    api_key: Optional[str]
    timeout: float = 30.0
    temperature: float = 0.2

    @property
    def is_configured(self) -> bool:
        """Check if required credentials are present for this provider."""
        if self.provider == "ollama":
            # Ollama doesn't strictly require an API key
            return bool(self.base_url)
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("your_"))

    @property
    def masked_api_key(self) -> str:
        """Return masked key for safe UI and log display."""
        if not self.api_key or self.provider == "ollama":
            return "N/A (Local / Unauthenticated)"
        clean_key = self.api_key.strip()
        if len(clean_key) <= 8:
            return "********"
        return f"{clean_key[:4]}...{clean_key[-4:]}"


def get_llm_config(provider_override: Optional[str] = None) -> LLMConfig:
    """
    Get the active LLM configuration.
    If provider_override is given, loads config for that provider.
    Otherwise loads from LLM_PROVIDER env var (default: nvidia).
    """
    provider = (
        provider_override
        or os.getenv("LLM_PROVIDER", "nvidia")
    ).lower().strip()

    if provider not in SUPPORTED_PROVIDERS:
        provider = "nvidia"

    timeout = float(os.getenv("LLM_TIMEOUT", "30.0"))
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    if provider == "nvidia":
        api_key = os.getenv("NVIDIA_API_KEY", "")
        base_url = os.getenv("NVIDIA_BASE_URL", DEFAULT_BASE_URLS["nvidia"])
        model = os.getenv("NVIDIA_MODEL", DEFAULT_MODELS["nvidia"])
    elif provider == "ollama":
        api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URLS["ollama"])
        model = os.getenv("OLLAMA_MODEL", DEFAULT_MODELS["ollama"])
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URLS["openai"])
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODELS["openai"])
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return LLMConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout=timeout,
        temperature=temperature,
    )
