"""
Base provider abstraction for SitePilot AI.
Defines standardized result models and the provider interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from src.config import LLMConfig


@dataclass
class ProviderTestResult:
    """Result of a provider connectivity test."""
    success: bool
    message: str
    provider: str
    model: str
    base_url: str
    latency_ms: Optional[float] = None
    sample_response: Optional[str] = None
    error_type: Optional[str] = None
    troubleshooting_tip: Optional[str] = None


@dataclass
class ProviderResponse:
    """Standardized response from an LLM call."""
    content: str
    success: bool
    latency_ms: float = 0.0
    model: str = ""
    provider: str = ""
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = field(default_factory=dict)


class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def test_connection(self) -> ProviderTestResult:
        """Test endpoint reachability and credentials."""
        pass

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> ProviderResponse:
        """Generate text completion from prompt."""
        pass
