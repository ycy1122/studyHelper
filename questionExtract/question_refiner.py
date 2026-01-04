"""
问题改写模块 - 使用AI将拗口的问题改写得更通顺清晰
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from openai import OpenAI
import json
from typing import Optional
import time

# 问题改写提示词
QUESTION_REFINE_PROMPT = """你是一个专业的文本编辑助手。请将以下面试问题改写得更通顺、更清晰。

要求：
1. 保持问题的核心含义不变
2. 使用更规范、更流畅的语言表达
3. 如果问题包含多个子问题，请分点列出（使用换行和序号）
4. 去除冗余词汇和拗口的表达
5. 专业术语保持不变
6. 如果问题已经很清晰，可以保持原样或略作润色

原始问题：
{question}

请以JSON格式返回改写后的问题：
{{
    "refined_question": "改写后的问题内容"
}}

只返回JSON对象，不要其他说明。
"""


class QuestionRefiner:
    """问题改写器"""

    def __init__(self, api_key: str, base_url: str, model: str):
        """初始化问题改写器"""
        import httpx
        # 创建httpx客户端（不使用系统代理）
        http_client = httpx.Client(timeout=60.0)
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )
        self.model = model

    def refine_question(self, question: str, max_retries: int = 3) -> Optional[str]:
        """
        改写单个问题

        Args:
            question: 原始问题
            max_retries: 最大重试次数

        Returns:
            改写后的问题，如果失败返回None
        """
        prompt = QUESTION_REFINE_PROMPT.format(question=question)

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的文本编辑助手，擅长改写和优化文本。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content.strip()
                result = json.loads(content)
                refined = result.get('refined_question', '').strip()

                if refined:
                    return refined
                else:
                    print(f"  ⚠️  第{attempt + 1}次尝试：返回结果为空")

            except json.JSONDecodeError as e:
                print(f"  ⚠️  第{attempt + 1}次尝试：JSON解析失败 - {e}")
            except Exception as e:
                print(f"  ⚠️  第{attempt + 1}次尝试：调用失败 - {e}")

            if attempt < max_retries - 1:
                time.sleep(1)

        print(f"  ❌ 改写失败，已重试{max_retries}次")
        return None


def main():
    """测试问题改写功能"""
    from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL

    print("=" * 80)
    print("测试问题改写功能")
    print("=" * 80)
    print()

    refiner = QuestionRefiner(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)

    # 测试用例
    test_questions = [
        "手撕:非hot100 给定一个随机数组,要求输出排序在中间的K个值例如给定随机数组arr=[9,3,7,1,4]。当K=3时,输出[3,4,7]",
        "介绍一下自己的项目，AI老师手语识别项目",
        "10.智力题：有12个外观相同的芯片、其中一个重量不同(不知轻重)，用天平最少称几次能找出这张芯片？"
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"[测试 {i}] 原始问题：")
        print(f"  {question}")
        print()

        refined = refiner.refine_question(question)

        if refined:
            print(f"  ✓ 改写后：")
            print(f"  {refined}")
        else:
            print(f"  ✗ 改写失败")

        print()
        print("-" * 80)
        print()


if __name__ == "__main__":
    main()
