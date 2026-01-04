"""
Context Manager

Manages conversation history and context window for chat sessions.
Handles token counting, sliding window, and context persistence.
"""

from typing import List, Optional, Dict
import logging
from dataclasses import dataclass, field
from datetime import datetime

from .llm.types import ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Conversation context container"""

    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    system_prompt: Optional[str] = None
    max_history: int = 10  # Maximum rounds of conversation
    max_tokens: int = 8000  # Maximum tokens in context
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def update_timestamp(self):
        """Update last modified time"""
        self.updated_at = datetime.now()


class ContextManager:
    """
    Conversation Context Manager

    Features:
    - Sliding window context management
    - Token-based truncation
    - Multiple session support
    - Memory-based storage (can be extended to Redis/DB)

    Example:
        ```python
        manager = ContextManager()

        # Add messages
        manager.add_message(session_id, ChatMessage(role="user", content="Hello"))
        manager.add_message(session_id, ChatMessage(role="assistant", content="Hi!"))

        # Get context for LLM
        messages = manager.get_context(session_id)
        ```
    """

    def __init__(
        self,
        default_max_history: int = 10,
        default_max_tokens: int = 8000,
        default_system_prompt: Optional[str] = None,
    ):
        """
        Initialize context manager.

        Args:
            default_max_history: Default max conversation rounds
            default_max_tokens: Default max tokens in context
            default_system_prompt: Default system prompt
        """
        self.default_max_history = default_max_history
        self.default_max_tokens = default_max_tokens
        self.default_system_prompt = default_system_prompt

        # In-memory storage {session_id: ConversationContext}
        self._contexts: Dict[str, ConversationContext] = {}

        logger.info("ContextManager initialized")

    # ========================================================================
    # Core Methods
    # ========================================================================

    def get_or_create_context(self, session_id: str) -> ConversationContext:
        """
        Get existing context or create new one.

        Args:
            session_id: Session identifier

        Returns:
            ConversationContext
        """
        if session_id not in self._contexts:
            self._contexts[session_id] = ConversationContext(
                session_id=session_id,
                system_prompt=self.default_system_prompt,
                max_history=self.default_max_history,
                max_tokens=self.default_max_tokens,
            )
            logger.info(f"Created new context for session: {session_id}")

        return self._contexts[session_id]

    def add_message(
        self,
        session_id: str,
        message: ChatMessage,
        auto_truncate: bool = True,
    ):
        """
        Add message to conversation history.

        Args:
            session_id: Session identifier
            message: Chat message to add
            auto_truncate: Whether to auto-truncate if exceeds limits
        """
        context = self.get_or_create_context(session_id)

        # Add message
        context.messages.append(message)
        context.update_timestamp()

        logger.debug(
            f"Added {message.role} message to {session_id} "
            f"(total: {len(context.messages)} messages)"
        )

        # Auto-truncate if needed
        if auto_truncate:
            self._truncate_context(context)

    def get_context(
        self,
        session_id: str,
        include_system: bool = True,
    ) -> List[ChatMessage]:
        """
        Get conversation context for LLM.

        Args:
            session_id: Session identifier
            include_system: Whether to prepend system prompt

        Returns:
            List of chat messages
        """
        context = self.get_or_create_context(session_id)

        messages = []

        # Add system prompt if requested
        if include_system and context.system_prompt:
            messages.append(
                ChatMessage(role="system", content=context.system_prompt)
            )

        # Add conversation history
        messages.extend(context.messages)

        return messages

    def set_system_prompt(self, session_id: str, prompt: str):
        """
        Set system prompt for session.

        Args:
            session_id: Session identifier
            prompt: System prompt text
        """
        context = self.get_or_create_context(session_id)
        context.system_prompt = prompt
        context.update_timestamp()

        logger.info(f"Updated system prompt for {session_id}")

    def clear_context(self, session_id: str, keep_system: bool = True):
        """
        Clear conversation history.

        Args:
            session_id: Session identifier
            keep_system: Whether to keep system prompt
        """
        if session_id in self._contexts:
            context = self._contexts[session_id]
            context.messages.clear()
            context.update_timestamp()

            if not keep_system:
                context.system_prompt = None

            logger.info(f"Cleared context for {session_id}")

    def delete_context(self, session_id: str):
        """
        Delete entire context for session.

        Args:
            session_id: Session identifier
        """
        if session_id in self._contexts:
            del self._contexts[session_id]
            logger.info(f"Deleted context for {session_id}")

    # ========================================================================
    # Context Truncation
    # ========================================================================

    def _truncate_context(self, context: ConversationContext):
        """
        Truncate context if it exceeds limits.

        Strategies:
        1. Keep only last N rounds of conversation (max_history)
        2. Ensure total tokens < max_tokens

        Args:
            context: Conversation context to truncate
        """
        original_count = len(context.messages)

        # Strategy 1: Limit by message count (rounds)
        # Each round = user + assistant pair
        max_messages = context.max_history * 2

        if len(context.messages) > max_messages:
            # Keep the most recent messages
            context.messages = context.messages[-max_messages:]
            logger.debug(
                f"Truncated {context.session_id} by message count: "
                f"{original_count} -> {len(context.messages)}"
            )

        # Strategy 2: Limit by token count
        # TODO: Implement accurate token counting
        # For now, use character count as rough approximation
        # 1 token ≈ 2 characters (Chinese) or 4 characters (English)

        total_chars = sum(len(msg.content) for msg in context.messages)
        estimated_tokens = total_chars / 2  # Conservative estimate

        if estimated_tokens > context.max_tokens:
            # Remove oldest messages until within limit
            while (
                context.messages
                and sum(len(msg.content) for msg in context.messages) / 2
                > context.max_tokens
            ):
                # Remove in pairs to maintain conversation flow
                if len(context.messages) >= 2:
                    context.messages.pop(0)
                    context.messages.pop(0)
                else:
                    context.messages.pop(0)

            logger.debug(
                f"Truncated {context.session_id} by token count: "
                f"{original_count} -> {len(context.messages)}"
            )

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_context_stats(self, session_id: str) -> Dict:
        """
        Get statistics for a context.

        Args:
            session_id: Session identifier

        Returns:
            Statistics dictionary
        """
        if session_id not in self._contexts:
            return {"exists": False}

        context = self._contexts[session_id]
        total_chars = sum(len(msg.content) for msg in context.messages)

        return {
            "exists": True,
            "session_id": session_id,
            "message_count": len(context.messages),
            "total_chars": total_chars,
            "estimated_tokens": total_chars / 2,
            "has_system_prompt": context.system_prompt is not None,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat(),
        }

    def list_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self._contexts.keys())

    def get_global_stats(self) -> Dict:
        """Get global statistics"""
        return {
            "total_sessions": len(self._contexts),
            "sessions": self.list_sessions(),
        }

    # ========================================================================
    # TODO: Future enhancements
    # ========================================================================

    # TODO: Implement persistence (Redis/Database)
    # async def save_to_db(self, session_id: str, db: Session):
    #     """Save context to database"""
    #     pass

    # TODO: Implement accurate token counting
    # def _count_tokens(self, messages: List[ChatMessage]) -> int:
    #     """Count actual tokens using tokenizer"""
    #     # Use tiktoken or transformers tokenizer
    #     pass

    # TODO: Implement context compression
    # def compress_context(self, session_id: str):
    #     """Compress old messages using summarization"""
    #     pass

    # TODO: Implement session expiry
    # def cleanup_expired_sessions(self, max_age_hours: int = 24):
    #     """Remove sessions older than max_age"""
    #     pass
