"""
数据库查询工具 - 方便查看和分析已解析的问题
"""
import sys
from sqlalchemy import create_engine, text
from config import DATABASE_URL

sys.stdout.reconfigure(encoding='utf-8')


def get_total_count():
    """获取问题总数"""
    engine = create_engine(DATABASE_URL)
    query = text("SELECT COUNT(*) FROM interview_questions")

    with engine.connect() as conn:
        result = conn.execute(query)
        count = result.scalar()

    return count


def get_recent_questions(limit=10):
    """获取最近的问题"""
    engine = create_engine(DATABASE_URL)
    query = text("""
        SELECT id, source_title, question, question_index, created_at
        FROM interview_questions
        ORDER BY created_at DESC
        LIMIT :limit
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {'limit': limit})
        rows = result.fetchall()

    return rows


def get_questions_by_title(title_keyword):
    """根据标题关键词搜索"""
    engine = create_engine(DATABASE_URL)
    query = text("""
        SELECT id, source_title, question, question_index
        FROM interview_questions
        WHERE source_title LIKE :keyword
        ORDER BY created_at DESC
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {'keyword': f'%{title_keyword}%'})
        rows = result.fetchall()

    return rows


def get_questions_by_keyword(keyword):
    """根据问题内容关键词搜索"""
    engine = create_engine(DATABASE_URL)
    query = text("""
        SELECT id, source_title, question, question_index
        FROM interview_questions
        WHERE question LIKE :keyword
        ORDER BY created_at DESC
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {'keyword': f'%{keyword}%'})
        rows = result.fetchall()

    return rows


def get_statistics():
    """获取统计信息"""
    engine = create_engine(DATABASE_URL)

    # 总问题数
    total_query = text("SELECT COUNT(*) FROM interview_questions")

    # 不同标题数
    titles_query = text("SELECT COUNT(DISTINCT source_title) FROM interview_questions")

    # 平均每个标题的问题数
    avg_query = text("""
        SELECT AVG(question_count) as avg_questions
        FROM (
            SELECT source_title, COUNT(*) as question_count
            FROM interview_questions
            GROUP BY source_title
        ) as subquery
    """)

    with engine.connect() as conn:
        total = conn.execute(total_query).scalar()
        titles = conn.execute(titles_query).scalar()
        avg = conn.execute(avg_query).scalar()

    return {
        'total_questions': total,
        'unique_titles': titles,
        'avg_questions_per_title': round(avg, 2) if avg else 0
    }


def main():
    """主函数 - 交互式查询"""
    print("=" * 80)
    print("面试题目数据库查询工具")
    print("=" * 80)

    while True:
        print("\n请选择操作：")
        print("1. 查看统计信息")
        print("2. 查看最近的问题")
        print("3. 按标题关键词搜索")
        print("4. 按问题内容关键词搜索")
        print("5. 退出")

        choice = input("\n请输入选项 (1-5): ").strip()

        if choice == '1':
            stats = get_statistics()
            print("\n统计信息：")
            print(f"  问题总数: {stats['total_questions']}")
            print(f"  不同标题数: {stats['unique_titles']}")
            print(f"  平均每个标题问题数: {stats['avg_questions_per_title']}")

        elif choice == '2':
            limit = input("请输入要查看的数量 (默认10): ").strip()
            limit = int(limit) if limit.isdigit() else 10

            rows = get_recent_questions(limit)
            print(f"\n最近的 {len(rows)} 个问题：")
            for row in rows:
                print(f"\n[ID: {row[0]}] {row[1]}")
                print(f"  问题{row[3]}: {row[2][:100]}{'...' if len(row[2]) > 100 else ''}")
                print(f"  时间: {row[4]}")

        elif choice == '3':
            keyword = input("请输入标题关键词: ").strip()
            if keyword:
                rows = get_questions_by_title(keyword)
                print(f"\n找到 {len(rows)} 个相关问题：")
                for row in rows:
                    print(f"\n[ID: {row[0]}] {row[1]}")
                    print(f"  问题{row[3]}: {row[2][:100]}{'...' if len(row[2]) > 100 else ''}")

        elif choice == '4':
            keyword = input("请输入问题内容关键词: ").strip()
            if keyword:
                rows = get_questions_by_keyword(keyword)
                print(f"\n找到 {len(rows)} 个相关问题：")
                for row in rows:
                    print(f"\n[ID: {row[0]}] {row[1]}")
                    print(f"  问题{row[3]}: {row[2][:100]}{'...' if len(row[2]) > 100 else ''}")

        elif choice == '5':
            print("\n再见！")
            break

        else:
            print("\n无效的选项，请重新输入")


if __name__ == "__main__":
    try:
        # 先显示统计信息
        stats = get_statistics()
        print(f"\n当前数据库统计：")
        print(f"  问题总数: {stats['total_questions']}")
        print(f"  不同标题数: {stats['unique_titles']}")
        print(f"  平均每个标题问题数: {stats['avg_questions_per_title']}")

        # 显示最近5个问题作为示例
        print(f"\n最近的5个问题示例：")
        rows = get_recent_questions(5)
        for row in rows:
            print(f"\n标题: {row[1][:50]}...")
            print(f"问题: {row[2][:80]}...")

        # 进入交互模式
        print("\n" + "=" * 80)
        user_input = input("\n是否进入交互查询模式？(y/n): ").strip().lower()
        if user_input == 'y':
            main()

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
