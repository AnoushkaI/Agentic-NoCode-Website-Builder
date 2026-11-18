"""
OpenAI-compatible client adapter for SitePilot AI.
Supports NVIDIA NIM, Ollama, and OpenAI with uniform error handling and diagnostics.
"""

import time
from typing import Optional
from openai import (
    OpenAI,
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    APIStatusError,
)
from src.config import LLMConfig
from src.providers.base import BaseProvider, ProviderResponse, ProviderTestResult


class OpenAICompatibleProvider(BaseProvider):
    """
    Adapter for any OpenAI-compatible API endpoint (NVIDIA NIM, Ollama, OpenAI).
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        # For Ollama, if api_key is empty, provide a dummy token as required by OpenAI SDK
        effective_key = self.config.api_key or "ollama-dummy-key"
        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=effective_key,
            timeout=self.config.timeout,
        )

    def _get_troubleshooting_tip(self, error_type: str) -> str:
        """Provide contextual guidance for common connection failures."""
        if self.config.provider == "nvidia":
            if error_type == "AuthenticationError":
                return (
                    "Invalid NVIDIA API key. Obtain a key from https://build.nvidia.com/ "
                    "and set NVIDIA_API_KEY in your .env file."
                )
            elif error_type == "APIConnectionError":
                return (
                    "Could not reach NVIDIA NIM endpoint. Check your internet connection "
                    "and verify NVIDIA_BASE_URL (default: https://integrate.api.nvidia.com/v1)."
                )
            return "Verify that the model exists in NVIDIA NIM catalog and that your account has active credits."

        elif self.config.provider == "ollama":
            if error_type == "APIConnectionError":
                return (
                    f"Ollama server not reachable at {self.config.base_url}. "
                    "Ensure Ollama is running (`ollama serve`) and accessible locally."
                )
            elif error_type == "NotFoundError" or "model" in error_type.lower():
                return (
                    f"Model '{self.config.model}' may not be pulled in Ollama. "
                    f"Run `ollama pull {self.config.model}` in your terminal."
                )
            return "Ensure local Ollama service is active."

        elif self.config.provider == "openai":
            if error_type == "AuthenticationError":
                return (
                    "Invalid OpenAI API key. Check OPENAI_API_KEY in your .env file "
                    "or get one from https://platform.openai.com/api-keys."
                )
            elif error_type == "RateLimitError":
                return "OpenAI rate limit or quota exceeded. Check your plan and billing details."
            return "Check your OpenAI account balance and endpoint settings."

        return "Check provider settings and network connectivity."

    def test_connection(self) -> ProviderTestResult:
        """
        Verify connectivity and credentials with a minimal ping query.
        Does not raise exceptions; returns structured diagnostic result.
        """
        # Pre-check credentials for cloud providers
        if self.config.provider in ("nvidia", "openai") and not self.config.is_configured:
            key_name = "NVIDIA_API_KEY" if self.config.provider == "nvidia" else "OPENAI_API_KEY"
            return ProviderTestResult(
                success=False,
                message=f"Missing or placeholder {key_name}.",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                error_type="MissingCredentials",
                troubleshooting_tip=(
                    f"Please add a valid {key_name} to your .env file or environment variables. "
                    "See .env.example for template."
                ),
            )

        start_time = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "Ping: reply with 'pong'"}],
                max_tokens=15,
                temperature=0.0,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            content = (response.choices[0].message.content or "").strip()

            return ProviderTestResult(
                success=True,
                message=f"Connection successful ({elapsed_ms:.1f}ms).",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                latency_ms=elapsed_ms,
                sample_response=content,
            )

        except AuthenticationError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderTestResult(
                success=False,
                message=f"Authentication failed: {str(e)}",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                latency_ms=elapsed_ms,
                error_type="AuthenticationError",
                troubleshooting_tip=self._get_troubleshooting_tip("AuthenticationError"),
            )

        except APIConnectionError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderTestResult(
                success=False,
                message=f"Endpoint connection failed: {str(e)}",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                latency_ms=elapsed_ms,
                error_type="APIConnectionError",
                troubleshooting_tip=self._get_troubleshooting_tip("APIConnectionError"),
            )

        except RateLimitError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderTestResult(
                success=False,
                message=f"Rate limit / quota exceeded: {str(e)}",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                latency_ms=elapsed_ms,
                error_type="RateLimitError",
                troubleshooting_tip=self._get_troubleshooting_tip("RateLimitError"),
            )

        except APITimeoutError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderTestResult(
                success=False,
                message=f"Request timed out after {self.config.timeout}s: {str(e)}",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                latency_ms=elapsed_ms,
                error_type="APITimeoutError",
                troubleshooting_tip="Endpoint took too long to respond. You can increase LLM_TIMEOUT in .env.",
            )

        except APIStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderTestResult(
                success=False,
                message=f"API returned HTTP error {e.status_code}: {str(e)}",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                latency_ms=elapsed_ms,
                error_type="APIStatusError",
                troubleshooting_tip=self._get_troubleshooting_tip(str(e)),
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderTestResult(
                success=False,
                message=f"Unexpected error: {str(e)}",
                provider=self.config.provider,
                model=self.config.model,
                base_url=self.config.base_url,
                latency_ms=elapsed_ms,
                error_type=type(e).__name__,
                troubleshooting_tip=self._get_troubleshooting_tip(type(e).__name__),
            )

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> ProviderResponse:
        """
        Send a chat completion request.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        temp = temperature if temperature is not None else self.config.temperature
        start_time = time.perf_counter()

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temp,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            content = (response.choices[0].message.content or "").strip()
            return ProviderResponse(
                content=content,
                success=True,
                latency_ms=elapsed_ms,
                model=self.config.model,
                provider=self.config.provider,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ProviderResponse(
                content="",
                success=False,
                latency_ms=elapsed_ms,
                model=self.config.model,
                provider=self.config.provider,
                error=str(e),
            )
