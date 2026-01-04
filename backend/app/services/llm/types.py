"""
OpenAI-Compatible Type Definitions

Unified message format following OpenAI's Chat Completion API standard.
All LLM adapters must convert their responses to these types.
"""

from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================================
# Message Types (Request)
# ============================================================================

@dataclass
class ChatMessage:
    """Standard chat message format (OpenAI compatible)"""
    role: Literal["system", "user", "assistant"]
    content: str
    name: Optional[str] = None  # Optional speaker name


# ============================================================================
# Streaming Response Types
# ============================================================================

@dataclass
class Delta:
    """Incremental content in streaming response"""
    role: Optional[str] = None
    content: Optional[str] = None


@dataclass
class StreamChoice:
    """Choice object in streaming chunk"""
    index: int
    delta: Delta
    finish_reason: Optional[Literal["stop", "length", "error"]] = None


@dataclass
class ChatCompletionChunk:
    """
    Streaming chunk format (OpenAI SSE compatible)

    Example SSE format:
        data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1234567890,
               "model":"qwen-max","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}
    """
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str = ""
    choices: List[StreamChoice] = field(default_factory=list)

    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format"""
        import json
        data = {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": choice.index,
                    "delta": {
                        k: v for k, v in {
                            "role": choice.delta.role,
                            "content": choice.delta.content
                        }.items() if v is not None
                    },
                    "finish_reason": choice.finish_reason
                }
                for choice in self.choices
            ]
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================================================
# Complete Response Types (Non-streaming)
# ============================================================================

@dataclass
class Usage:
    """Token usage statistics"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatCompletionResponse:
    """Complete chat completion response (non-streaming)"""
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str = ""
    choices: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Usage] = None


# ============================================================================
# Configuration Types
# ============================================================================

@dataclass
class ModelConfig:
    """LLM model configuration"""
    name: str                    # Model identifier (e.g., "qwen3-max")
    adapter_type: str            # Adapter class name (e.g., "qwen", "deepseek")
    api_key: str                 # API authentication key
    base_url: str                # API endpoint URL
    model_id: str                # Actual model name in API (e.g., "qwen-max-latest")
    max_tokens: int = 4000       # Maximum output tokens
    temperature: float = 0.7     # Sampling temperature
    timeout: int = 60            # Request timeout in seconds
    enabled: bool = True         # Whether this model is active
    priority: int = 99           # Lower number = higher priority
    cost_per_1k_tokens: float = 0.0  # Cost in RMB per 1000 tokens

    # TODO: Add rate limiting config
    # rate_limit_rpm: int = 60  # Requests per minute
    # rate_limit_tpm: int = 100000  # Tokens per minute

    # TODO: Add retry config
    # max_retries: int = 3
    # retry_delay: float = 1.0


# ============================================================================
# Health Check Types
# ============================================================================

@dataclass
class HealthStatus:
    """Model health check result"""
    model_name: str
    healthy: bool
    latency: Optional[float] = None  # Response time in seconds
    error: Optional[str] = None
    checked_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "healthy": self.healthy,
            "latency": self.latency,
            "error": self.error,
            "checked_at": self.checked_at.isoformat()
        }


# ============================================================================
# RAG Types
# ============================================================================

@dataclass
class RAGContext:
    """RAG retrieval context with two-stage retrieval details"""
    # Final results (after reranking)
    documents: List[str]         # Retrieved document contents (top-5)
    sources: List[Dict[str, Any]]  # Source metadata (question_id, note_id, etc.)
    scores: List[float]          # Final relevance scores

    # Two-stage retrieval details
    recall_results: Optional[List[Dict[str, Any]]] = None  # Coarse retrieval (top-20)
    recall_method: Optional[str] = None  # "vector+bm25"
    rerank_method: Optional[str] = None  # "bm25_rerank"

    def format_for_prompt(self) -> str:
        """Format retrieved knowledge for LLM prompt"""
        if not self.documents:
            return ""

        context_lines = ["【知识库检索结果】"]
        for i, (doc, source, score) in enumerate(zip(self.documents, self.sources, self.scores), 1):
            # 安全检查：source可能是None
            if source is None:
                source_type = "unknown"
                source_id = ""
            else:
                source_type = source.get("type", "unknown")
                source_id = source.get("id", "")
            context_lines.append(f"\n[{i}] (相关度: {score:.2f}) [{source_type}#{source_id}]")
            context_lines.append(doc)

        return "\n".join(context_lines)
