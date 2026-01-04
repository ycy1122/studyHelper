"""
使用示例：演示如何使用question_parser工具模块
"""
from question_parser import QuestionParser, DatabaseManager
from config import (
    QWEN_API_KEY,
    QWEN_BASE_URL,
    QWEN_MODEL,
    QUESTION_EXTRACTION_PROMPT,
    DATABASE_URL
)

def example_1_parse_single_text():
    """示例1：解析单个文本"""
    print("=" * 80)
    print("示例1：解析单个文本")
    print("=" * 80)

    # 初始化解析器
    parser = QuestionParser(
        api_key=QWEN_API_KEY,
        base_url=QWEN_BASE_URL,
        model=QWEN_MODEL,
        prompt_template=QUESTION_EXTRACTION_PROMPT
    )

    # 测试文本
    text = """
    一面：
    1. 介绍一下Transformer的结构
    2. Attention机制的计算过程
    3. 为什么要除以根号dk
    4. 介绍一下你的项目
    """

    # 解析问题
    questions = parser.parse_questions(text)

    print(f"\n原始文本：{text}")
    print(f"\n识别到 {len(questions)} 个问题：")
    for idx, q in enumerate(questions, 1):
        print(f"{idx}. {q}")


def example_2_save_to_database():
    """示例2：解析并保存到数据库"""
    print("\n" + "=" * 80)
    print("示例2：解析并保存到数据库")
    print("=" * 80)

    # 初始化解析器和数据库
    parser = QuestionParser(
        api_key=QWEN_API_KEY,
        base_url=QWEN_BASE_URL,
        model=QWEN_MODEL,
        prompt_template=QUESTION_EXTRACTION_PROMPT
    )

    db = DatabaseManager(DATABASE_URL)

    # 测试数据
    text = "1.什么是RAG？ 2.什么是Agent？ 3.如何评估模型性能？"
    source_title = "AI面试题目示例"

    # 解析问题
    questions = parser.parse_questions(text)

    # 构造记录
    records = []
    for idx, question in enumerate(questions, 1):
        record = {
            'source_title': source_title,
            'question': question,
            'question_index': idx,
            'original_text': text
        }
        records.append(record)

    # 保存到数据库
    inserted_count = db.insert_questions(records)
    print(f"\n成功插入 {inserted_count} 条记录")

    # 查询数据库总数
    total = db.get_question_count()
    print(f"数据库中问题总数: {total}")


def example_3_batch_parse():
    """示例3：批量解析多个文本"""
    print("\n" + "=" * 80)
    print("示例3：批量解析多个文本")
    print("=" * 80)

    parser = QuestionParser(
        api_key=QWEN_API_KEY,
        base_url=QWEN_BASE_URL,
        model=QWEN_MODEL,
        prompt_template=QUESTION_EXTRACTION_PROMPT
    )

    # 多个文本
    texts = [
        "1.介绍LoRA原理 2.介绍DPO算法",
        "如何优化大模型推理速度？",
        "一面：项目介绍、八股、算法题"
    ]

    # 批量解析
    results = parser.batch_parse(texts)

    for idx, (text, questions) in enumerate(zip(texts, results), 1):
        print(f"\n文本{idx}: {text[:50]}...")
        print(f"识别到问题: {questions}")


def example_4_query_database():
    """示例4：查询数据库"""
    print("\n" + "=" * 80)
    print("示例4：查询数据库中的问题")
    print("=" * 80)

    from sqlalchemy import create_engine, select, text

    engine = create_engine(DATABASE_URL)

    # 查询最近的10个问题
    query = text("""
        SELECT source_title, question, question_index, created_at
        FROM interview_questions
        ORDER BY created_at DESC
        LIMIT 10
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

    print(f"\n数据库中最近的10个问题：")
    for row in rows:
        print(f"\n标题: {row[0]}")
        print(f"问题: {row[1]}")
        print(f"序号: {row[2]}")
        print(f"时间: {row[3]}")


if __name__ == "__main__":
    # 运行示例1：解析单个文本
    example_1_parse_single_text()

    # 运行示例2：保存到数据库（如果需要，取消注释）
    # example_2_save_to_database()

    # 运行示例3：批量解析（如果需要，取消注释）
    # example_3_batch_parse()

    # 运行示例4：查询数据库（如果需要，取消注释）
    # example_4_query_database()

    print("\n" + "=" * 80)
    print("示例运行完成！")
    print("=" * 80)
