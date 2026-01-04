# 项目配置文件

# PostgreSQL数据库配置
DATABASE_URL = "postgresql://postgres:TMPpassword1@localhost:5432/postgres"

# Qwen API配置
QWEN_API_KEY = "sk-ec17fdcaa8dd4e69b827142bb045088c"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen-plus"  # 使用qwen-plus，识别准确率更高

# Excel文件路径（相对于questionExtract目录的上一级）
import os
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
EXCEL_FILE_PATH = os.path.join(_project_root, "baseFiles", "interviewQuestions.xlsx")

# 问题识别的提示词模板
QUESTION_EXTRACTION_PROMPT = """你是一个专业的面试题目分析助手。请仔细分析下面的文本，识别其中包含的所有面试问题。

要求：
1. 识别所有独立的问题，包括主问题和子问题
2. 保持问题的原始表述，不要改写
3. 如果问题有编号（如1. 2. 3.或一、二、三），保留编号
4. 如果文本中没有明确的问题（比如只是描述性文本），则返回空数组
5. 输出格式必须是严格的JSON对象，包含questions数组

文本内容：
{text}

请以JSON格式输出，格式如下：
{{"questions": ["问题1", "问题2", "问题3"]}}

只返回JSON对象，不要有其他说明文字。
"""
