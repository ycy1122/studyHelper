"""
岗位分析API - 包含RAG流程的面试准备计划生成
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app import schemas, models
from app.database import get_db

router = APIRouter(prefix="/job-analysis", tags=["岗位分析"])


@router.post("/", response_model=schemas.JobAnalysisResponse, status_code=status.HTTP_201_CREATED)
def create_job_analysis(
    job_analysis: schemas.JobAnalysisCreate,
    trigger_analysis: bool = False,  # 是否触发AI分析
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    创建岗位分析

    参数:
        trigger_analysis: 是否立即触发AI分析（默认False，只保存不分析）

    如果trigger_analysis=True，会在后台异步执行RAG分析流程
    """
    # 先创建记录
    db_job_analysis = models.JobAnalysis(
        **job_analysis.dict(),
        analysis_status='pending'
    )
    db.add(db_job_analysis)
    db.commit()
    db.refresh(db_job_analysis)

    # 如果需要触发分析，添加后台任务
    if trigger_analysis and background_tasks:
        db_job_analysis.analysis_status = 'processing'
        db.commit()
        db.refresh(db_job_analysis)

        background_tasks.add_task(
            analyze_job_with_rag,
            job_analysis_id=db_job_analysis.id,
            job_title=db_job_analysis.job_title,
            jd_content=db_job_analysis.jd_content
        )

    return db_job_analysis


@router.get("/", response_model=List[schemas.JobAnalysisResponse])
def list_job_analyses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取岗位分析列表"""
    query = db.query(models.JobAnalysis).order_by(
        models.JobAnalysis.created_at.desc()
    )
    analyses = query.offset(skip).limit(limit).all()
    return analyses


@router.get("/{analysis_id}", response_model=schemas.JobAnalysisResponse)
def get_job_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """获取单个岗位分析"""
    analysis = db.query(models.JobAnalysis).filter(
        models.JobAnalysis.id == analysis_id
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="岗位分析不存在"
        )

    return analysis


@router.post("/{analysis_id}/analyze", response_model=schemas.JobAnalysisResponse)
def trigger_analysis(
    analysis_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    触发AI分析（独立接口）

    对已保存的岗位分析触发AI分析，异步执行不阻塞
    """
    db_analysis = db.query(models.JobAnalysis).filter(
        models.JobAnalysis.id == analysis_id
    ).first()

    if not db_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="岗位分析不存在"
        )

    # 如果已经在分析中，不重复触发
    if db_analysis.analysis_status == 'processing':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="分析正在进行中，请勿重复提交"
        )

    # 更新状态为处理中
    db_analysis.analysis_status = 'processing'
    db.commit()
    db.refresh(db_analysis)

    # 添加后台任务
    background_tasks.add_task(
        analyze_job_with_rag,
        job_analysis_id=db_analysis.id,
        job_title=db_analysis.job_title,
        jd_content=db_analysis.jd_content
    )

    return db_analysis


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """删除岗位分析"""
    db_analysis = db.query(models.JobAnalysis).filter(
        models.JobAnalysis.id == analysis_id
    ).first()

    if not db_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="岗位分析不存在"
        )

    db.delete(db_analysis)
    db.commit()

    return None


async def analyze_job_with_rag(job_analysis_id: int, job_title: str, jd_content: str):
    """
    使用RAG流程分析岗位并生成面试准备计划（后台任务）

    流程：
    1. 语义改写JD内容，提取关键要求
    2. 向量化查询并召回相关知识：
       - 已有题目（改写后的问题）
       - 岗位描述
       - 笔记区内容
    3. 对召回结果进行重排
    4. 调用大模型生成面试准备计划
    """
    import logging
    import json
    from app.database import SessionLocal
    from app import models
    from app.services.rag_service import RAGService
    from questionExtract.config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
    from openai import OpenAI
    import httpx

    logger = logging.getLogger(__name__)
    logger.info(f"开始分析岗位: {job_title}")

    db = SessionLocal()
    try:
        # 1. 初始化RAG服务
        rag_service = RAGService(db)

        # 2. 确保知识库是最新的
        rag_service.build_knowledge_base()

        # 3. 使用RAG检索相关知识
        context, recommended_question_ids = rag_service.analyze_jd_and_retrieve(
            jd_content=jd_content,
            job_title=job_title
        )

        # 4. 调用大模型生成面试准备计划
        http_client = httpx.Client(timeout=120.0)
        llm_client = OpenAI(
            api_key=QWEN_API_KEY,
            base_url=QWEN_BASE_URL,
            http_client=http_client
        )

        prompt = f"""你是一个专业的面试准备顾问。请根据以下岗位JD和相关知识，为求职者制定详细的面试准备计划。

【岗位名称】{job_title}

【岗位JD】
{jd_content}

【相关知识库检索结果】
{context}

请生成一份详细的面试准备计划，包括：

1. **岗位分析**
   - 核心技能要求
   - 重点考察方向
   - 难度评估

2. **准备策略**
   - 技术准备重点
   - 项目经验准备
   - 行为面试准备

3. **推荐学习路径**
   - 必须掌握的知识点
   - 需要复习的领域
   - 加分项

4. **模拟面试问题**
   - 列出5-10个可能的面试问题
   - 每个问题的答题思路

5. **时间规划**
   - 建议准备周期
   - 每日学习安排

请以Markdown格式输出，结构清晰，内容专业实用。
"""

        response = llm_client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[
                {"role": "system", "content": "你是一个专业的面试准备顾问和职业规划师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        analysis_result = response.choices[0].message.content.strip()

        # 5. 更新数据库记录
        job_analysis = db.query(models.JobAnalysis).filter(
            models.JobAnalysis.id == job_analysis_id
        ).first()

        if job_analysis:
            job_analysis.analysis_result = analysis_result
            job_analysis.recommended_questions = json.dumps(recommended_question_ids)

            # 提取关键要求（简化版，从JD中提取）
            key_requirements = extract_key_requirements(jd_content, llm_client)
            job_analysis.key_requirements = key_requirements

            # 设置状态为完成
            job_analysis.analysis_status = 'completed'

            db.commit()

            logger.info(f"岗位分析完成: {job_title}，推荐 {len(recommended_question_ids)} 道题目")
        else:
            logger.error(f"未找到job_analysis记录: {job_analysis_id}")

    except Exception as e:
        logger.error(f"岗位分析失败: {e}", exc_info=True)
        # 更新为失败状态
        try:
            job_analysis = db.query(models.JobAnalysis).filter(
                models.JobAnalysis.id == job_analysis_id
            ).first()
            if job_analysis:
                job_analysis.analysis_result = f"分析失败: {str(e)}"
                job_analysis.analysis_status = 'failed'
                db.commit()
        except:
            pass
    finally:
        db.close()


def extract_key_requirements(jd_content: str, llm_client) -> str:
    """提取岗位关键要求"""
    from questionExtract.config import QWEN_MODEL

    try:
        prompt = f"""请从以下岗位JD中提取关键技能要求，用简洁的要点列出：

{jd_content}

请以要点形式输出，每行一个要求。"""

        response = llm_client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[
                {"role": "system", "content": "你是一个HR专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"提取失败: {str(e)}"
