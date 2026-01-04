"""
明细问题查询API
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List, Optional
import random

from app import schemas, models
from app.database import get_db

router = APIRouter(prefix="/questions", tags=["明细问题"])


@router.get("/", response_model=List[schemas.InterviewQuestionResponse])
def list_questions(
    skip: int = 0,
    limit: int = 100,
    domain: Optional[str] = None,
    has_answer: Optional[bool] = None,
    mastery_level: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取明细问题列表"""
    query = db.query(models.InterviewQuestion)

    # 过滤条件
    if domain:
        query = query.filter(models.InterviewQuestion.domain == domain)

    if has_answer is not None:
        query = query.filter(models.InterviewQuestion.has_answer == has_answer)

    if mastery_level:
        query = query.filter(models.InterviewQuestion.latest_mastery_level == mastery_level)

    if keyword:
        query = query.filter(
            or_(
                models.InterviewQuestion.question.contains(keyword),
                models.InterviewQuestion.keywords.contains(keyword)
            )
        )

    query = query.order_by(models.InterviewQuestion.created_at.desc())
    questions = query.offset(skip).limit(limit).all()

    return questions


@router.get("/random", response_model=schemas.InterviewQuestionResponse)
def get_random_question(
    domain: Optional[str] = Query(None, description="领域筛选"),
    mastery_level: Optional[str] = Query(None, description="掌握程度筛选"),
    exclude_ids: Optional[str] = Query(None, description="排除的问题ID列表，逗号分隔"),
    db: Session = Depends(get_db)
):
    """
    随机获取一个问题用于练习
    """
    query = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.has_answer == True  # 只返回有答案的问题
    )

    # 应用过滤条件
    if domain:
        query = query.filter(models.InterviewQuestion.domain == domain)

    if mastery_level:
        query = query.filter(models.InterviewQuestion.latest_mastery_level == mastery_level)

    # 排除指定ID
    if exclude_ids:
        try:
            exclude_list = [int(x.strip()) for x in exclude_ids.split(',') if x.strip()]
            if exclude_list:
                query = query.filter(~models.InterviewQuestion.id.in_(exclude_list))
        except ValueError:
            pass

    # 获取所有符合条件的问题
    questions = query.all()

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有符合条件的问题"
        )

    # 随机选择一个
    question = random.choice(questions)

    return question


@router.get("/{question_id}", response_model=schemas.InterviewQuestionResponse)
def get_question(question_id: int, db: Session = Depends(get_db)):
    """获取单个问题详情"""
    question = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="问题不存在"
        )

    return question


@router.put("/{question_id}/answer", response_model=schemas.InterviewQuestionResponse)
def update_question_answer(
    question_id: int,
    answer_data: schemas.InterviewQuestionUpdateAnswer,
    db: Session = Depends(get_db)
):
    """更新问题答案"""
    question = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="问题不存在"
        )

    # 更新答案
    question.answer = answer_data.answer
    question.has_answer = True

    # 更新可选字段
    if answer_data.keywords is not None:
        question.keywords = answer_data.keywords
    if answer_data.domain is not None:
        question.domain = answer_data.domain

    db.commit()
    db.refresh(question)

    return question


@router.get("/statistics/overview", response_model=schemas.StatisticsResponse)
def get_statistics(db: Session = Depends(get_db)):
    """获取统计信息"""

    # 总问题数
    total_questions = db.query(func.count(models.InterviewQuestion.id)).scalar()

    # 已有答案的问题数
    answered_questions = db.query(func.count(models.InterviewQuestion.id)).filter(
        models.InterviewQuestion.has_answer == True
    ).scalar()

    # 已练习的问题数（有练习记录的）
    practiced_questions = db.query(
        func.count(func.distinct(models.PracticeRecord.question_id))
    ).scalar()

    # 掌握程度统计
    mastery_stats_raw = db.query(
        models.InterviewQuestion.latest_mastery_level,
        func.count(models.InterviewQuestion.id)
    ).filter(
        models.InterviewQuestion.latest_mastery_level.isnot(None)
    ).group_by(
        models.InterviewQuestion.latest_mastery_level
    ).all()

    mastery_stats = {level: count for level, count in mastery_stats_raw}
    mastery_stats.setdefault('不会', 0)
    mastery_stats.setdefault('一般', 0)
    mastery_stats.setdefault('会了', 0)
    mastery_stats['未练习'] = total_questions - practiced_questions

    # 领域统计
    domain_stats_raw = db.query(
        models.InterviewQuestion.domain,
        func.count(models.InterviewQuestion.id)
    ).filter(
        models.InterviewQuestion.domain.isnot(None)
    ).group_by(
        models.InterviewQuestion.domain
    ).all()

    domain_stats = {domain: count for domain, count in domain_stats_raw}

    return schemas.StatisticsResponse(
        total_questions=total_questions,
        answered_questions=answered_questions,
        practiced_questions=practiced_questions,
        mastery_stats=mastery_stats,
        domain_stats=domain_stats
    )
