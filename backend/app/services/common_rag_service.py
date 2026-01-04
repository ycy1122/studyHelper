"""
Common RAG Service

Enterprise-grade knowledge retrieval service with vector search and BM25 reranking.
Decoupled from specific business logic for maximum reusability.

Usage:
    # Initialize service
    rag = CommonRAGService()

    # Build knowledge base
    rag.rebuild_knowledge_base(session)

    # Query
    results = rag.query("What is RAG?", top_k=5, use_rerank=True)
"""

import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
import jieba
from sqlalchemy.orm import Session

from ..services.llm.types import RAGContext

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeDocument:
    """Generic knowledge document"""

    id: str  # Unique document ID
    content: str  # Document text content
    metadata: Dict[str, Any]  # Arbitrary metadata


class CommonRAGService:
    """
    Common RAG Service - Universal knowledge retrieval

    Features:
    - Vector embedding with sentence-transformers
    - Semantic search with ChromaDB
    - BM25 keyword reranking
    - Caching and performance optimization
    - Business-logic agnostic

    Thread-safe: No (create separate instance per request if needed)
    """

    def __init__(
        self,
        collection_name: str = "interview_knowledge",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
        chroma_path: Optional[str] = None,
    ):
        """
        Initialize RAG service.

        Args:
            collection_name: ChromaDB collection name
            embedding_model: Sentence transformer model name
            chroma_path: Path to ChromaDB storage (default: backend/chroma_db)
        """
        self.collection_name = collection_name

        # Load embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        logger.info("Embedding model loaded successfully")

        # Initialize vector database
        if chroma_path is None:
            chroma_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "chroma_db"
            )

        os.makedirs(chroma_path, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path, settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name, metadata={"description": "Common knowledge base"}
        )

        logger.info(
            f"Vector DB initialized. Collection: {collection_name}, "
            f"Documents: {self.collection.count()}"
        )

    # ========================================================================
    # Knowledge Base Construction
    # ========================================================================

    def rebuild_knowledge_base(self, session: Session):
        """
        Rebuild entire knowledge base from database.

        This method queries the database and constructs knowledge documents.

        Args:
            session: SQLAlchemy database session
        """
        from app import models

        logger.info("Rebuilding knowledge base...")

        # Clear existing collection
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Common knowledge base"},
            )
            logger.info("Cleared existing collection")
        except Exception as e:
            logger.warning(f"Failed to clear collection: {e}")

        documents: List[KnowledgeDocument] = []

        # 1. Add questions (with refined questions)
        questions = session.query(models.InterviewQuestion).filter(
            models.InterviewQuestion.has_answer == True
        ).all()

        for q in questions:
            question_text = q.refined_question or q.question
            content = (
                f"【问题】{question_text}\n"
                f"【答案】{q.answer}\n"
                f"【领域】{q.domain}\n"
                f"【关键词】{q.keywords}"
            )

            documents.append(
                KnowledgeDocument(
                    id=f"question_{q.id}",
                    content=content,
                    metadata={
                        "type": "question",
                        "question_id": q.id,
                        "domain": q.domain or "",
                        "keywords": q.keywords or "",
                    },
                )
            )

        # 2. Add notes
        notes = session.query(models.InterviewNote).all()

        for note in notes:
            content = (
                f"【笔记】{note.title}\n"
                f"【类型】{note.note_type}\n"
                f"【内容】{note.content}"
            )
            if note.tags:
                content += f"\n【标签】{note.tags}"

            documents.append(
                KnowledgeDocument(
                    id=f"note_{note.id}",
                    content=content,
                    metadata={
                        "type": "note",
                        "note_id": note.id,
                        "note_type": note.note_type,
                        "tags": note.tags or "",
                    },
                )
            )

        # 3. Add job analyses
        analyses = session.query(models.JobAnalysis).all()

        for analysis in analyses:
            content = f"【岗位】{analysis.job_title}\n【JD】{analysis.jd_content}"
            if analysis.key_requirements:
                content += f"\n【关键要求】{analysis.key_requirements}"

            documents.append(
                KnowledgeDocument(
                    id=f"job_{analysis.id}",
                    content=content,
                    metadata={
                        "type": "job_analysis",
                        "analysis_id": analysis.id,
                        "job_title": analysis.job_title,
                    },
                )
            )

        # Batch add to vector DB
        self._add_documents_batch(documents)

        logger.info(f"Knowledge base rebuilt with {len(documents)} documents")

    def _add_documents_batch(self, documents: List[KnowledgeDocument]):
        """
        Add documents to vector database in batch.

        Args:
            documents: List of knowledge documents
        """
        if not documents:
            logger.warning("No documents to add")
            return

        logger.info(f"Vectorizing {len(documents)} documents...")

        # Extract fields
        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # Vectorize
        embeddings = self.embedding_model.encode(contents, show_progress_bar=True)

        # Add to ChromaDB
        self.collection.add(
            ids=ids,
            documents=contents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )

        logger.info(f"Added {len(documents)} documents to vector DB")

    # ========================================================================
    # Query Methods
    # ========================================================================

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        recall_k: int = 20,
        use_rerank: bool = True,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RAGContext:
        """
        Query knowledge base with two-stage hybrid retrieval.

        Stage 1 (Coarse Recall): Retrieve top-20 using vector search + BM25
        Stage 2 (Precision Rerank): Rerank to top-5 using weighted scoring

        Args:
            query_text: Query string
            top_k: Number of final results to return (default: 5)
            recall_k: Number of candidates in recall stage (default: 20)
            use_rerank: Whether to use precision reranking
            filters: Optional metadata filters (e.g., {"type": "question"})

        Returns:
            RAGContext with detailed two-stage retrieval info
        """
        logger.info(f"Two-stage retrieval: {query_text[:100]}...")

        # ========================================================================
        # Stage 1: Coarse Recall (top-20)
        # ========================================================================
        logger.debug(f"Stage 1: Coarse recall (top-{recall_k})")

        # 1.1 Vector search
        vector_results = self._semantic_search(
            query_text, top_k=recall_k, filters=filters
        )
        logger.debug(f"Vector search: {len(vector_results)} results")

        # 1.2 BM25 keyword search
        bm25_results = self._bm25_search(
            query_text, top_k=recall_k, filters=filters
        )
        logger.debug(f"BM25 search: {len(bm25_results)} results")

        # 1.3 Merge and deduplicate
        recall_results = self._merge_results(vector_results, bm25_results, recall_k)
        logger.info(f"Stage 1 complete: {len(recall_results)} candidates")

        # ========================================================================
        # Stage 2: Precision Reranking (top-5)
        # ========================================================================
        if use_rerank and len(recall_results) > top_k:
            logger.debug(f"Stage 2: Precision rerank (top-{top_k})")
            final_results = self._bm25_rerank(query_text, recall_results, top_k)
        else:
            final_results = recall_results[:top_k]

        logger.info(f"Stage 2 complete: {len(final_results)} final results")

        # ========================================================================
        # Format as RAGContext
        # ========================================================================
        documents = [r["content"] for r in final_results]
        sources = [r.get("metadata") or {} for r in final_results]
        scores = [r["score"] for r in final_results]

        # Include recall stage details
        recall_details = [
            {
                "content": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"],
                "metadata": r.get("metadata") or {},
                "score": r["score"],
                "vector_score": r.get("vector_score", 0),
                "bm25_score": r.get("bm25_score", 0),
            }
            for r in recall_results
        ]

        context = RAGContext(
            documents=documents,
            sources=sources,
            scores=scores,
            recall_results=recall_details,
            recall_method="vector+bm25",
            rerank_method="bm25_weighted" if use_rerank else None,
        )

        logger.info(f"Query complete: {len(documents)} final, {len(recall_details)} recall")
        return context

    def _semantic_search(
        self,
        query_text: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic vector search.

        Args:
            query_text: Query string
            top_k: Number of results
            filters: Metadata filters

        Returns:
            List of search results
        """
        # Vectorize query
        query_embedding = self.embedding_model.encode([query_text])[0]

        # Search in ChromaDB
        search_kwargs = {
            "query_embeddings": [query_embedding.tolist()],
            "n_results": top_k,
        }

        if filters:
            search_kwargs["where"] = filters

        results = self.collection.query(**search_kwargs)

        # Format results
        formatted = []
        if results["documents"] and len(results["documents"]) > 0:
            for i in range(len(results["documents"][0])):
                # ChromaDB returns distance (lower is better)
                # Convert to similarity score (higher is better)
                distance = results["distances"][0][i]
                similarity = 1 / (1 + distance)  # Simple normalization

                # 确保metadata不为None
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                metadata = metadata or {}  # 如果是None，使用空字典

                formatted.append(
                    {
                        "content": results["documents"][0][i],
                        "metadata": metadata,
                        "score": similarity,
                        "vector_score": similarity,  # Store original vector score
                        "distance": distance,
                        "id": results["ids"][0][i],
                    }
                )

        return formatted

    def _bm25_search(
        self,
        query_text: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 keyword search on entire knowledge base.

        Args:
            query_text: Query string
            top_k: Number of results
            filters: Metadata filters

        Returns:
            List of search results with BM25 scores
        """
        # Get all documents from ChromaDB
        all_results = self.collection.get()

        if not all_results["documents"]:
            return []

        documents = all_results["documents"]
        metadatas = all_results["metadatas"]
        ids = all_results["ids"]

        # Apply filters if needed
        if filters:
            filtered_docs = []
            filtered_metas = []
            filtered_ids = []
            for doc, meta, doc_id in zip(documents, metadatas, ids):
                if meta and all(meta.get(k) == v for k, v in filters.items()):
                    filtered_docs.append(doc)
                    filtered_metas.append(meta)
                    filtered_ids.append(doc_id)
            documents = filtered_docs
            metadatas = filtered_metas
            ids = filtered_ids

        if not documents:
            return []

        # Tokenize for BM25
        import jieba
        query_tokens = list(jieba.cut(query_text))
        corpus_tokens = [list(jieba.cut(doc)) for doc in documents]

        # Calculate BM25 scores
        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi(corpus_tokens)
        scores = bm25.get_scores(query_tokens)

        # Build results
        results = []
        for i, (doc, meta, doc_id, score) in enumerate(zip(documents, metadatas, ids, scores)):
            results.append({
                "content": doc,
                "metadata": meta or {},
                "score": float(score),
                "bm25_score": float(score),  # Store original BM25 score
                "id": doc_id,
            })

        # Sort by BM25 score and return top-k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _merge_results(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Merge vector and BM25 results with reciprocal rank fusion (RRF).

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            top_k: Number of results to return

        Returns:
            Merged and deduplicated results
        """
        # Build ID to result mapping
        merged = {}

        # Add vector results (with rank-based scoring)
        for rank, result in enumerate(vector_results, 1):
            doc_id = result["id"]
            vector_rrf = 1.0 / (rank + 60)  # RRF with k=60
            merged[doc_id] = {
                **result,
                "vector_rank": rank,
                "vector_rrf": vector_rrf,
                "bm25_rrf": 0.0,
            }

        # Add BM25 results (merge if exists)
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result["id"]
            bm25_rrf = 1.0 / (rank + 60)

            if doc_id in merged:
                # Merge: add BM25 info
                merged[doc_id]["bm25_rank"] = rank
                merged[doc_id]["bm25_rrf"] = bm25_rrf
                merged[doc_id]["bm25_score"] = result.get("bm25_score", 0)
            else:
                # New document from BM25
                merged[doc_id] = {
                    **result,
                    "bm25_rank": rank,
                    "bm25_rrf": bm25_rrf,
                    "vector_rrf": 0.0,
                }

        # Calculate combined RRF score
        for doc_id, doc in merged.items():
            doc["rrf_score"] = doc["vector_rrf"] + doc["bm25_rrf"]
            doc["score"] = doc["rrf_score"]  # Use RRF as final score

        # Sort by RRF score and return top-k
        results = list(merged.values())
        results.sort(key=lambda x: x["rrf_score"], reverse=True)
        return results[:top_k]

    def _bm25_rerank(
        self, query_text: str, candidates: List[Dict], top_k: int = 5
    ) -> List[Dict]:
        """
        Rerank candidates using BM25 algorithm.

        Args:
            query_text: Query string
            candidates: Candidate documents
            top_k: Number of results

        Returns:
            Reranked results
        """
        if not candidates:
            return []

        logger.debug(f"BM25 reranking {len(candidates)} candidates...")

        # Tokenize
        query_tokens = list(jieba.cut(query_text))
        corpus_tokens = [list(jieba.cut(doc["content"])) for doc in candidates]

        # Calculate BM25 scores
        bm25 = BM25Okapi(corpus_tokens)
        scores = bm25.get_scores(query_tokens)

        # Add BM25 scores
        for i, doc in enumerate(candidates):
            doc["bm25_score"] = float(scores[i])
            # Combine with semantic score (weighted average)
            doc["score"] = 0.6 * doc["score"] + 0.4 * (scores[i] / max(scores) if max(scores) > 0 else 0)

        # Sort by combined score
        reranked = sorted(candidates, key=lambda x: x["score"], reverse=True)

        return reranked[:top_k]

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.

        Returns:
            Statistics dictionary
        """
        total_docs = self.collection.count()

        # TODO: Add more detailed stats
        # - Documents by type
        # - Documents by domain
        # - Average embedding computation time

        return {
            "total_documents": total_docs,
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_model.get_config_dict().get("model_name_or_path", "unknown"),
        }

    def clear_cache(self):
        """
        Clear any internal caches.

        Currently not implemented (no caching yet).
        """
        # TODO: Implement caching layer
        # - Cache frequent queries
        # - Cache embeddings
        pass

    # ========================================================================
    # TODO: Future enhancements
    # ========================================================================

    # TODO: Implement incremental updates
    # def add_document(self, document: KnowledgeDocument):
    #     """Add single document without full rebuild"""
    #     pass

    # TODO: Implement query caching
    # def _get_cached_results(self, query_hash: str):
    #     """Get cached query results"""
    #     pass

    # TODO: Implement hybrid scoring strategies
    # def _hybrid_score(self, semantic_score, bm25_score, strategy="weighted"):
    #     """Combine semantic and BM25 scores"""
    #     pass

    # TODO: Implement query expansion
    # def _expand_query(self, query: str) -> List[str]:
    #     """Generate query variations for better recall"""
    #     pass
