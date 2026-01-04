"""
问题解析工具模块 - 可复用的工具类
"""
import json
import re
from typing import List, Dict, Optional
from openai import OpenAI
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuestionParser:
    """问题解析器 - 使用Qwen模型识别和提取问题"""

    def __init__(self, api_key: str, base_url: str, model: str, prompt_template: str):
        """
        初始化问题解析器

        Args:
            api_key: Qwen API密钥
            base_url: API基础URL
            model: 使用的模型名称
            prompt_template: 提示词模板
        """
        import httpx
        # 创建httpx客户端
        http_client = httpx.Client(timeout=60.0)
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )
        self.model = model
        self.prompt_template = prompt_template
        logger.info(f"QuestionParser初始化完成，使用模型: {model}")

    def parse_questions(self, text: str, max_retries: int = 3) -> List[str]:
        """
        解析文本中的问题

        Args:
            text: 待解析的文本
            max_retries: 最大重试次数

        Returns:
            问题列表
        """
        if not text or not text.strip():
            logger.warning("输入文本为空")
            return []

        # 构造提示词
        prompt = self.prompt_template.format(text=text)

        for attempt in range(max_retries):
            try:
                logger.info(f"调用Qwen API (尝试 {attempt + 1}/{max_retries})...")

                # 调用Qwen API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的面试题目分析助手，擅长从文本中提取问题。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,  # 降低温度以获得更稳定的输出
                    response_format={"type": "json_object"}  # 强制返回JSON格式
                )

                # 提取响应内容
                content = response.choices[0].message.content.strip()
                logger.debug(f"API返回内容: {content}")

                # 解析JSON
                result = json.loads(content)

                # 提取questions字段
                questions = result.get('questions', [])

                if not isinstance(questions, list):
                    logger.warning(f"返回的questions不是列表类型: {type(questions)}")
                    continue

                # 过滤空字符串
                questions = [q.strip() for q in questions if q and q.strip()]

                logger.info(f"成功识别到 {len(questions)} 个问题")
                return questions

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                logger.error(f"原始内容: {content if 'content' in locals() else 'N/A'}")

                # 尝试从非标准JSON中提取
                try:
                    questions = self._extract_questions_fallback(content if 'content' in locals() else '')
                    if questions:
                        logger.info(f"通过备用方法识别到 {len(questions)} 个问题")
                        return questions
                except Exception as fallback_error:
                    logger.error(f"备用提取方法也失败: {fallback_error}")

            except Exception as e:
                logger.error(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")

        logger.error(f"解析失败，已重试{max_retries}次")
        return []

    def _extract_questions_fallback(self, text: str) -> List[str]:
        """
        备用方法：从非标准JSON中提取问题

        Args:
            text: 待解析的文本

        Returns:
            问题列表
        """
        # 尝试匹配JSON数组
        match = re.search(r'\[([^\]]+)\]', text, re.DOTALL)
        if match:
            array_content = match.group(1)
            # 提取引号中的内容
            questions = re.findall(r'"([^"]+)"', array_content)
            return questions
        return []

    def batch_parse(self, texts: List[str], batch_size: int = 10) -> List[List[str]]:
        """
        批量解析多个文本

        Args:
            texts: 文本列表
            batch_size: 批次大小（预留参数，当前逐个处理）

        Returns:
            问题列表的列表
        """
        results = []
        total = len(texts)

        for idx, text in enumerate(texts, 1):
            logger.info(f"处理进度: {idx}/{total}")
            questions = self.parse_questions(text)
            results.append(questions)

        return results


class DatabaseManager:
    """数据库管理器 - 负责数据库操作"""

    def __init__(self, database_url: str):
        """
        初始化数据库管理器

        Args:
            database_url: 数据库连接URL
        """
        from sqlalchemy import create_engine, Table, Column, Integer, String, Text, DateTime, Boolean, MetaData
        from sqlalchemy.sql import func

        self.engine = create_engine(database_url, echo=False)
        self.metadata = MetaData()

        # 定义表结构（包含新字段）
        self.interview_questions = Table(
            'interview_questions',
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('source_title', String(500), comment='原始标题'),
            Column('question', Text, nullable=False, comment='单个问题'),
            Column('question_index', Integer, comment='问题在原始文本中的序号'),
            Column('original_text', Text, comment='原始题目文本（用于追溯）'),
            Column('has_answer', Boolean, default=False, comment='是否已生成答案'),
            Column('answer', Text, comment='答案内容'),
            Column('keywords', Text, comment='关键词（逗号分隔）'),
            Column('domain', String(50), comment='领域分类'),
            Column('refined_question', Text, comment='改写后的问题（更通顺清晰）'),
            Column('created_at', DateTime, server_default=func.now(), comment='创建时间')
        )

        logger.info("DatabaseManager初始化完成")

    def create_tables(self):
        """创建数据表"""
        self.metadata.create_all(self.engine)
        logger.info("数据表创建成功")

    def insert_questions(self, records: List[Dict]) -> int:
        """
        批量插入问题记录

        Args:
            records: 记录列表，每条记录包含source_title, question, question_index, original_text

        Returns:
            插入的记录数
        """
        if not records:
            logger.warning("没有记录需要插入")
            return 0

        with self.engine.begin() as conn:
            result = conn.execute(self.interview_questions.insert(), records)
            inserted_count = result.rowcount

        logger.info(f"成功插入 {inserted_count} 条记录")
        return inserted_count

    def get_question_count(self) -> int:
        """获取数据库中的问题总数"""
        from sqlalchemy import select, func

        with self.engine.connect() as conn:
            result = conn.execute(
                select(func.count()).select_from(self.interview_questions)
            )
            count = result.scalar()

        return count

    def get_unanswered_questions(self, limit: int = None) -> List[Dict]:
        """
        获取未生成答案的问题

        Args:
            limit: 限制返回数量，None表示返回所有

        Returns:
            问题记录列表
        """
        from sqlalchemy import select, or_

        query = select(
            self.interview_questions.c.id,
            self.interview_questions.c.question,
            self.interview_questions.c.source_title
        ).where(
            or_(
                self.interview_questions.c.has_answer == False,
                self.interview_questions.c.has_answer == None
            )
        )

        if limit:
            query = query.limit(limit)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()

        questions = []
        for row in rows:
            questions.append({
                'id': row[0],
                'question': row[1],
                'source_title': row[2]
            })

        return questions

    def update_answer(self, question_id: int, answer: str, keywords: str, domain: str) -> bool:
        """
        更新问题的答案和相关信息

        Args:
            question_id: 问题ID
            answer: 答案内容
            keywords: 关键词（逗号分隔）
            domain: 领域分类

        Returns:
            是否更新成功
        """
        from sqlalchemy import update

        try:
            with self.engine.begin() as conn:
                stmt = update(self.interview_questions).where(
                    self.interview_questions.c.id == question_id
                ).values(
                    has_answer=True,
                    answer=answer,
                    keywords=keywords,
                    domain=domain
                )
                result = conn.execute(stmt)
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"更新答案失败: {e}")
            return False

    def get_answered_count(self) -> int:
        """获取已生成答案的问题数量"""
        from sqlalchemy import select, func

        with self.engine.connect() as conn:
            result = conn.execute(
                select(func.count()).select_from(self.interview_questions).where(
                    self.interview_questions.c.has_answer == True
                )
            )
            count = result.scalar()

        return count

    def get_questions_without_refined(self, limit: int = None) -> List[tuple]:
        """
        获取所有未改写的问题（refined_question为NULL）

        Args:
            limit: 限制返回数量

        Returns:
            [(question_id, question_text), ...]
        """
        from sqlalchemy import select

        with self.engine.connect() as conn:
            query = select(
                self.interview_questions.c.id,
                self.interview_questions.c.question
            ).where(
                self.interview_questions.c.refined_question == None
            ).order_by(
                self.interview_questions.c.id
            )

            if limit:
                query = query.limit(limit)

            result = conn.execute(query)
            return [(row[0], row[1]) for row in result]

    def update_refined_question(self, question_id: int, refined_question: str) -> bool:
        """
        更新问题的改写版本

        Args:
            question_id: 问题ID
            refined_question: 改写后的问题

        Returns:
            是否更新成功
        """
        from sqlalchemy import update

        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    update(self.interview_questions).where(
                        self.interview_questions.c.id == question_id
                    ).values(
                        refined_question=refined_question
                    )
                )
                conn.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"更新改写问题失败: {e}")
            return False
