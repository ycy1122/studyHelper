"""
SQLAlchemy数据模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, DECIMAL, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class SourceQuestion(Base):
    """原始问题表"""
    __tablename__ = "source_questions"

    id = Column(Integer, primary_key=True, index=True)
    source_title = Column(String(500))
    original_text = Column(Text, nullable=False, unique=True)
    is_extracted = Column(Boolean, default=False, index=True)
    detail_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    detail_questions = relationship("InterviewQuestion", back_populates="source_question")


class InterviewQuestion(Base):
    """明细问题表"""
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    source_title = Column(String(500))
    question = Column(Text, nullable=False, unique=True)
    question_index = Column(Integer)
    original_text = Column(Text)
    has_answer = Column(Boolean, default=False, index=True)
    answer = Column(Text)
    keywords = Column(Text)
    domain = Column(String(50), index=True)
    refined_question = Column(Text)  # 改写后的问题（更通顺清晰）
    source_question_id = Column(Integer, ForeignKey('source_questions.id', ondelete='SET NULL'), index=True)
    latest_mastery_level = Column(String(20), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    source_question = relationship("SourceQuestion", back_populates="detail_questions")
    practice_records = relationship("PracticeRecord", back_populates="question")


class PracticeRecord(Base):
    """练习记录表"""
    __tablename__ = "practice_records"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey('interview_questions.id', ondelete='CASCADE'), nullable=False, index=True)
    user_answer = Column(Text)
    ai_score = Column(DECIMAL(5, 2))
    ai_feedback = Column(Text)
    mastery_level = Column(String(20), index=True)
    practice_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    time_spent = Column(Integer)

    # 关系
    question = relationship("InterviewQuestion", back_populates="practice_records")


class InterviewNote(Base):
    """面试笔记/心得记录表"""
    __tablename__ = "interview_notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)  # 笔记标题
    content = Column(Text, nullable=False)  # 笔记内容（面试录音转文本、心得等）
    note_type = Column(String(50), default='心得', index=True)  # 类型：心得、面试记录
    tags = Column(String(500))  # 标签，逗号分隔
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InterviewSchedule(Base):
    """面试日程表"""
    __tablename__ = "interview_schedules"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), nullable=False)  # 公司名称
    position_name = Column(String(200), nullable=False)  # 岗位名称
    interview_time = Column(DateTime(timezone=True), nullable=False, index=True)  # 面试时间
    interview_type = Column(String(50))  # 面试类型：电话面试、视频面试、现场面试
    location = Column(String(500))  # 面试地点/链接
    status = Column(String(50), default='待面试', index=True)  # 状态：待面试、已完成、已取消
    notes = Column(Text)  # 备注
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobAnalysis(Base):
    """岗位分析表"""
    __tablename__ = "job_analyses"

    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String(200), nullable=False)  # 岗位名称
    company_name = Column(String(200))  # 公司名称
    jd_content = Column(Text, nullable=False)  # 岗位JD原文
    analysis_result = Column(Text)  # 分析结果（面试准备计划）
    key_requirements = Column(Text)  # 提取的关键要求
    recommended_questions = Column(Text)  # 推荐练习的题目ID列表（JSON）
    analysis_status = Column(String(20), default='pending', index=True)  # 分析状态：pending/processing/completed/failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
