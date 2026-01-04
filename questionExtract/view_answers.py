"""
查看生成的答案示例
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import create_engine, text
from config import DATABASE_URL

def main():
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()

    # 查询已生成答案的问题
    result = conn.execute(text("""
        SELECT id, question, answer, keywords, domain
        FROM interview_questions
        WHERE has_answer = TRUE
        ORDER BY id
        LIMIT 3
    """))
    rows = result.fetchall()
    conn.close()

    print("=" * 80)
    print("生成的答案示例")
    print("=" * 80)

    for idx, row in enumerate(rows, 1):
        print(f"\n【示例 {idx}】")
        print(f"ID: {row[0]}")
        print(f"问题: {row[1]}")
        print(f"\n答案:\n{row[2]}")
        print(f"\n关键词: {row[3]}")
        print(f"领域: {row[4]}")
        print("-" * 80)

if __name__ == "__main__":
    main()
