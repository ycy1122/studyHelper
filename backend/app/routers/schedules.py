"""
面试日程管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from app import schemas, models
from app.database import get_db

router = APIRouter(prefix="/schedules", tags=["面试日程"])


@router.post("/", response_model=schemas.InterviewScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule: schemas.InterviewScheduleCreate,
    db: Session = Depends(get_db)
):
    """创建面试日程"""
    db_schedule = models.InterviewSchedule(**schedule.dict())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


@router.get("/", response_model=List[schemas.InterviewScheduleResponse])
def list_schedules(
    status_filter: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取面试日程列表"""
    query = db.query(models.InterviewSchedule)

    if status_filter:
        query = query.filter(models.InterviewSchedule.status == status_filter)

    query = query.order_by(models.InterviewSchedule.interview_time.asc())
    schedules = query.offset(skip).limit(limit).all()

    return schedules


@router.get("/upcoming", response_model=List[schemas.InterviewScheduleResponse])
def get_upcoming_schedules(days: int = 7, db: Session = Depends(get_db)):
    """获取未来N天的面试日程"""
    now = datetime.now()
    future = now + timedelta(days=days)

    schedules = db.query(models.InterviewSchedule).filter(
        models.InterviewSchedule.interview_time >= now,
        models.InterviewSchedule.interview_time <= future,
        models.InterviewSchedule.status == '待面试'
    ).order_by(
        models.InterviewSchedule.interview_time.asc()
    ).all()

    return schedules


@router.get("/{schedule_id}", response_model=schemas.InterviewScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """获取单个面试日程"""
    schedule = db.query(models.InterviewSchedule).filter(
        models.InterviewSchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试日程不存在"
        )

    return schedule


@router.put("/{schedule_id}", response_model=schemas.InterviewScheduleResponse)
def update_schedule(
    schedule_id: int,
    schedule_update: schemas.InterviewScheduleUpdate,
    db: Session = Depends(get_db)
):
    """更新面试日程"""
    db_schedule = db.query(models.InterviewSchedule).filter(
        models.InterviewSchedule.id == schedule_id
    ).first()

    if not db_schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试日程不存在"
        )

    # 更新字段
    for field, value in schedule_update.dict(exclude_unset=True).items():
        setattr(db_schedule, field, value)

    db.commit()
    db.refresh(db_schedule)

    return db_schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """删除面试日程"""
    db_schedule = db.query(models.InterviewSchedule).filter(
        models.InterviewSchedule.id == schedule_id
    ).first()

    if not db_schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试日程不存在"
        )

    db.delete(db_schedule)
    db.commit()

    return None
