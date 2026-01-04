# 面试题目提取工具

使用Qwen大模型自动识别Excel中的面试题目，并保存到PostgreSQL数据库。

## 功能特点

- 自动识别文本中的所有面试问题（包括主问题和子问题）
- 一行多个问题会自动拆分为多行存储
- 使用Qwen API的JSON模式确保输出格式稳定
- 支持断点续传和批量处理
- 完整的日志记录
- 可复用的工具模块设计

## 文件说明

- `config.py` - 配置文件（API密钥、数据库连接等）
- `question_parser.py` - 核心工具模块（QuestionParser和DatabaseManager类）
- `process_questions.py` - 主执行脚本
- `query_questions.py` - 数据库查询工具
- `example_usage.py` - 使用示例代码
- `check_excel.py` - Excel文件检查工具
- `db_schema.sql` - 数据库表结构
- `requirements.txt` - Python依赖包
- `question_processing.log` - 处理日志文件

## 数据库表结构

```sql
CREATE TABLE interview_questions (
    id SERIAL PRIMARY KEY,
    source_title VARCHAR(500),      -- 原始标题
    question TEXT NOT NULL,          -- 单个问题
    question_index INTEGER,          -- 问题序号
    original_text TEXT,              -- 原始文本
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 使用方法

### 1. 首次使用（在questionExtract目录内）

```bash
# 进入questionExtract目录
cd questionExtract

# 安装依赖
pip install -r requirements.txt

# 运行主脚本
python process_questions.py
```

### 2. 作为Python包使用（从项目根目录）

```python
# 从项目根目录导入
from questionExtract.question_parser import QuestionParser, DatabaseManager
from questionExtract.config import (
    QWEN_API_KEY,
    QWEN_BASE_URL,
    QWEN_MODEL,
    QUESTION_EXTRACTION_PROMPT,
    DATABASE_URL
)

# 初始化解析器
parser = QuestionParser(
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL,
    model=QWEN_MODEL,
    prompt_template=QUESTION_EXTRACTION_PROMPT
)

# 解析单个文本
text = "1.什么是Transformer？ 2.什么是Attention？"
questions = parser.parse_questions(text)
print(questions)  # ['1.什么是Transformer？', '2.什么是Attention？']

# 初始化数据库
db = DatabaseManager(DATABASE_URL)
db.create_tables()

# 插入问题
records = [
    {
        'source_title': '面试题',
        'question': questions[0],
        'question_index': 1,
        'original_text': text
    }
]
db.insert_questions(records)
```

### 3. 在questionExtract目录内直接使用

```python
# 在questionExtract目录内
from question_parser import QuestionParser, DatabaseManager
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, QUESTION_EXTRACTION_PROMPT

parser = QuestionParser(
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL,
    model=QWEN_MODEL,
    prompt_template=QUESTION_EXTRACTION_PROMPT
)

questions = parser.parse_questions("你的问题文本")
```

### 4. 查询数据库

```bash
# 在questionExtract目录内
cd questionExtract
python query_questions.py
```

或从代码查询：

```python
from questionExtract.question_parser import DatabaseManager

db = DatabaseManager('postgresql://postgres:TMPpassword1@localhost:5432/postgres')
count = db.get_question_count()
print(f'数据库中共有 {count} 个问题')
```

## 配置说明

在 `config.py` 中修改以下配置：

```python
# 数据库连接
DATABASE_URL = "postgresql://user:password@host:port/database"

# Qwen API
QWEN_API_KEY = "your-api-key"
QWEN_MODEL = "qwen-plus"  # 可选: qwen-turbo, qwen-max

# Excel文件路径（自动根据相对路径计算）
# 指向 studyHelper/baseFiles/interviewQuestions.xlsx
```

## 目录结构

```
studyHelper/
├── questionExtract/          # 问题提取工具包
│   ├── __init__.py          # 包初始化文件
│   ├── config.py            # 配置文件
│   ├── question_parser.py   # 核心工具模块
│   ├── process_questions.py # 主执行脚本
│   ├── query_questions.py   # 查询工具
│   ├── example_usage.py     # 使用示例
│   ├── check_excel.py       # Excel检查工具
│   ├── requirements.txt     # 依赖包
│   ├── db_schema.sql        # 数据库表结构
│   └── README.md            # 本文档
└── baseFiles/
    └── interviewQuestions.xlsx  # Excel数据文件
```

## 特殊处理

- **内容审核**: 如果某行内容触发API内容审核，会自动重试3次，失败后跳过该行
- **空内容**: 自动跳过空行或无效内容
- **编码问题**: 所有日志输出使用UTF-8编码

## 日志说明

- 控制台会实时显示处理进度
- 详细日志保存在 `question_processing.log` 文件中
- 每个问题的识别结果都会被记录

## 注意事项

1. 确保PostgreSQL数据库已启动并可访问
2. Qwen API密钥需要有足够的调用额度
3. Excel文件处理时请关闭文件，避免文件占用
4. 首次运行会自动创建数据表

## 扩展使用

### 批量处理多个文件

```python
import glob
from questionExtract import QuestionParser, DatabaseManager
from questionExtract.config import *

parser = QuestionParser(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, QUESTION_EXTRACTION_PROMPT)
db = DatabaseManager(DATABASE_URL)

excel_files = glob.glob('../baseFiles/*.xlsx')
for file_path in excel_files:
    print(f'处理文件: {file_path}')
    # 调用处理函数...
```

### 只处理部分行

```python
from questionExtract.process_questions import process_excel_to_database
from questionExtract import QuestionParser, DatabaseManager
from questionExtract.config import *

parser = QuestionParser(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, QUESTION_EXTRACTION_PROMPT)
db = DatabaseManager(DATABASE_URL)

# 只处理第10到20行
stats = process_excel_to_database(
    excel_path=EXCEL_FILE_PATH,
    parser=parser,
    db_manager=db,
    start_row=10,
    end_row=20
)
```

## 执行结果

当前数据库中已有 **247个问题** 被成功识别和存储。

## 问题排查

如果遇到问题：

1. 检查 `question_processing.log` 日志文件
2. 确认数据库连接字符串正确
3. 验证API密钥是否有效
4. 查看是否有网络连接问题

## 开发者

本工具使用阿里云Qwen大模型API进行问题识别。
