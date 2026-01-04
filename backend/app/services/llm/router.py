"""
LLM Router

Intelligent routing layer with automatic fallback and health monitoring.
Manages multiple LLM adapters and ensures high availability.
"""

from typing import AsyncGenerator, List, Optional, Dict
import logging
from datetime import datetime, timedelta

from .base import BaseLLMAdapter
from .types import ChatMessage, ChatCompletionChunk, HealthStatus

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    LLM Router with automatic fallback.

    Features:
    - Model selection by priority
    - Automatic fallback on failure
    - Health monitoring
    - Manual model switching
    - Metrics collection

    Example usage:
        ```python
        router = LLMRouter(adapters=[qwen_adapter, deepseek_adapter])

        async for chunk in router.route_chat(messages):
            print(chunk.choices[0].delta.content)
        ```
    """

    def __init__(
        self,
        adapters: List[BaseLLMAdapter],
        fallback_enabled: bool = True,
        health_check_interval: int = 300,  # 5 minutes
    ):
        """
        Initialize router with adapters.

        Args:
            adapters: List of LLM adapters (should be sorted by priority)
            fallback_enabled: Whether to enable automatic fallback
            health_check_interval: Seconds between health checks
        """
        # Sort adapters by priority (lower number = higher priority)
        self.adapters = sorted(adapters, key=lambda a: a.priority)
        self.fallback_enabled = fallback_enabled
        self.health_check_interval = health_check_interval

        # Health status cache
        self._health_cache: Dict[str, HealthStatus] = {}
        self._last_health_check: Optional[datetime] = None

        # Statistics
        self._fallback_count = 0
        self._model_usage = {adapter.model_name: 0 for adapter in adapters}

        logger.info(
            f"LLMRouter initialized with {len(adapters)} adapters: "
            f"{[a.model_name for a in adapters]}"
        )

    # ========================================================================
    # Main Routing Method
    # ========================================================================

    async def route_chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,  # Force specific model
        enable_search: bool = False,  # 新增：是否启用互联网搜索
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Route chat request to available model with automatic fallback.

        Args:
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            model_name: Force specific model (skip routing)
            enable_search: Enable internet search tool (Qwen only)

        Yields:
            ChatCompletionChunk: Streaming response

        Raises:
            Exception: If all models fail
        """
        # If specific model requested, use it
        if model_name:
            adapter = self._get_adapter_by_name(model_name)
            if adapter:
                async for chunk in self._try_adapter(
                    adapter, messages, temperature, max_tokens, enable_search
                ):
                    yield chunk
                return
            else:
                raise ValueError(f"Model '{model_name}' not found")

        # Try adapters in priority order
        errors = []

        for adapter in self._get_enabled_adapters():
            try:
                logger.info(f"Routing request to {adapter.model_name}")

                async for chunk in self._try_adapter(
                    adapter, messages, temperature, max_tokens, enable_search
                ):
                    yield chunk

                # Success - record usage
                self._model_usage[adapter.model_name] += 1
                return

            except Exception as e:
                error_msg = f"{adapter.model_name} failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

                # Mark as unhealthy
                self._health_cache[adapter.model_name] = HealthStatus(
                    model_name=adapter.model_name,
                    healthy=False,
                    error=str(e),
                )

                # Continue to fallback if enabled
                if self.fallback_enabled and adapter != self.adapters[-1]:
                    self._fallback_count += 1
                    logger.warning(
                        f"Falling back to next model ({self._fallback_count} total fallbacks)"
                    )
                    continue
                else:
                    raise

        # All models failed
        raise Exception(
            f"All {len(self.adapters)} models failed. Errors: {'; '.join(errors)}"
        )

    async def _try_adapter(
        self,
        adapter: BaseLLMAdapter,
        messages: List[ChatMessage],
        temperature: Optional[float],
        max_tokens: Optional[int],
        enable_search: bool = False,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Try streaming from an adapter.

        Args:
            adapter: LLM adapter
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            enable_search: Enable internet search (Qwen only)

        Yields:
            ChatCompletionChunk: Streaming response
        """
        # Pass enable_search only to Qwen adapters
        from .adapters.qwen_adapter import QwenAdapter
        if isinstance(adapter, QwenAdapter):
            async for chunk in adapter.stream_chat(messages, temperature, max_tokens, enable_search):
                yield chunk
        else:
            async for chunk in adapter.stream_chat(messages, temperature, max_tokens):
                yield chunk

    # ========================================================================
    # Health Monitoring
    # ========================================================================

    async def check_all_health(self, force: bool = False) -> Dict[str, HealthStatus]:
        """
        Check health of all adapters.

        Args:
            force: Force check even if cache is fresh

        Returns:
            Dictionary of health statuses by model name
        """
        # Check if cache is still valid
        if (
            not force
            and self._last_health_check
            and (datetime.now() - self._last_health_check).total_seconds()
            < self.health_check_interval
        ):
            logger.debug("Using cached health status")
            return self._health_cache

        logger.info("Performing health check on all models")

        for adapter in self.adapters:
            try:
                status = await adapter.health_check()
                self._health_cache[adapter.model_name] = status

                if status.healthy:
                    logger.info(
                        f"{adapter.model_name}: Healthy (latency: {status.latency:.2f}s)"
                    )
                else:
                    logger.warning(f"{adapter.model_name}: Unhealthy - {status.error}")

            except Exception as e:
                logger.error(f"Health check failed for {adapter.model_name}: {e}")
                self._health_cache[adapter.model_name] = HealthStatus(
                    model_name=adapter.model_name,
                    healthy=False,
                    error=str(e),
                )

        self._last_health_check = datetime.now()
        return self._health_cache

    def get_healthy_models(self) -> List[str]:
        """Get list of healthy model names"""
        return [
            name
            for name, status in self._health_cache.items()
            if status.healthy
        ]

    # ========================================================================
    # Model Management
    # ========================================================================

    def _get_enabled_adapters(self) -> List[BaseLLMAdapter]:
        """Get list of enabled adapters"""
        return [adapter for adapter in self.adapters if adapter.is_enabled]

    def _get_adapter_by_name(self, model_name: str) -> Optional[BaseLLMAdapter]:
        """Get adapter by model name"""
        for adapter in self.adapters:
            if adapter.model_name == model_name:
                return adapter
        return None

    def get_primary_model(self) -> Optional[BaseLLMAdapter]:
        """Get primary (highest priority) model"""
        enabled = self._get_enabled_adapters()
        return enabled[0] if enabled else None

    def list_models(self) -> List[Dict[str, any]]:
        """
        List all models with their status.

        Returns:
            List of model info dictionaries
        """
        models = []
        for adapter in self.adapters:
            health = self._health_cache.get(adapter.model_name)

            models.append(
                {
                    "name": adapter.model_name,
                    "model_id": adapter.model_id,
                    "enabled": adapter.is_enabled,
                    "priority": adapter.priority,
                    "healthy": health.healthy if health else None,
                    "latency": health.latency if health else None,
                    "usage_count": self._model_usage.get(adapter.model_name, 0),
                }
            )

        return models

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> Dict[str, any]:
        """
        Get router statistics.

        Returns:
            Dictionary of statistics
        """
        total_requests = sum(self._model_usage.values())

        return {
            "total_requests": total_requests,
            "fallback_count": self._fallback_count,
            "fallback_rate": (
                self._fallback_count / total_requests if total_requests > 0 else 0
            ),
            "model_usage": self._model_usage,
            "healthy_models": len(self.get_healthy_models()),
            "total_models": len(self.adapters),
            "last_health_check": (
                self._last_health_check.isoformat()
                if self._last_health_check
                else None
            ),
        }

    # ========================================================================
    # Resource Management
    # ========================================================================

    async def close_all(self):
        """Close all adapter connections"""
        logger.info("Closing all adapter connections")
        for adapter in self.adapters:
            try:
                await adapter.close()
            except Exception as e:
                logger.error(f"Error closing {adapter.model_name}: {e}")

    # ========================================================================
    # TODO: Future enterprise features
    # ========================================================================

    # TODO: Implement circuit breaker pattern
    # - Track consecutive failures per model
    # - Temporarily disable model after N failures
    # - Auto-recover after timeout period
    #
    # def _should_skip_model(self, adapter: BaseLLMAdapter) -> bool:
    #     """Check if model should be skipped due to circuit breaker"""
    #     pass

    # TODO: Implement load balancing
    # - Distribute load across healthy models
    # - Consider latency and cost in routing decisions
    #
    # def _select_optimal_model(self) -> BaseLLMAdapter:
    #     """Select model based on load balancing strategy"""
    #     pass

    # TODO: Implement intelligent retry with exponential backoff
    # async def _retry_with_backoff(self, adapter, messages, attempts=3):
    #     """Retry failed requests with exponential backoff"""
    #     pass
