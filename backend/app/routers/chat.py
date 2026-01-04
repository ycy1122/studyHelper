"""
Chat API

Enterprise-grade chatbot API with streaming responses.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import json
import logging

from app.database import get_db
from app.services.llm.types import ChatMessage
from app.services.llm.config_loader import get_config_loader
from app.services.llm.router import LLMRouter
from app.services.llm.adapters import ADAPTER_REGISTRY
from app.services.context_manager import ContextManager
from app.services.chat_service import ChatService
from app.services.common_rag_service import CommonRAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chatbot"])

# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Chat request payload"""
    session_id: str
    message: str
    use_rag: bool = True
    model: Optional[str] = None  # Force specific model (None = auto)
    dev_mode: bool = False  # Enable developer mode (debug info)
    enable_search: bool = False  # Enable internet search (Qwen only)


class SessionHistoryResponse(BaseModel):
    """Chat session history response"""
    session_id: str
    messages: List[dict]


# ============================================================================
# Global Service Instances
# (Initialized on first request)
# ============================================================================

_llm_router: Optional[LLMRouter] = None
_context_manager: Optional[ContextManager] = None
_rag_service: Optional[CommonRAGService] = None
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """
    Get or initialize chat service (singleton pattern).

    Returns:
        ChatService instance
    """
    global _llm_router, _context_manager, _rag_service, _chat_service

    if _chat_service is not None:
        return _chat_service

    logger.info("Initializing chat services...")

    try:
        # Load configuration
        config_loader = get_config_loader()
        model_configs = config_loader.load_model_configs()
        router_config = config_loader.get_router_config()
        context_config = config_loader.get_context_config()
        rag_config = config_loader.get_rag_config()

        logger.info(f"Loaded {len(model_configs)} model configurations")

        # Initialize adapters
        adapters = []
        for model_config in model_configs:
            adapter_class = ADAPTER_REGISTRY.get(model_config.adapter_type)

            if adapter_class is None:
                logger.error(
                    f"Unknown adapter type: {model_config.adapter_type} "
                    f"for model {model_config.name}"
                )
                continue

            adapter = adapter_class(model_config)
            adapters.append(adapter)

            logger.info(
                f"Initialized adapter: {model_config.name} "
                f"({model_config.adapter_type})"
            )

        if not adapters:
            raise ValueError("No valid adapters configured")

        # Initialize LLM router
        _llm_router = LLMRouter(
            adapters=adapters,
            fallback_enabled=router_config.get("fallback_enabled", True),
            health_check_interval=router_config.get("health_check_interval", 300),
        )

        # Initialize context manager
        _context_manager = ContextManager(
            default_max_history=context_config.get("max_history", 10),
            default_max_tokens=context_config.get("max_tokens", 8000),
            default_system_prompt=context_config.get("system_prompt"),
        )

        # Initialize RAG service (if enabled)
        if rag_config.get("enabled", True):
            _rag_service = CommonRAGService()
            logger.info("RAG service initialized")
        else:
            logger.info("RAG service disabled")

        # Initialize chat service
        _chat_service = ChatService(
            llm_router=_llm_router,
            context_manager=_context_manager,
            rag_service=_rag_service,
        )

        logger.info("Chat service initialization complete")

        return _chat_service

    except Exception as e:
        logger.error(f"Failed to initialize chat service: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat service initialization failed: {str(e)}",
        )


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Stream chat completion (Server-Sent Events).

    Args:
        request: Chat request
        db: Database session

    Returns:
        StreamingResponse with SSE format
    """
    chat_service = get_chat_service()

    async def event_generator():
        """Generate SSE events"""
        try:
            # Stream from chat service
            async for chunk in chat_service.stream_chat(
                session_id=request.session_id,
                user_message=request.message,
                use_rag=request.use_rag,
                model_name=request.model,
                db_session=db if request.use_rag else None,
                dev_mode=request.dev_mode,
                enable_search=request.enable_search,
            ):
                # Convert to SSE format
                sse_data = chunk.to_sse_format()
                yield sse_data

            # Send done signal
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)

            # Send error event
            error_data = {
                "type": "error",
                "error": str(e),
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
def get_session_history(session_id: str):
    """
    Get conversation history for session.

    Args:
        session_id: Session identifier

    Returns:
        List of messages
    """
    chat_service = get_chat_service()

    messages = chat_service.get_session_history(session_id)

    # Convert to dict format
    message_dicts = [
        {
            "role": msg.role,
            "content": msg.content,
        }
        for msg in messages
    ]

    return SessionHistoryResponse(
        session_id=session_id,
        messages=message_dicts,
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """
    Delete chat session.

    Args:
        session_id: Session identifier
    """
    chat_service = get_chat_service()
    chat_service.delete_session(session_id)

    return {"message": "Session deleted successfully"}


@router.post("/sessions/{session_id}/clear")
def clear_session(session_id: str):
    """
    Clear chat history for session (keep session).

    Args:
        session_id: Session identifier
    """
    chat_service = get_chat_service()
    chat_service.clear_session(session_id)

    return {"message": "Session cleared successfully"}


@router.get("/models")
def list_models():
    """
    List available models with health status.

    Returns:
        List of model info
    """
    chat_service = get_chat_service()
    models = chat_service.llm_router.list_models()

    return {"models": models}


@router.get("/stats")
def get_stats():
    """
    Get chat service statistics.

    Returns:
        Statistics dictionary
    """
    chat_service = get_chat_service()
    stats = chat_service.get_stats()

    return stats


@router.post("/health-check")
async def health_check_models():
    """
    Perform health check on all models.

    Returns:
        Health status for all models
    """
    chat_service = get_chat_service()
    health_status = await chat_service.llm_router.check_all_health(force=True)

    return {
        "health_status": {
            name: status.to_dict() for name, status in health_status.items()
        }
    }


# ============================================================================
# TODO: Future endpoints
# ============================================================================

# TODO: POST /chat/sessions - Create new session with initial config
# TODO: GET /chat/sessions - List all sessions
# TODO: PUT /chat/sessions/{session_id}/config - Update session config
# TODO: POST /chat/export - Export conversation to file
# TODO: GET /chat/metrics - Detailed metrics and analytics
