"""
LLM Adapters Package

Provider-specific implementations of BaseLLMAdapter.
Each adapter translates provider's API to OpenAI-compatible format.
"""

from .qwen_adapter import QwenAdapter
from .deepseek_adapter import DeepSeekAdapter

# Adapter registry for dynamic loading
ADAPTER_REGISTRY = {
    "qwen": QwenAdapter,
    "alibaba": QwenAdapter,  # Alias
    "deepseek": DeepSeekAdapter,
}

__all__ = [
    "QwenAdapter",
    "DeepSeekAdapter",
    "ADAPTER_REGISTRY",
]
