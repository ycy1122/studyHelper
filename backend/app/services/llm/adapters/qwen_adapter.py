"""
Qwen (Alibaba Tongyi Qianwen) Adapter

Converts Qwen API to OpenAI-compatible format.
API Documentation: https://help.aliyun.com/zh/dashscope/
"""

from typing import AsyncGenerator, List, Optional
import httpx
import json
import time
import uuid

from ..base import BaseLLMAdapter
from ..types import (
    ChatMessage,
    ChatCompletionChunk,
    HealthStatus,
    StreamChoice,
    Delta,
    ModelConfig,
)


class QwenAdapter(BaseLLMAdapter):
    """
    Alibaba Qwen LLM Adapter

    Supports models:
    - qwen-max-latest (Qwen3-Max)
    - qwen-plus-latest
    - qwen-turbo-latest
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        # Initialize HTTP client with timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enable_search: bool = False,  # 新增：是否启用互联网搜索
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Stream chat completion from Qwen API.

        Qwen uses OpenAI-compatible API format, so minimal conversion needed.
        """
        # Use config values if not overridden
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        # Convert messages to Qwen format (same as OpenAI)
        qwen_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        # Build request payload
        payload = {
            "model": self.config.model_id,
            "messages": qwen_messages,
            "temperature": temp,
            "max_tokens": max_tok,
            "stream": True,
            "stream_options": {"include_usage": True},  # Get token usage in stream
        }

        # Add internet search tool if enabled
        if enable_search:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "internet_search",
                        "description": "通过搜索引擎获取最新的互联网信息。当需要查询实时信息、最新新闻、当前事件时使用此工具。",
                        "parameters": {}
                    }
                }
            ]

        # Log request
        self.log_request(messages, temperature=temp, max_tokens=max_tok)

        request_id = str(uuid.uuid4())
        start_time = time.time()
        total_tokens = 0

        try:
            # Make streaming request
            url = f"{self.config.base_url}/chat/completions"
            async with self.client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise Exception(
                        f"Qwen API error: {response.status_code} - {error_text.decode()}"
                    )

                # Parse SSE stream
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    # Remove "data: " prefix
                    if line.startswith("data: "):
                        line = line[6:]

                    # Skip [DONE] signal
                    if line == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(line)
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to parse chunk: {line}")
                        continue

                    # Extract delta content
                    if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                        choice = chunk_data["choices"][0]
                        delta_data = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")

                        # Convert to OpenAI format
                        delta = Delta(
                            role=delta_data.get("role"),
                            content=delta_data.get("content"),
                        )

                        stream_choice = StreamChoice(
                            index=0, delta=delta, finish_reason=finish_reason
                        )

                        chunk = ChatCompletionChunk(
                            id=request_id,
                            model=self.config.name,
                            choices=[stream_choice],
                        )

                        yield chunk

                    # Extract usage info (in final chunk)
                    usage = chunk_data.get("usage")
                    if usage and isinstance(usage, dict):
                        total_tokens = usage.get("total_tokens", 0)

            # Record success
            latency = time.time() - start_time
            cost = self.calculate_cost(total_tokens)
            self.record_request(success=True, tokens=total_tokens)
            self.log_response(tokens=total_tokens, latency=latency, cost=cost)

        except Exception as e:
            self.record_request(success=False)
            self.log_error(e)
            raise

    async def health_check(self) -> HealthStatus:
        """
        Perform health check on Qwen model.

        Sends minimal request to verify accessibility.
        """
        try:
            start = time.time()

            # Send simple test message
            test_messages = [ChatMessage(role="user", content="Hi")]

            # Just need first chunk to verify
            async for chunk in self.stream_chat(test_messages, max_tokens=5):
                break

            latency = time.time() - start

            status = HealthStatus(
                model_name=self.config.name, healthy=True, latency=latency
            )

        except Exception as e:
            status = HealthStatus(
                model_name=self.config.name,
                healthy=False,
                error=str(e),
            )

        self._last_health_check = status
        return status

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()
