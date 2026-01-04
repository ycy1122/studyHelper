"""
Chat Service

High-level orchestration service for chatbot conversations.
Coordinates RAG retrieval, context management, and LLM routing.
"""

from typing import AsyncGenerator, Optional, List, Dict
import logging
import time
import uuid

from .llm.router import LLMRouter
from .llm.types import ChatMessage, ChatCompletionChunk
from .context_manager import ContextManager
from .common_rag_service import CommonRAGService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ChatService:
    """
    Chat Service - Main orchestration layer

    Responsibilities:
    - Coordinate RAG retrieval
    - Manage conversation context
    - Route requests to LLM
    - Handle errors and fallbacks
    - Collect metrics

    Example:
        ```python
        chat_service = ChatService(llm_router, context_manager, rag_service)

        async for chunk in chat_service.stream_chat(
            session_id="user-123",
            user_message="What is RAG?",
            use_rag=True
        ):
            print(chunk.choices[0].delta.content)
        ```
    """

    def __init__(
        self,
        llm_router: LLMRouter,
        context_manager: ContextManager,
        rag_service: Optional[CommonRAGService] = None,
    ):
        """
        Initialize chat service.

        Args:
            llm_router: LLM router for model selection and fallback
            context_manager: Context manager for conversation history
            rag_service: RAG service for knowledge retrieval (optional)
        """
        self.llm_router = llm_router
        self.context_manager = context_manager
        self.rag_service = rag_service

        # Service statistics
        self._total_chats = 0
        self._total_tokens = 0
        self._total_cost = 0.0

        logger.info("ChatService initialized")

    # ========================================================================
    # Main Chat Method
    # ========================================================================

    async def stream_chat(
        self,
        session_id: str,
        user_message: str,
        use_rag: bool = True,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        db_session: Optional[Session] = None,
        dev_mode: bool = False,
        enable_search: bool = False,  # 新增：是否启用互联网搜索
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Stream chat completion with RAG and context management.

        Args:
            session_id: Unique session identifier
            user_message: User's input message
            use_rag: Whether to use RAG knowledge retrieval
            model_name: Force specific model (None = auto-select)
            temperature: Sampling temperature
            max_tokens: Max output tokens
            db_session: Database session (required if use_rag=True)
            dev_mode: Developer mode (send debug info)
            enable_search: Enable internet search tool (Qwen only)

        Yields:
            ChatCompletionChunk: Streaming response chunks

        Raises:
            ValueError: If RAG requested but db_session not provided
        """
        chat_id = str(uuid.uuid4())
        start_time = time.time()

        # Performance timing
        timings = {}

        logger.info(
            f"[CHAT-{chat_id[:8]}] session={session_id} "
            f"use_rag={use_rag} model={model_name or 'auto'}"
        )

        try:
            # Step 1: Add user message to context
            step_start = time.time()
            self.context_manager.add_message(
                session_id,
                ChatMessage(role="user", content=user_message),
            )
            timings["add_message"] = time.time() - step_start

            # Step 2: RAG knowledge retrieval (if enabled)
            rag_context = None
            refined_queries = None
            if use_rag:
                if not self.rag_service:
                    logger.warning("RAG requested but service not available")
                elif not db_session:
                    raise ValueError("db_session required when use_rag=True")
                else:
                    # Query rewriting for better retrieval (generate 3 versions)
                    step_start = time.time()
                    refined_queries = await self._refine_query(user_message, session_id)
                    timings["query_rewrite"] = time.time() - step_start

                    step_start = time.time()
                    rag_context = await self._retrieve_knowledge(
                        refined_queries, db_session
                    )
                    timings["rag_retrieval"] = time.time() - step_start

            # Step 3: Build enhanced system prompt (with RAG context if available)
            step_start = time.time()
            self._update_system_prompt(session_id, rag_context)
            timings["update_prompt"] = time.time() - step_start

            # Step 4: Get conversation context
            step_start = time.time()
            messages = self.context_manager.get_context(
                session_id, include_system=True
            )
            timings["get_context"] = time.time() - step_start

            logger.debug(
                f"[CHAT-{chat_id[:8]}] context_messages={len(messages)} "
                f"rag_docs={len(rag_context.documents) if rag_context else 0}"
            )

            # Step 4.5: Skip early debug info (will send complete one at the end)
            # (Removed to avoid incomplete timing data)

            # Step 5: Stream from LLM
            assistant_message_parts = []
            llm_start = time.time()

            async for chunk in self.llm_router.route_chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
                enable_search=enable_search,
            ):
                # Collect assistant response
                if chunk.choices and chunk.choices[0].delta.content:
                    assistant_message_parts.append(chunk.choices[0].delta.content)

                yield chunk

            timings["llm_generation"] = time.time() - llm_start

            # Step 6: Save assistant response to context
            assistant_message = "".join(assistant_message_parts)
            if assistant_message:
                self.context_manager.add_message(
                    session_id,
                    ChatMessage(role="assistant", content=assistant_message),
                )

            # Step 7: Update statistics
            timings["total"] = time.time() - start_time
            self._total_chats += 1

            # Step 7.5: Send updated debug info with complete timings (dev_mode)
            if dev_mode:
                debug_info_final = self._build_debug_info(
                    session_id=session_id,
                    messages=messages + [ChatMessage(role="assistant", content=assistant_message)],
                    rag_context=rag_context,
                    use_rag=use_rag,
                    model_name=model_name,
                    original_query=user_message if use_rag else None,
                    refined_queries=refined_queries if use_rag else None,
                    timings=timings,  # Now includes llm_generation and total!
                )
                # Yield final debug chunk with complete timings
                yield debug_info_final

            # Log detailed performance breakdown
            logger.info(
                f"[CHAT-{chat_id[:8]}] completed in {timings['total']:.2f}s "
                f"response_len={len(assistant_message)}"
            )
            if use_rag:
                logger.info(
                    f"[CHAT-{chat_id[:8]}] Performance breakdown: "
                    f"query_rewrite={timings.get('query_rewrite', 0):.2f}s, "
                    f"rag_retrieval={timings.get('rag_retrieval', 0):.2f}s, "
                    f"llm_generation={timings.get('llm_generation', 0):.2f}s"
                )

        except Exception as e:
            logger.error(f"[CHAT-{chat_id[:8]}] failed: {e}", exc_info=True)
            raise

    async def _refine_query(self, original_query: str, session_id: str) -> List[str]:
        """
        Refine user query into 3 different versions for better RAG retrieval.

        Uses conversation history to generate diverse query variations:
        - Version 1: Expansion (expand abbreviations, add context)
        - Version 2: Keywords (extract key concepts)
        - Version 3: Synonyms (use variations and related terms)

        Args:
            original_query: Original user query
            session_id: Session identifier for context

        Returns:
            List of 3 refined query strings
        """
        # Get recent conversation history (last 2 rounds)
        history = self.context_manager.get_context(session_id, include_system=False)
        recent_history = history[-4:] if len(history) > 4 else history  # Last 2 rounds
        history_text = chr(10).join([f"{msg.role}: {msg.content}" for msg in recent_history]) if recent_history else "无"

        # Build 3 different query refinement prompts
        refine_prompts = [
            # Version 1: Expansion strategy
            f"""将用户的问题改写为更适合检索的形式（扩展版本）。

【规则】
1. 展开所有缩写词（如"LLM"→"大语言模型"，"API"→"应用程序接口"）
2. 补充上下文信息（根据对话历史）
3. 添加相关的完整表述
4. 保持原意，只优化检索效果
5. 只返回改写后的问题，不要其他解释

【对话历史】
{history_text}

【用户问题】
{original_query}

【改写后的问题（扩展版）】""",

            # Version 2: Keyword extraction strategy
            f"""将用户的问题改写为更适合检索的形式（关键词版本）。

【规则】
1. 提取核心关键概念和术语
2. 保留技术词汇和专业名词
3. 去除无关的修饰词
4. 简洁明确，聚焦核心问题
5. 只返回改写后的问题，不要其他解释

【对话历史】
{history_text}

【用户问题】
{original_query}

【改写后的问题（关键词版）】""",

            # Version 3: Synonym/variation strategy
            f"""将用户的问题改写为更适合检索的形式（同义词版本）。

【规则】
1. 使用同义词和相关术语替换原词
2. 用不同的表达方式重新组织问题
3. 保持语义不变但换一种说法
4. 增加检索的多样性
5. 只返回改写后的问题，不要其他解释

【对话历史】
{history_text}

【用户问题】
{original_query}

【改写后的问题（同义词版）】"""
        ]

        refined_queries = []

        try:
            # Generate 3 versions in parallel
            import asyncio

            async def refine_single(prompt: str) -> str:
                """Refine a single query version"""
                refine_messages = [ChatMessage(role="user", content=prompt)]
                refined_parts = []

                async for chunk in self.llm_router.route_chat(
                    messages=refine_messages,
                    temperature=0.3,
                    max_tokens=200,
                ):
                    if chunk.choices and chunk.choices[0].delta.content:
                        refined_parts.append(chunk.choices[0].delta.content)

                return "".join(refined_parts).strip()

            # Run all 3 refinements in parallel
            tasks = [refine_single(prompt) for prompt in refine_prompts]
            refined_queries = await asyncio.gather(*tasks)

            # Validate and filter out empty results
            valid_queries = []
            strategy_names = ["扩展版", "关键词版", "同义词版"]

            for i, query in enumerate(refined_queries):
                if query and len(query) >= 2:
                    valid_queries.append(query)
                    logger.info(f"Query refined ({strategy_names[i]}): '{original_query}' → '{query}'")
                else:
                    # Fallback to original for this version
                    valid_queries.append(original_query)
                    logger.warning(f"Query refinement failed for {strategy_names[i]}, using original")

            return valid_queries

        except Exception as e:
            logger.error(f"Query refinement error: {e}, using original query for all versions")
            return [original_query, original_query, original_query]

    async def _retrieve_knowledge(
        self,
        queries: List[str],
        db_session: Session,
    ):
        """
        Retrieve relevant knowledge using RAG with multiple query versions.

        Args:
            queries: List of refined user queries (3 versions)
            db_session: Database session

        Returns:
            RAGContext with retrieved knowledge (merged from all query versions)
        """
        logger.debug(f"Retrieving knowledge from RAG using {len(queries)} query versions...")

        # Rebuild knowledge base if needed (TODO: optimize this)
        # For now, rebuild on every query to ensure fresh data
        self.rag_service.rebuild_knowledge_base(db_session)

        # Query with each version and merge results
        all_results = []
        for i, query in enumerate(queries):
            logger.debug(f"Querying with version {i+1}: {query}")
            rag_context = self.rag_service.query(
                query_text=query,
                top_k=5,
                use_rerank=True,
            )
            all_results.append(rag_context)

        # Merge results from all 3 query versions
        merged_context = self._merge_rag_results(all_results)

        logger.debug(f"Retrieved {len(merged_context.documents)} knowledge docs (merged from {len(queries)} queries)")

        return merged_context

    def _merge_rag_results(self, rag_contexts: List) -> 'RAGContext':
        """
        Merge RAG results from multiple query versions using RRF.

        Args:
            rag_contexts: List of RAGContext objects from different queries

        Returns:
            Merged RAGContext with top-5 documents
        """
        from .llm.types import RAGContext

        if not rag_contexts:
            return RAGContext(documents=[], sources=[], scores=[])

        if len(rag_contexts) == 1:
            return rag_contexts[0]

        # Use RRF (Reciprocal Rank Fusion) to merge results
        merged_docs = {}

        for query_idx, context in enumerate(rag_contexts):
            for rank, (doc, source, score) in enumerate(
                zip(context.documents, context.sources, context.scores), 1
            ):
                # Use document content as key for deduplication
                doc_key = doc[:100]  # Use first 100 chars as key

                if doc_key not in merged_docs:
                    merged_docs[doc_key] = {
                        "document": doc,
                        "source": source,
                        "original_score": score,
                        "rrf_score": 0.0,
                        "query_ranks": {},
                    }

                # Add RRF score from this query version
                rrf = 1.0 / (rank + 60)  # RRF with k=60
                merged_docs[doc_key]["rrf_score"] += rrf
                merged_docs[doc_key]["query_ranks"][f"query_{query_idx+1}"] = rank

        # Sort by RRF score and take top-5
        sorted_docs = sorted(
            merged_docs.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )[:5]

        # Extract documents, sources, and scores
        documents = [doc["document"] for doc in sorted_docs]
        sources = [doc["source"] for doc in sorted_docs]
        scores = [doc["rrf_score"] for doc in sorted_docs]

        # Preserve recall information from first query version
        recall_results = rag_contexts[0].recall_results if rag_contexts[0].recall_results else None
        recall_method = rag_contexts[0].recall_method if rag_contexts[0].recall_method else None

        return RAGContext(
            documents=documents,
            sources=sources,
            scores=scores,
            recall_results=recall_results,
            recall_method=f"{recall_method} + multi-query(3)" if recall_method else "multi-query(3)",
            rerank_method="rrf_multi_query",
        )

    def _update_system_prompt(self, session_id: str, rag_context=None):
        """
        Update system prompt with RAG context.

        Args:
            session_id: Session identifier
            rag_context: RAG retrieval results (optional)
        """
        # Base system prompt
        system_prompt = """你是一个专业的面试助手，基于知识库回答用户关于面试的问题。

【回答要求】
1. 基于知识库内容回答，确保准确性
2. 如果知识库没有相关信息，基于通用知识回答，并说明"这不在我的知识库中"
3. 回答要结构清晰，使用Markdown格式
4. 对于技术问题，提供代码示例
5. 对于面试题，提供答题思路和关键点
6. 语气专业、友好"""

        # Add RAG context if available
        if rag_context and rag_context.documents:
            rag_section = "\n\n" + rag_context.format_for_prompt()
            system_prompt += rag_section

        self.context_manager.set_system_prompt(session_id, system_prompt)

    def _build_debug_info(
        self,
        session_id: str,
        messages: List[ChatMessage],
        rag_context,
        use_rag: bool,
        model_name: Optional[str],
        original_query: Optional[str] = None,
        refined_queries: Optional[List[str]] = None,
        timings: Optional[Dict[str, float]] = None,
    ) -> ChatCompletionChunk:
        """
        Build debug information chunk for developer mode.

        Args:
            session_id: Session identifier
            messages: Full message list sent to LLM
            rag_context: RAG retrieval context
            use_rag: Whether RAG was used
            model_name: Model name (or auto)
            original_query: Original user query
            refined_queries: List of 3 refined query versions
            timings: Performance timing breakdown

        Returns:
            ChatCompletionChunk with debug metadata
        """
        # Extract system prompt and split into base and RAG parts
        system_prompt_full = messages[0].content if messages and messages[0].role == "system" else ""

        # Split system prompt: base part ends at "【知识库检索结果】"
        base_system_prompt = system_prompt_full
        current_rag_context = None

        if "【知识库检索结果】" in system_prompt_full:
            parts = system_prompt_full.split("【知识库检索结果】", 1)
            base_system_prompt = parts[0].strip()
            current_rag_context = "【知识库检索结果】" + parts[1]

        # Extract conversation history (without system)
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role != "system"
        ]

        # Calculate conversation round (每两条消息是一轮：user + assistant)
        # Note: debug info is sent BEFORE assistant message is added,
        # so we need to add 1 to get the current round number
        conversation_round = (len(history) + 1) // 2

        # Build RAG details with two-stage retrieval info
        rag_details = None
        if use_rag and rag_context and rag_context.documents:
            rag_details = {
                "enabled": True,
                "original_query": original_query,
                "refined_queries": refined_queries or [],
                "query_versions": [
                    {"version": "扩展版", "query": refined_queries[0] if refined_queries and len(refined_queries) > 0 else original_query},
                    {"version": "关键词版", "query": refined_queries[1] if refined_queries and len(refined_queries) > 1 else original_query},
                    {"version": "同义词版", "query": refined_queries[2] if refined_queries and len(refined_queries) > 2 else original_query},
                ],
                # Stage 2: Final results (precision)
                "final_count": len(rag_context.documents),
                "final_documents": [
                    {
                        "content": doc[:200] + "..." if len(doc) > 200 else doc,
                        "source": src,
                        "score": score,
                    }
                    for doc, src, score in zip(
                        rag_context.documents,
                        rag_context.sources,
                        rag_context.scores,
                    )
                ],
                # Stage 1: Recall results (coarse)
                "recall_count": len(rag_context.recall_results) if rag_context.recall_results else 0,
                "recall_documents": rag_context.recall_results or [],
                "recall_method": rag_context.recall_method or "unknown",
                "rerank_method": rag_context.rerank_method or "none",
            }
        else:
            rag_details = {"enabled": False, "final_count": 0, "recall_count": 0, "query_versions": []}

        # Build debug payload
        from .llm.types import StreamChoice, Delta
        import json

        debug_data = {
            "type": "debug",
            "session_id": session_id,
            "model": model_name or "auto",
            "round": conversation_round,  # 当前是第几轮对话
            "context": {
                "base_system_prompt": base_system_prompt,
                "current_rag_context": current_rag_context,
                "history_length": len(history),  # 历史消息数量
                "conversation_rounds": conversation_round,  # 对话轮数
                "history": history,
                "total_messages": len(messages),  # 包含system在内的总消息数
            },
            "rag": rag_details,
            "timings": timings or {},  # 性能计时
        }

        # Return as ChatCompletionChunk with special delta
        return ChatCompletionChunk(
            id="debug",
            model="debug",
            choices=[
                StreamChoice(
                    index=0,
                    delta=Delta(content=json.dumps(debug_data, ensure_ascii=False)),
                )
            ],
        )

    # ========================================================================
    # Session Management
    # ========================================================================

    def clear_session(self, session_id: str):
        """
        Clear conversation history for session.

        Args:
            session_id: Session identifier
        """
        self.context_manager.clear_context(session_id, keep_system=True)
        logger.info(f"Cleared session: {session_id}")

    def delete_session(self, session_id: str):
        """
        Delete entire session.

        Args:
            session_id: Session identifier
        """
        self.context_manager.delete_context(session_id)
        logger.info(f"Deleted session: {session_id}")

    def get_session_history(self, session_id: str) -> List[ChatMessage]:
        """
        Get conversation history for session.

        Args:
            session_id: Session identifier

        Returns:
            List of chat messages (without system prompt)
        """
        return self.context_manager.get_context(
            session_id, include_system=False
        )

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> dict:
        """
        Get service statistics.

        Returns:
            Statistics dictionary
        """
        llm_stats = self.llm_router.get_stats()
        context_stats = self.context_manager.get_global_stats()

        return {
            "total_chats": self._total_chats,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "llm_stats": llm_stats,
            "context_stats": context_stats,
            "rag_enabled": self.rag_service is not None,
        }

    # ========================================================================
    # TODO: Future enhancements
    # ========================================================================

    # TODO: Implement conversation persistence
    # async def save_conversation(self, session_id: str, db: Session):
    #     """Save conversation to database"""
    #     pass

    # TODO: Implement conversation analytics
    # def analyze_conversation(self, session_id: str) -> Dict:
    #     """Analyze conversation quality, topics, etc."""
    #     pass

    # TODO: Implement smart RAG triggering
    # def should_use_rag(self, message: str) -> bool:
    #     """Intelligently decide if RAG is needed"""
    #     # Check if question is knowledge-seeking
    #     # vs. casual conversation
    #     pass

    # TODO: Implement streaming with metadata
    # async def stream_with_metadata(self, ...):
    #     """Stream chunks with additional metadata (sources, confidence, etc.)"""
    #     pass
