"""
面试笔记管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app import schemas, models
from app.database import get_db

router = APIRouter(prefix="/notes", tags=["面试笔记"])


@router.post("/", response_model=schemas.InterviewNoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    note: schemas.InterviewNoteCreate,
    db: Session = Depends(get_db)
):
    """创建笔记"""
    db_note = models.InterviewNote(**note.dict())
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


@router.get("/", response_model=List[schemas.InterviewNoteResponse])
def list_notes(
    note_type: str = None,
    search: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    获取笔记列表

    支持按类型和关键字搜索（标题+内容）
    """
    query = db.query(models.InterviewNote)

    # 按类型筛选
    if note_type:
        query = query.filter(models.InterviewNote.note_type == note_type)

    # 关键字搜索（标题或内容）
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.InterviewNote.title.ilike(search_pattern)) |
            (models.InterviewNote.content.ilike(search_pattern))
        )

    query = query.order_by(models.InterviewNote.created_at.desc())
    notes = query.offset(skip).limit(limit).all()

    return notes


@router.get("/{note_id}", response_model=schemas.InterviewNoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)):
    """获取单个笔记"""
    note = db.query(models.InterviewNote).filter(
        models.InterviewNote.id == note_id
    ).first()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔记不存在"
        )

    return note


@router.put("/{note_id}", response_model=schemas.InterviewNoteResponse)
def update_note(
    note_id: int,
    note_update: schemas.InterviewNoteUpdate,
    db: Session = Depends(get_db)
):
    """更新笔记"""
    db_note = db.query(models.InterviewNote).filter(
        models.InterviewNote.id == note_id
    ).first()

    if not db_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔记不存在"
        )

    # 更新字段
    for field, value in note_update.dict(exclude_unset=True).items():
        setattr(db_note, field, value)

    db.commit()
    db.refresh(db_note)

    return db_note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    """删除笔记"""
    db_note = db.query(models.InterviewNote).filter(
        models.InterviewNote.id == note_id
    ).first()

    if not db_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔记不存在"
        )

    db.delete(db_note)
    db.commit()

    return None
