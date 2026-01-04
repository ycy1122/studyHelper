"""
Pydantic模型 - API输入输出schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# 原始问题相关
class SourceQuestionBase(BaseModel):
    source_title: Optional[str] = None
    original_text: str


class SourceQuestionCreate(SourceQuestionBase):
    pass


class SourceQuestionUpdate(BaseModel):
    source_title: Optional[str] = None
    original_text: Optional[str] = None
    is_extracted: Optional[bool] = None
    detail_count: Optional[int] = None


class SourceQuestionResponse(SourceQuestionBase):
    id: int
    is_extracted: bool
    detail_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 明细问题相关
class InterviewQuestionBase(BaseModel):
    question: str
    source_title: Optional[str] = None


class InterviewQuestionUpdateAnswer(BaseModel):
    """更新问题答案"""
    answer: str
    keywords: Optional[str] = None
    domain: Optional[str] = None


class InterviewQuestionResponse(BaseModel):
    id: int
    question: str
    refined_question: Optional[str] = None  # 改写后的问题
    source_title: Optional[str] = None
    question_index: Optional[int] = None
    has_answer: bool
    answer: Optional[str] = None
    keywords: Optional[str] = None
    domain: Optional[str] = None
    latest_mastery_level: Optional[str] = None
    source_question_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# 练习相关
class PracticeRecordCreate(BaseModel):
    question_id: int
    user_answer: Optional[str] = None
    mastery_level: Optional[str] = Field(None, pattern="^(不会|一般|会了)$")
    time_spent: Optional[int] = None


class PracticeRecordResponse(BaseModel):
    id: int
    question_id: int
    user_answer: Optional[str] = None
    ai_score: Optional[Decimal] = None
    ai_feedback: Optional[str] = None
    mastery_level: Optional[str] = None
    practice_time: datetime
    time_spent: Optional[int] = None

    class Config:
        from_attributes = True


# 随机问题请求
class RandomQuestionRequest(BaseModel):
    domain: Optional[str] = None
    mastery_level: Optional[str] = None
    exclude_ids: Optional[List[int]] = []


# 答案评分请求
class ScoreAnswerRequest(BaseModel):
    question_id: int
    user_answer: str
    mastery_level: Optional[str] = None
    time_spent: Optional[int] = None


# 答案评分响应
class ScoreAnswerResponse(BaseModel):
    practice_record_id: int
    ai_score: Decimal
    ai_feedback: str
    reference_answer: str
    keywords: Optional[str] = None


# 统计信息
class StatisticsResponse(BaseModel):
    total_questions: int
    answered_questions: int
    practiced_questions: int
    mastery_stats: dict
    domain_stats: dict


# 面试笔记相关
class InterviewNoteCreate(BaseModel):
    title: str
    content: str
    note_type: Optional[str] = '心得'
    tags: Optional[str] = None


class InterviewNoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: Optional[str] = None
    tags: Optional[str] = None


class InterviewNoteResponse(BaseModel):
    id: int
    title: str
    content: str
    note_type: str
    tags: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 面试日程相关
class InterviewScheduleCreate(BaseModel):
    company_name: str
    position_name: str
    interview_time: datetime
    interview_type: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = '待面试'
    notes: Optional[str] = None


class InterviewScheduleUpdate(BaseModel):
    company_name: Optional[str] = None
    position_name: Optional[str] = None
    interview_time: Optional[datetime] = None
    interview_type: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class InterviewScheduleResponse(BaseModel):
    id: int
    company_name: str
    position_name: str
    interview_time: datetime
    interview_type: Optional[str] = None
    location: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 岗位分析相关
class JobAnalysisCreate(BaseModel):
    job_title: str
    company_name: Optional[str] = None
    jd_content: str


class JobAnalysisResponse(BaseModel):
    id: int
    job_title: str
    company_name: Optional[str] = None
    jd_content: str
    analysis_result: Optional[str] = None
    key_requirements: Optional[str] = None
    recommended_questions: Optional[str] = None
    analysis_status: str = 'pending'  # pending/processing/completed/failed
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
