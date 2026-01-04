"""
答案生成功能测试脚本
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from answer_generator import AnswerGenerator
from question_parser import DatabaseManager
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, DATABASE_URL

print("=" * 80)
print("答案生成功能测试")
print("=" * 80)

# 测试1: 初始化
print("\n[测试1] 初始化组件...")
try:
    generator = AnswerGenerator(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)
    db = DatabaseManager(DATABASE_URL)
    print("✓ 初始化成功")
except Exception as e:
    print(f"✗ 初始化失败: {e}")
    sys.exit(1)

# 测试2: 查询统计
print("\n[测试2] 查询数据库统计...")
try:
    total = db.get_question_count()
    answered = db.get_answered_count()
    unanswered = total - answered
    print(f"✓ 总问题数: {total}")
    print(f"✓ 已生成答案: {answered}")
    print(f"✓ 待生成答案: {unanswered}")
except Exception as e:
    print(f"✗ 查询失败: {e}")

# 测试3: 单个答案生成
print("\n[测试3] 生成单个问题的答案...")
try:
    test_question = "什么是Attention机制？"
    print(f"问题: {test_question}")

    result = generator.generate_answer(test_question)

    if result:
        print("✓ 答案生成成功")
        print(f"\n答案（前200字）:\n{result['answer'][:200]}...")
        print(f"\n关键词: {result['keywords']}")
        print(f"领域: {result['domain']}")
    else:
        print("✗ 答案生成失败")
except Exception as e:
    print(f"✗ 测试失败: {e}")

# 测试4: 获取未生成答案的问题
print("\n[测试4] 获取未生成答案的问题...")
try:
    questions = db.get_unanswered_questions(limit=3)
    print(f"✓ 成功获取 {len(questions)} 个未生成答案的问题")

    if questions:
        print("\n示例问题:")
        for i, q in enumerate(questions[:3], 1):
            print(f"{i}. [ID:{q['id']}] {q['question'][:60]}...")
except Exception as e:
    print(f"✗ 获取失败: {e}")

# 测试5: 验证领域约束
print("\n[测试5] 验证领域分类...")
from answer_generator import VALID_DOMAINS
print(f"✓ 支持的领域: {', '.join(VALID_DOMAINS)}")

# 测试6: 查看已生成的答案示例
print("\n[测试6] 查看已生成的答案示例...")
try:
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT question, keywords, domain
            FROM interview_questions
            WHERE has_answer = TRUE
            LIMIT 3
        """))
        rows = result.fetchall()

    if rows:
        print(f"✓ 找到 {len(rows)} 个已生成答案的问题")
        for i, row in enumerate(rows, 1):
            print(f"\n{i}. {row[0][:60]}...")
            print(f"   关键词: {row[1]}")
            print(f"   领域: {row[2]}")
    else:
        print("  还没有生成任何答案")
except Exception as e:
    print(f"✗ 查询失败: {e}")

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)

print("\n快速使用指南：")
print("1. 批量生成答案: python generate_answers.py --max 10")
print("2. 查看答案示例: python view_answers.py")
print("3. 数据库迁移: python migrate_database.py")
print("4. 详细文档: README_ANSWER_GENERATION.md")
