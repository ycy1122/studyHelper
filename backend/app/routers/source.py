"""
原始问题管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app import schemas, models
from app.database import get_db
from questionExtract.question_parser import QuestionParser
from questionExtract.question_refiner import QuestionRefiner
from questionExtract.answer_generator import AnswerGenerator
from questionExtract.config import (
    QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, QUESTION_EXTRACTION_PROMPT
)

router = APIRouter(prefix="/source", tags=["原始问题管理"])


@router.post("/", response_model=schemas.SourceQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_source_question(
    source_question: schemas.SourceQuestionCreate,
    db: Session = Depends(get_db)
):
    """创建原始问题"""
    # 检查是否已存在
    existing = db.query(models.SourceQuestion).filter(
        models.SourceQuestion.original_text == source_question.original_text
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该原始问题已存在"
        )

    db_source = models.SourceQuestion(**source_question.dict())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)

    return db_source


@router.get("/", response_model=List[schemas.SourceQuestionResponse])
def list_source_questions(
    skip: int = 0,
    limit: int = 100,
    is_extracted: bool = None,
    db: Session = Depends(get_db)
):
    """获取原始问题列表"""
    query = db.query(models.SourceQuestion)

    if is_extracted is not None:
        query = query.filter(models.SourceQuestion.is_extracted == is_extracted)

    query = query.order_by(models.SourceQuestion.created_at.desc())
    questions = query.offset(skip).limit(limit).all()

    return questions


@router.get("/{source_id}", response_model=schemas.SourceQuestionResponse)
def get_source_question(source_id: int, db: Session = Depends(get_db)):
    """获取单个原始问题"""
    source = db.query(models.SourceQuestion).filter(
        models.SourceQuestion.id == source_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始问题不存在"
        )

    return source


@router.post("/{source_id}/extract")
def extract_questions(source_id: int, db: Session = Depends(get_db)):
    """
    提取原始问题的明细问题，并改写和生成答案
    """
    # 获取原始问题
    source = db.query(models.SourceQuestion).filter(
        models.SourceQuestion.id == source_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始问题不存在"
        )

    if source.is_extracted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该原始问题已提取过"
        )

    # 使用QuestionParser提取问题
    parser = QuestionParser(
        api_key=QWEN_API_KEY,
        base_url=QWEN_BASE_URL,
        model=QWEN_MODEL,
        prompt_template=QUESTION_EXTRACTION_PROMPT
    )

    questions = parser.parse_questions(source.original_text)

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未能识别到任何问题，请检查原始文本是否包含面试问题"
        )

    # 初始化问题改写器和答案生成器
    refiner = QuestionRefiner(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)
    answer_gen = AnswerGenerator(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)

    # 保存明细问题
    detail_count = 0
    for idx, question_text in enumerate(questions, 1):
        # 检查是否已存在该问题
        existing = db.query(models.InterviewQuestion).filter(
            models.InterviewQuestion.question == question_text
        ).first()

        if existing:
            continue  # 跳过重复问题

        # 改写问题
        refined_question = refiner.refine_question(question_text)

        # 生成答案
        answer_result = answer_gen.generate_answer(question_text)

        db_question = models.InterviewQuestion(
            source_title=source.source_title,
            question=question_text,
            refined_question=refined_question,
            question_index=idx,
            original_text=source.original_text,
            source_question_id=source.id,
            has_answer=bool(answer_result),
            answer=answer_result.get('answer') if answer_result else None,
            keywords=answer_result.get('keywords') if answer_result else None,
            domain=answer_result.get('domain') if answer_result else None
        )
        db.add(db_question)
        detail_count += 1

    # 更新原始问题状态
    source.is_extracted = True
    source.detail_count = detail_count

    db.commit()

    return {
        "message": "问题提取、改写和答案生成完成",
        "detail_count": detail_count,
        "total_identified": len(questions)
    }


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source_question(source_id: int, db: Session = Depends(get_db)):
    """删除原始问题"""
    source = db.query(models.SourceQuestion).filter(
        models.SourceQuestion.id == source_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始问题不存在"
        )

    db.delete(source)
    db.commit()

    return None
