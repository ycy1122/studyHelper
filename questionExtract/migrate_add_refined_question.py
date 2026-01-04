"""
数据库迁移：添加refined_question字段
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
from config import DATABASE_URL

def migrate():
    # 解析数据库URL
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', DATABASE_URL)
    if not match:
        print("❌ 数据库URL格式错误")
        return

    user, password, host, port, database = match.groups()

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        print("=" * 80)
        print("数据库迁移：添加refined_question字段")
        print("=" * 80)
        print()

        # 检查字段是否已存在
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='interview_questions' AND column_name='refined_question'
        """)

        if cursor.fetchone():
            print("✓ refined_question 字段已存在，无需迁移")
        else:
            print("[1/1] 添加 refined_question 字段...")
            cursor.execute("""
                ALTER TABLE interview_questions
                ADD COLUMN refined_question TEXT
            """)
            conn.commit()
            print("✓ 字段添加成功")

        print()
        print("=" * 80)
        print("迁移完成！")
        print("=" * 80)

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        if 'conn' in locals():
            conn.rollback()

if __name__ == "__main__":
    migrate()
