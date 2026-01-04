"""
数据库迁移脚本 - 添加新表
添加：
1. interview_notes - 面试笔记表
2. interview_schedules - 面试日程表
3. job_analyses - 岗位分析表
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app import models

def migrate():
    """执行迁移"""
    print("=" * 80)
    print("开始数据库迁移 - 添加新表")
    print("=" * 80)

    try:
        # 创建所有表（已存在的会跳过）
        Base.metadata.create_all(bind=engine)

        print("\n[SUCCESS] Migration completed!")
        print("\nNew tables added:")
        print("  - interview_notes")
        print("  - interview_schedules")
        print("  - job_analyses")
        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        print("=" * 80)
        raise


if __name__ == "__main__":
    migrate()
