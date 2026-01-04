"""
评估与A/B测试API

提供RAG系统的评估、A/B测试和性能监控功能
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import time
import logging

from app.database import get_db
from app.services.chat_service import ChatService
from app.routers.chat import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["评估与测试"])


# ============================================================================
# Request/Response Models
# ============================================================================

class StandardQuestion(BaseModel):
    """标准测试问题"""
    question: str
    ground_truth: str
    category: Optional[str] = None


class TestConfig(BaseModel):
    """测试配置"""
    model: str = "qwen3-max"
    query_strategy: str = "multi-version"  # multi-version, single, none
    retrieval_method: str = "hybrid"  # hybrid, vector-only, bm25-only
    rerank_method: str = "rrf"  # rrf, bm25, none
    use_rag: bool = True


class TestResult(BaseModel):
    """单个测试结果"""
    question: str
    answer: str
    ground_truth: str
    score: float
    response_time: float
    has_relevant_docs: bool
    rag_documents_count: int
    timestamp: datetime


class ABTestConfig(BaseModel):
    """A/B测试配置"""
    config_a: TestConfig
    config_b: TestConfig
    test_questions: List[str]  # Question IDs or indices


class ABTestResult(BaseModel):
    """A/B测试结果"""
    config_a_results: Dict[str, Any]
    config_b_results: Dict[str, Any]
    winner: Optional[str] = None  # "A", "B", or "tie"
    timestamp: datetime


# ============================================================================
# Standard Test Questions (Ground Truth)
# ============================================================================

STANDARD_QUESTIONS = [
    {
        "id": 1,
        "question": "什么是RAG（检索增强生成）？它有什么优势？",
        "ground_truth": "RAG是一种结合了信息检索和生成式AI的技术。它首先从知识库中检索相关文档，然后基于检索到的内容生成回答。主要优势包括：1）减少幻觉，提高准确性；2）能够利用最新的外部知识；3）可以提供来源引用；4）无需重新训练模型就能更新知识。",
        "category": "基础概念"
    },
    {
        "id": 2,
        "question": "BM25算法的工作原理是什么？",
        "ground_truth": "BM25是一种基于词频的信息检索算法。它通过以下因素计算相关性得分：1）词频TF（Term Frequency）：词在文档中出现的频率，使用饱和函数避免过度奖励高频词；2）逆文档频率IDF（Inverse Document Frequency）：词的稀有程度，稀有词权重更高；3）文档长度归一化：较长文档不会获得不公平的优势。公式核心参数包括k1（控制TF饱和度）和b（控制长度归一化）。",
        "category": "检索算法"
    },
    {
        "id": 3,
        "question": "向量检索和关键词检索各有什么优缺点？",
        "ground_truth": "向量检索优点：能捕捉语义相似性，对同义词和改写鲁棒，适合语义理解任务。缺点：计算成本高，对精确匹配支持弱。关键词检索（如BM25）优点：速度快，精确匹配效果好，可解释性强。缺点：无法理解语义，对同义词和改写敏感。最佳实践是混合检索（Hybrid Search），结合两者优势。",
        "category": "检索方法"
    },
    {
        "id": 4,
        "question": "什么是RRF（倒数排名融合），如何使用？",
        "ground_truth": "RRF是一种简单有效的结果融合方法。对于文档d，RRF得分 = Σ 1/(k + rank_i)，其中rank_i是文档在第i个排序列表中的排名，k是平滑参数（通常取60）。RRF的优点：1）不需要归一化分数；2）对不同检索系统的分数尺度不敏感；3）实现简单但效果好。常用于混合检索中融合向量检索和BM25的结果。",
        "category": "融合算法"
    },
    {
        "id": 5,
        "question": "Query改写在RAG中的作用是什么？如何实现？",
        "ground_truth": "Query改写是将用户原始问题转换为更适合检索的形式，以提高召回率和准确性。作用包括：1）展开缩写词和简称；2）补充上下文信息；3）生成多个检索视角。实现方法：1）基于规则的改写；2）使用LLM生成改写版本；3）生成多个版本（扩展版、关键词版、同义词版）并分别检索后融合结果。多版本改写可以覆盖不同的检索需求，提升整体召回效果。",
        "category": "Query优化"
    }
]


# ============================================================================
# Evaluation Metrics
# ============================================================================

def calculate_similarity_score(answer: str, ground_truth: str) -> float:
    """
    计算答案与标准答案的相似度得分

    简化实现：使用关键词匹配。实际应用中可以使用：
    - BLEU/ROUGE分数
    - 语义相似度（embedding cosine similarity）
    - LLM-as-a-judge
    """
    # 简单的关键词匹配实现
    answer_lower = answer.lower()
    ground_truth_lower = ground_truth.lower()

    # 提取关键概念（简化版）
    key_concepts = []
    if "rag" in ground_truth_lower:
        key_concepts.extend(["rag", "检索", "生成", "知识库"])
    if "bm25" in ground_truth_lower:
        key_concepts.extend(["bm25", "词频", "tf", "idf"])
    if "向量" in ground_truth_lower:
        key_concepts.extend(["向量", "语义", "embedding"])
    if "rrf" in ground_truth_lower:
        key_concepts.extend(["rrf", "倒数", "排名", "融合"])
    if "query" in ground_truth_lower or "改写" in ground_truth_lower:
        key_concepts.extend(["query", "改写", "重写"])

    # 计算匹配度
    matches = sum(1 for concept in key_concepts if concept in answer_lower)
    score = min(matches / max(len(key_concepts), 1), 1.0)

    # 基础分：如果答案不为空
    if len(answer.strip()) > 10:
        score = max(score, 0.3)

    return score


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/standard-questions")
def get_standard_questions() -> List[Dict[str, Any]]:
    """获取标准测试问题列表"""
    return STANDARD_QUESTIONS


@router.post("/run-standard-test")
async def run_standard_test(
    config: TestConfig,
    chat_service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db)
) -> List[TestResult]:
    """
    运行标准测试

    对5个标准问题进行测试，返回评分结果
    """
    results = []
    session_id = f"eval-test-{int(time.time())}"

    logger.info(f"Running standard test with config: {config}")

    try:
        for question_data in STANDARD_QUESTIONS:
            start_time = time.time()

            # 调用chat服务获取答案
            answer_parts = []
            rag_docs_count = 0

            async for chunk in chat_service.stream_chat(
                session_id=session_id,
                user_message=question_data["question"],
                use_rag=config.use_rag,
                model_name=config.model if config.model != "auto" else None,
                db_session=db,
                dev_mode=True  # 获取debug信息
            ):
                # 跳过debug chunk
                if chunk.id == "debug":
                    # 从debug信息中提取RAG文档数量
                    try:
                        import json
                        debug_data = json.loads(chunk.choices[0].delta.content)
                        if debug_data.get("type") == "debug":
                            rag_info = debug_data.get("rag", {})
                            rag_docs_count = rag_info.get("final_count", 0)
                    except:
                        pass
                    continue

                # 收集答案内容
                if chunk.choices and chunk.choices[0].delta.content:
                    answer_parts.append(chunk.choices[0].delta.content)

            answer = "".join(answer_parts)
            response_time = (time.time() - start_time) * 1000  # Convert to ms

            # 计算得分
            score = calculate_similarity_score(answer, question_data["ground_truth"])

            result = TestResult(
                question=question_data["question"],
                answer=answer,
                ground_truth=question_data["ground_truth"],
                score=score,
                response_time=response_time,
                has_relevant_docs=rag_docs_count > 0,
                rag_documents_count=rag_docs_count,
                timestamp=datetime.now()
            )

            results.append(result)
            logger.info(f"Test completed: Q={question_data['id']}, Score={score:.2f}")

    except Exception as e:
        logger.error(f"Standard test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")

    return results


@router.post("/run-abtest")
async def run_abtest(
    abtest_config: ABTestConfig,
    chat_service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db)
) -> ABTestResult:
    """
    运行A/B测试

    比较两种配置的性能差异
    """
    logger.info("Running A/B test...")

    # Run tests for Config A
    results_a = await run_standard_test(abtest_config.config_a, chat_service, db)

    # Run tests for Config B
    results_b = await run_standard_test(abtest_config.config_b, chat_service, db)

    # Calculate aggregate metrics
    def aggregate_results(results: List[TestResult]) -> Dict[str, Any]:
        return {
            "accuracy": sum(r.score for r in results) / len(results) * 100,
            "avg_response_time": sum(r.response_time for r in results) / len(results),
            "recall_accuracy": sum(1 for r in results if r.has_relevant_docs) / len(results) * 100,
            "test_count": len(results)
        }

    metrics_a = aggregate_results(results_a)
    metrics_b = aggregate_results(results_b)

    # Determine winner
    winner = None
    if metrics_b["accuracy"] > metrics_a["accuracy"] + 2:  # 2% threshold
        winner = "B"
    elif metrics_a["accuracy"] > metrics_b["accuracy"] + 2:
        winner = "A"
    else:
        winner = "tie"

    return ABTestResult(
        config_a_results=metrics_a,
        config_b_results=metrics_b,
        winner=winner,
        timestamp=datetime.now()
    )


@router.get("/test-history")
def get_test_history(
    limit: int = 10,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    获取历史测试记录

    TODO: 实现数据库持久化
    """
    # Mock data for now
    return [
        {
            "id": 1,
            "timestamp": "2026-01-01 14:30:00",
            "config": "多版本Query + 混合检索",
            "accuracy": 85.2,
            "avg_response_time": 1250,
            "status": "completed"
        }
    ]


@router.get("/metrics/overview")
def get_metrics_overview() -> Dict[str, Any]:
    """
    获取评估系统概览指标

    TODO: 实现真实的统计数据
    """
    return {
        "total_tests": 12,
        "avg_accuracy": 78.5,
        "active_ab_tests": 2,
        "last_updated": datetime.now().isoformat()
    }
