"""
面试题目提取工具包

主要功能：
- 使用Qwen大模型识别和提取面试题目
- 将识别的题目保存到PostgreSQL数据库
- 为问题生成答案、关键词和领域分类
- 提供查询和统计功能

核心模块：
- question_parser: QuestionParser（问题解析器）和 DatabaseManager（数据库管理器）
- answer_generator: AnswerGenerator（答案生成器）
- config: 配置信息（API密钥、数据库连接等）
- process_questions: 问题提取脚本
- generate_answers: 答案生成脚本
- query_questions: 数据库查询工具

使用示例：
    from questionExtract import QuestionParser, DatabaseManager, AnswerGenerator
    from questionExtract.config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, QUESTION_EXTRACTION_PROMPT

    # 提取问题
    parser = QuestionParser(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, QUESTION_EXTRACTION_PROMPT)
    questions = parser.parse_questions("1.什么是RAG？ 2.什么是Agent？")

    # 生成答案
    generator = AnswerGenerator(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)
    result = generator.generate_answer("什么是RAG？")
    print(result)  # {'answer': '...', 'keywords': '...', 'domain': '...'}
"""

from .question_parser import QuestionParser, DatabaseManager
from .answer_generator import AnswerGenerator

__version__ = "2.0.0"
__all__ = ["QuestionParser", "DatabaseManager", "AnswerGenerator"]
