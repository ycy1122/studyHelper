"""
Base LLM Adapter

Abstract base class that all LLM adapters must implement.
Enforces OpenAI-compatible interface for consistent behavior across providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional
import logging
import time

from .types import (
    ChatMessage,
    ChatCompletionChunk,
    HealthStatus,
    ModelConfig,
)

logger = logging.getLogger(__name__)


class BaseLLMAdapter(ABC):
    """
    Abstract base class for all LLM adapters.

    Each LLM provider (Qwen, DeepSeek, OpenAI, etc.) must implement this interface
    to ensure consistent behavior and interchangeability.

    Enterprise-level features:
    - Standardized error handling
    - Request/response logging
    - Performance monitoring
    - Health checking
    """

    def __init__(self, config: ModelConfig):
        """
        Initialize adapter with model configuration.

        Args:
            config: Model configuration containing API credentials and parameters
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.name}")

        # Performance metrics
        self._total_requests = 0
        self._failed_requests = 0
        self._total_tokens = 0
        self._last_health_check: Optional[HealthStatus] = None

    # ========================================================================
    # Abstract Methods (Must be implemented by subclasses)
    # ========================================================================

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Stream chat completion responses.

        This is the core method that all adapters must implement. It should:
        1. Convert ChatMessage to provider's format
        2. Make streaming API request
        3. Parse provider's streaming response
        4. Convert to ChatCompletionChunk format
        5. Yield chunks one by one

        Args:
            messages: List of chat messages (OpenAI format)
            temperature: Sampling temperature (overrides config if provided)
            max_tokens: Max output tokens (overrides config if provided)

        Yields:
            ChatCompletionChunk: Standardized streaming chunks

        Raises:
            Exception: On API errors, connection errors, etc.
        """
        pass

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """
        Perform health check on this model.

        Should send a minimal request to verify the model is accessible and responsive.

        Returns:
            HealthStatus: Health check result with latency info

        Example implementation:
            ```python
            try:
                start = time.time()
                test_messages = [ChatMessage(role="user", content="Hi")]
                async for chunk in self.stream_chat(test_messages, max_tokens=5):
                    break  # Just need first chunk
                latency = time.time() - start
                return HealthStatus(
                    model_name=self.config.name,
                    healthy=True,
                    latency=latency
                )
            except Exception as e:
                return HealthStatus(
                    model_name=self.config.name,
                    healthy=False,
                    error=str(e)
                )
            ```
        """
        pass

    # ========================================================================
    # Common Properties
    # ========================================================================

    @property
    def model_name(self) -> str:
        """Model identifier (e.g., 'qwen3-max')"""
        return self.config.name

    @property
    def model_id(self) -> str:
        """Actual model ID used in API (e.g., 'qwen-max-latest')"""
        return self.config.model_id

    @property
    def is_enabled(self) -> bool:
        """Whether this model is currently enabled"""
        return self.config.enabled

    @property
    def priority(self) -> int:
        """Model priority (lower = higher priority)"""
        return self.config.priority

    @property
    def cost_per_1k_tokens(self) -> float:
        """Cost in RMB per 1000 tokens"""
        return self.config.cost_per_1k_tokens

    # ========================================================================
    # Common Helper Methods
    # ========================================================================

    def calculate_cost(self, total_tokens: int) -> float:
        """
        Calculate cost for given token count.

        Args:
            total_tokens: Total tokens (prompt + completion)

        Returns:
            Cost in RMB
        """
        return (total_tokens / 1000.0) * self.cost_per_1k_tokens

    def record_request(self, success: bool, tokens: int = 0):
        """
        Record request metrics.

        Args:
            success: Whether request succeeded
            tokens: Total tokens used
        """
        self._total_requests += 1
        if not success:
            self._failed_requests += 1
        self._total_tokens += tokens

    def get_metrics(self) -> dict:
        """
        Get adapter performance metrics.

        Returns:
            Dictionary of metrics
        """
        success_rate = (
            (self._total_requests - self._failed_requests) / self._total_requests
            if self._total_requests > 0
            else 0.0
        )

        return {
            "model_name": self.model_name,
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "success_rate": success_rate,
            "total_tokens": self._total_tokens,
            "total_cost": self.calculate_cost(self._total_tokens),
            "last_health_check": (
                self._last_health_check.to_dict()
                if self._last_health_check
                else None
            ),
        }

    # ========================================================================
    # Logging Helpers
    # ========================================================================

    def log_request(self, messages: List[ChatMessage], **kwargs):
        """Log outgoing request"""
        self.logger.info(
            f"[REQUEST] model={self.model_name} messages={len(messages)} "
            f"params={kwargs}"
        )

    def log_response(self, tokens: int, latency: float, cost: float):
        """Log completed response"""
        self.logger.info(
            f"[RESPONSE] model={self.model_name} tokens={tokens} "
            f"latency={latency:.2f}s cost=¥{cost:.4f}"
        )

    def log_error(self, error: Exception):
        """Log error"""
        self.logger.error(
            f"[ERROR] model={self.model_name} error={type(error).__name__}: {error}"
        )

    # ========================================================================
    # TODO: Future enterprise features
    # ========================================================================

    # TODO: Implement rate limiting
    # async def check_rate_limit(self) -> bool:
    #     """Check if request would exceed rate limits"""
    #     pass

    # TODO: Implement request retry with exponential backoff
    # async def retry_request(self, func, max_retries=3):
    #     """Retry failed requests with exponential backoff"""
    #     pass

    # TODO: Implement circuit breaker pattern
    # def is_circuit_open(self) -> bool:
    #     """Check if circuit breaker is open (too many failures)"""
    #     pass
