"""
答案生成模块 - 使用Qwen生成问题的答案、关键词和领域分类
"""
import json
import logging
from typing import Dict, Optional
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 领域分类
VALID_DOMAINS = [
    '大模型',
    'RAG',
    '记忆管理',
    'Langchain语法',
    '智能体框架',
    '效果评测',
    '工程化部署实践',
    '其他'
]

# 答案生成提示词模板
ANSWER_GENERATION_PROMPT = """你是一个专业的AI技术专家，擅长回答大模型、RAG、智能体等相关技术问题。

请针对以下面试问题，生成详细的答案，并提取关键词和领域分类。

问题：{question}

要求：
1. 答案要专业、准确、全面，适合面试场景
2. 关键词：提取3-5个核心技术关键词，用逗号分隔
3. 领域分类：从以下选项中选择最匹配的一个
   - 大模型：关于大语言模型的训练、推理、优化等
   - RAG：检索增强生成相关技术
   - 记忆管理：对话记忆、上下文管理等
   - Langchain语法：Langchain框架的语法和使用
   - 智能体框架：Agent架构、工具调用、多智能体等
   - 效果评测：模型评估、指标、测试方法等
   - 工程化部署实践：模型部署、服务化、性能优化等
   - 其他：其他AI相关技术

请以JSON格式返回，格式如下：
{{
    "answer": "详细的答案内容...",
    "keywords": "关键词1,关键词2,关键词3",
    "domain": "领域分类"
}}

只返回JSON对象，不要有其他说明文字。
"""


class AnswerGenerator:
    """答案生成器 - 使用Qwen生成答案、关键词和领域分类"""

    def __init__(self, api_key: str, base_url: str, model: str):
        """
        初始化答案生成器

        Args:
            api_key: Qwen API密钥
            base_url: API基础URL
            model: 使用的模型名称
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
        logger.info(f"AnswerGenerator初始化完成，使用模型: {model}")

    def generate_answer(self, question: str, max_retries: int = 3) -> Optional[Dict[str, str]]:
        """
        为问题生成答案

        Args:
            question: 问题文本
            max_retries: 最大重试次数

        Returns:
            包含answer、keywords、domain的字典，失败返回None
        """
        if not question or not question.strip():
            logger.warning("问题文本为空")
            return None

        # 构造提示词
        prompt = ANSWER_GENERATION_PROMPT.format(question=question)

        for attempt in range(max_retries):
            try:
                logger.info(f"生成答案 (尝试 {attempt + 1}/{max_retries})...")

                # 调用Qwen API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的AI技术专家和面试官，擅长回答技术问题。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,  # 适中的温度以平衡准确性和创造性
                    response_format={"type": "json_object"}  # 强制返回JSON格式
                )

                # 提取响应内容
                content = response.choices[0].message.content.strip()
                logger.debug(f"API返回内容: {content[:200]}...")

                # 解析JSON
                result = json.loads(content)

                # 验证必需字段
                if 'answer' not in result or 'keywords' not in result or 'domain' not in result:
                    logger.warning(f"返回的JSON缺少必需字段: {result.keys()}")
                    continue

                # 验证领域分类
                domain = result['domain']
                if domain not in VALID_DOMAINS:
                    logger.warning(f"无效的领域分类: {domain}，设置为'其他'")
                    result['domain'] = '其他'

                # 确保答案和关键词不为空
                if not result['answer'].strip():
                    logger.warning("生成的答案为空")
                    continue

                if not result['keywords'].strip():
                    logger.warning("生成的关键词为空")
                    result['keywords'] = '未分类'

                logger.info(f"成功生成答案，领域: {result['domain']}, 关键词: {result['keywords'][:50]}...")
                return {
                    'answer': result['answer'].strip(),
                    'keywords': result['keywords'].strip(),
                    'domain': result['domain'].strip()
                }

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                logger.error(f"原始内容: {content if 'content' in locals() else 'N/A'}")

            except Exception as e:
                logger.error(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")

        logger.error(f"生成答案失败，已重试{max_retries}次")
        return None

    def batch_generate(self, questions: list) -> list:
        """
        批量生成答案

        Args:
            questions: 问题列表，每个元素是包含id和question的字典

        Returns:
            结果列表，每个元素包含id、answer、keywords、domain
        """
        results = []
        total = len(questions)

        for idx, q in enumerate(questions, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"处理进度: {idx}/{total}")
            logger.info(f"问题ID: {q['id']}")
            logger.info(f"问题内容: {q['question'][:100]}...")

            result = self.generate_answer(q['question'])

            if result:
                results.append({
                    'id': q['id'],
                    **result
                })
                logger.info(f"✓ 成功生成答案")
            else:
                logger.warning(f"✗ 生成答案失败")

        logger.info(f"\n批量生成完成，成功: {len(results)}/{total}")
        return results
