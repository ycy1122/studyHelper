"""
RAG服务 - 实现知识库检索和重排功能
"""
import os
import json
import logging
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
import jieba
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RAGService:
    """RAG服务类 - 负责向量化、检索、重排"""

    def __init__(self, db_session: Session):
        """
        初始化RAG服务

        Args:
            db_session: 数据库会话
        """
        self.db = db_session

        # 初始化Embedding模型（使用中文模型）
        logger.info("正在加载Embedding模型...")
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logger.info("Embedding模型加载完成")

        # 初始化向量数据库
        chroma_path = os.path.join(os.path.dirname(__file__), '..', '..', 'chroma_db')
        os.makedirs(chroma_path, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # 创建集合（如果不存在）
        self.collection = self.chroma_client.get_or_create_collection(
            name="interview_knowledge",
            metadata={"description": "面试知识库"}
        )

        logger.info(f"向量数据库初始化完成，当前文档数: {self.collection.count()}")

    def build_knowledge_base(self):
        """
        构建知识库
        将所有题目、笔记内容向量化并存入Chroma
        """
        from app import models

        logger.info("开始构建知识库...")

        # 清空现有集合
        try:
            self.chroma_client.delete_collection("interview_knowledge")
            self.collection = self.chroma_client.create_collection(
                name="interview_knowledge",
                metadata={"description": "面试知识库"}
            )
        except:
            pass

        documents = []
        metadatas = []
        ids = []

        # 1. 添加题目（使用改写后的问题）
        questions = self.db.query(models.InterviewQuestion).filter(
            models.InterviewQuestion.has_answer == True
        ).all()

        for q in questions:
            # 使用改写后的问题，如果没有则用原问题
            question_text = q.refined_question or q.question
            doc_text = f"【问题】{question_text}\n【答案】{q.answer}\n【领域】{q.domain}\n【关键词】{q.keywords}"

            documents.append(doc_text)
            metadatas.append({
                'type': 'question',
                'question_id': q.id,
                'domain': q.domain or '',
                'keywords': q.keywords or ''
            })
            ids.append(f"question_{q.id}")

        # 2. 添加笔记内容
        notes = self.db.query(models.InterviewNote).all()

        for note in notes:
            doc_text = f"【笔记】{note.title}\n【类型】{note.note_type}\n【内容】{note.content}"
            if note.tags:
                doc_text += f"\n【标签】{note.tags}"

            documents.append(doc_text)
            metadatas.append({
                'type': 'note',
                'note_id': note.id,
                'note_type': note.note_type,
                'tags': note.tags or ''
            })
            ids.append(f"note_{note.id}")

        # 3. 添加岗位分析记录
        analyses = self.db.query(models.JobAnalysis).all()

        for analysis in analyses:
            doc_text = f"【岗位】{analysis.job_title}\n【JD】{analysis.jd_content}"
            if analysis.key_requirements:
                doc_text += f"\n【关键要求】{analysis.key_requirements}"

            documents.append(doc_text)
            metadatas.append({
                'type': 'job_analysis',
                'analysis_id': analysis.id,
                'job_title': analysis.job_title
            })
            ids.append(f"job_{analysis.id}")

        # 批量添加到向量数据库
        if documents:
            logger.info(f"准备向量化 {len(documents)} 个文档...")

            # 向量化
            embeddings = self.embedding_model.encode(documents, show_progress_bar=True)

            # 存入Chroma
            self.collection.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"知识库构建完成！共 {len(documents)} 个文档")
        else:
            logger.warning("没有可用文档，知识库为空")

    def semantic_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        语义搜索

        Args:
            query: 查询文本
            top_k: 返回前K个结果

        Returns:
            搜索结果列表
        """
        logger.info(f"执行语义搜索: {query[:50]}...")

        # 向量化查询
        query_embedding = self.embedding_model.encode([query])[0]

        # 从Chroma检索
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )

        # 格式化结果
        formatted_results = []
        if results['documents'] and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i],
                    'id': results['ids'][0][i]
                })

        logger.info(f"检索到 {len(formatted_results)} 个相关文档")
        return formatted_results

    def bm25_rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        使用BM25重排序

        Args:
            query: 查询文本
            candidates: 候选文档列表
            top_k: 返回前K个结果

        Returns:
            重排序后的结果
        """
        if not candidates:
            return []

        logger.info(f"使用BM25重排序 {len(candidates)} 个候选文档...")

        # 分词
        query_tokens = list(jieba.cut(query))
        corpus_tokens = [list(jieba.cut(doc['document'])) for doc in candidates]

        # 计算BM25分数
        bm25 = BM25Okapi(corpus_tokens)
        scores = bm25.get_scores(query_tokens)

        # 添加BM25分数并排序
        for i, doc in enumerate(candidates):
            doc['bm25_score'] = float(scores[i])

        # 按BM25分数排序
        reranked = sorted(candidates, key=lambda x: x['bm25_score'], reverse=True)

        logger.info(f"重排序完成，返回前 {top_k} 个结果")
        return reranked[:top_k]

    def analyze_jd_and_retrieve(self, jd_content: str, job_title: str) -> Tuple[str, List[int]]:
        """
        分析岗位JD并检索相关知识

        Args:
            jd_content: 岗位JD内容
            job_title: 岗位名称

        Returns:
            (分析结果文本, 推荐题目ID列表)
        """
        logger.info(f"开始分析岗位: {job_title}")

        # 1. 语义搜索召回
        search_results = self.semantic_search(
            query=f"{job_title}\n{jd_content}",
            top_k=20
        )

        # 2. BM25重排序
        reranked_results = self.bm25_rerank(
            query=jd_content,
            candidates=search_results,
            top_k=10
        )

        # 3. 提取推荐题目ID
        recommended_question_ids = []
        for result in reranked_results:
            if result['metadata'].get('type') == 'question':
                question_id = result['metadata'].get('question_id')
                if question_id:
                    recommended_question_ids.append(question_id)

        # 4. 构建上下文用于生成面试计划
        context = self._build_context(reranked_results)

        logger.info(f"检索完成，推荐 {len(recommended_question_ids)} 道题目")

        return context, recommended_question_ids

    def _build_context(self, results: List[Dict]) -> str:
        """构建上下文字符串"""
        context_parts = []

        for i, result in enumerate(results, 1):
            doc_type = result['metadata'].get('type', '未知')
            context_parts.append(f"\n【相关知识{i}】类型: {doc_type}")
            context_parts.append(result['document'])
            context_parts.append(f"相关度得分: {result.get('bm25_score', 0):.2f}")

        return "\n".join(context_parts)
