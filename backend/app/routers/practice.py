"""
练习功能API - 答题、评分、记录
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import sys
import os
from decimal import Decimal
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app import schemas, models
from app.database import get_db
from questionExtract.config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
from openai import OpenAI
import httpx

router = APIRouter(prefix="/practice", tags=["练习功能"])

# 初始化OpenAI客户端
http_client = httpx.Client(timeout=60.0)
client = OpenAI(
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL,
    http_client=http_client
)

# AI评分提示词
SCORING_PROMPT_TEMPLATE = """你是一个专业的面试评分助手。请根据用户的回答和参考答案，给出评分和反馈。

面试问题：{question}

参考答案：{reference_answer}

关键词：{keywords}

用户回答：{user_answer}

请从以下几个维度评分：
1. 准确性：回答是否准确、正确
2. 完整性：是否涵盖了关键要点
3. 深度：回答的深度和理解程度
4. 表达：逻辑性和条理性

综合评分：0-100分

请以JSON格式返回：
{{
    "score": <0-100的分数>,
    "feedback": "<详细的评分反馈，包括优点和改进建议>",
    "key_points_covered": <覆盖了几个关键点>,
    "suggestions": "<具体的改进建议>"
}}

只返回JSON对象，不要有其他说明文字。
"""


def score_answer_with_ai(question: str, user_answer: str, reference_answer: str, keywords: str = None) -> dict:
    """使用AI对用户回答进行评分"""

    prompt = SCORING_PROMPT_TEMPLATE.format(
        question=question,
        reference_answer=reference_answer,
        keywords=keywords or "无",
        user_answer=user_answer
    )

    try:
        response = client.chat.completions.create(
            model=QWEN_MODEL,
            messages=[
                {"role": "system", "content": "你是一个专业的面试评分助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content.strip()
        result = json.loads(content)

        return {
            'score': Decimal(str(result.get('score', 0))),
            'feedback': result.get('feedback', ''),
            'suggestions': result.get('suggestions', '')
        }

    except Exception as e:
        # 如果AI评分失败，返回默认值
        return {
            'score': Decimal('0'),
            'feedback': f'AI评分失败: {str(e)}',
            'suggestions': '请稍后重试'
        }


@router.post("/submit", response_model=schemas.ScoreAnswerResponse)
def submit_answer(
    submission: schemas.ScoreAnswerRequest,
    db: Session = Depends(get_db)
):
    """
    提交答案并获取AI评分
    """
    # 获取问题
    question = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.id == submission.question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="问题不存在"
        )

    if not question.has_answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该问题没有参考答案"
        )

    # 使用AI评分
    scoring_result = score_answer_with_ai(
        question=question.question,
        user_answer=submission.user_answer,
        reference_answer=question.answer,
        keywords=question.keywords
    )

    # 创建练习记录
    practice_record = models.PracticeRecord(
        question_id=submission.question_id,
        user_answer=submission.user_answer,
        ai_score=scoring_result['score'],
        ai_feedback=f"{scoring_result['feedback']}\n\n改进建议：{scoring_result['suggestions']}",
        mastery_level=submission.mastery_level,
        time_spent=submission.time_spent
    )

    db.add(practice_record)

    # 更新问题的最新掌握程度
    if submission.mastery_level:
        question.latest_mastery_level = submission.mastery_level

    db.commit()
    db.refresh(practice_record)

    return schemas.ScoreAnswerResponse(
        practice_record_id=practice_record.id,
        ai_score=practice_record.ai_score,
        ai_feedback=practice_record.ai_feedback,
        reference_answer=question.answer,
        keywords=question.keywords
    )


@router.post("/mark-mastery")
def mark_mastery(
    question_id: int,
    mastery_level: str,
    db: Session = Depends(get_db)
):
    """
    仅标记问题的掌握程度（不提交答案）
    """
    if mastery_level not in ['不会', '一般', '会了']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="掌握程度必须是：不会、一般、会了 之一"
        )

    question = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="问题不存在"
        )

    # 创建简单的练习记录
    practice_record = models.PracticeRecord(
        question_id=question_id,
        mastery_level=mastery_level
    )

    db.add(practice_record)

    # 更新问题的最新掌握程度
    question.latest_mastery_level = mastery_level

    db.commit()

    return {"message": "标记成功", "mastery_level": mastery_level}


@router.get("/records", response_model=List[schemas.PracticeRecordResponse])
def get_practice_records(
    question_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取练习记录"""
    query = db.query(models.PracticeRecord)

    if question_id:
        query = query.filter(models.PracticeRecord.question_id == question_id)

    query = query.order_by(models.PracticeRecord.practice_time.desc())
    records = query.offset(skip).limit(limit).all()

    return records


@router.get("/records/{record_id}", response_model=schemas.PracticeRecordResponse)
def get_practice_record(record_id: int, db: Session = Depends(get_db)):
    """获取单条练习记录"""
    record = db.query(models.PracticeRecord).filter(
        models.PracticeRecord.id == record_id
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="练习记录不存在"
        )

    return record
