# 答案生成功能使用指南

## 功能概述

自动为数据库中的面试问题生成详细的答案、提取关键词并进行领域分类。

## 新增字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| has_answer | BOOLEAN | 是否已生成答案 |
| answer | TEXT | 答案内容 |
| keywords | TEXT | 关键词（逗号分隔，3-5个） |
| domain | VARCHAR(50) | 领域分类 |

### 领域分类枚举值

- 大模型
- RAG
- 记忆管理
- Langchain语法
- 智能体框架
- 效果评测
- 工程化部署实践
- 其他

## 使用方法

### 1. 数据库迁移（首次使用）

```bash
cd questionExtract
python migrate_database.py
```

迁移脚本会：
- 添加新字段（has_answer, answer, keywords, domain）
- 添加领域字段的检查约束
- 清理重复问题（保留最早的一条）
- 为question字段添加唯一索引

### 2. 批量生成答案

#### 处理所有未生成答案的问题

```bash
python generate_answers.py
```

#### 只处理部分问题（测试）

```bash
# 只处理前10个问题
python generate_answers.py --max 10

# 每批处理5个问题
python generate_answers.py --batch-size 5

# 组合使用
python generate_answers.py --max 20 --batch-size 5
```

### 3. 查看生成的答案

```bash
python view_answers.py
```

或使用SQL查询：

```sql
-- 查看所有已生成答案的问题
SELECT id, question, answer, keywords, domain
FROM interview_questions
WHERE has_answer = TRUE;

-- 按领域分组统计
SELECT domain, COUNT(*) as count
FROM interview_questions
WHERE has_answer = TRUE
GROUP BY domain
ORDER BY count DESC;

-- 搜索特定关键词的问题
SELECT question, keywords, domain
FROM interview_questions
WHERE keywords LIKE '%Transformer%'
AND has_answer = TRUE;
```

## 作为Python模块使用

### 单个问题生成答案

```python
from questionExtract import AnswerGenerator, DatabaseManager
from questionExtract.config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, DATABASE_URL

# 初始化生成器
generator = AnswerGenerator(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)

# 生成答案
result = generator.generate_answer("什么是Transformer？")

if result:
    print(f"答案: {result['answer']}")
    print(f"关键词: {result['keywords']}")
    print(f"领域: {result['domain']}")
else:
    print("生成失败")
```

### 批量生成并保存

```python
from questionExtract import AnswerGenerator, DatabaseManager
from questionExtract.config import *

# 初始化
generator = AnswerGenerator(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)
db = DatabaseManager(DATABASE_URL)

# 获取未生成答案的问题
questions = db.get_unanswered_questions(limit=10)

# 批量生成
results = generator.batch_generate(questions)

# 保存到数据库
for result in results:
    db.update_answer(
        question_id=result['id'],
        answer=result['answer'],
        keywords=result['keywords'],
        domain=result['domain']
    )

print(f"成功生成 {len(results)} 个答案")
```

## 答案示例

### 问题
```
1.八股：Encoder与decoder的中Attention区别？
```

### 生成的答案
```
Encoder和Decoder中的Attention机制在结构和功能上有显著区别。在标准的Transformer
架构中，Encoder使用的是自注意力（Self-Attention）机制，其Query、Key和Value均来自
同一输入序列，目的是捕捉输入序列内部的上下文依赖关系...

关键词: Attention机制,Self-Attention,Cross-Attention,Masked Self-Attention,Transformer
领域: 大模型
```

## 性能建议

1. **批量大小**: 建议设置为5-10，避免API限流
2. **并发控制**: 当前版本顺序处理，避免超过API限制
3. **重试机制**: 每个问题最多重试3次
4. **日志记录**: 所有操作都会记录到 `answer_generation.log`

## 常见问题

### Q: 如何重新生成某个问题的答案？

```sql
-- 将has_answer设置为FALSE
UPDATE interview_questions
SET has_answer = FALSE, answer = NULL, keywords = NULL, domain = NULL
WHERE id = <问题ID>;

-- 然后重新运行生成脚本
```

### Q: 如何修改领域分类？

修改 `answer_generator.py` 中的 `VALID_DOMAINS` 列表，并更新数据库约束：

```sql
ALTER TABLE interview_questions
DROP CONSTRAINT check_domain_values;

ALTER TABLE interview_questions
ADD CONSTRAINT check_domain_values
CHECK (domain IN ('新领域1', '新领域2', ...));
```

### Q: 生成的答案质量如何控制？

在 `answer_generator.py` 中调整：
- `temperature` 参数（默认0.3）：越低越保守，越高越有创造性
- 修改 `ANSWER_GENERATION_PROMPT` 提示词模板

### Q: API调用失败怎么办？

1. 检查API密钥是否有效
2. 查看 `answer_generation.log` 日志文件
3. 确认网络连接正常
4. 检查API额度是否充足

## 数据统计查询

```python
from questionExtract import DatabaseManager
from questionExtract.config import DATABASE_URL

db = DatabaseManager(DATABASE_URL)

print(f"总问题数: {db.get_question_count()}")
print(f"已生成答案: {db.get_answered_count()}")
print(f"待生成答案: {db.get_question_count() - db.get_answered_count()}")
```

## 注意事项

1. **唯一性约束**: question字段已添加唯一索引，相同问题只保留一条
2. **领域约束**: domain字段只能是预定义的8个值之一
3. **关键词格式**: 多个关键词用逗号分隔，建议3-5个
4. **答案长度**: 无限制，但建议保持在合理范围（200-800字）
5. **成本控制**: 每个问题大约消耗500-1000 tokens，注意API成本

## 后续优化方向

- [ ] 支持并发生成以提升速度
- [ ] 添加答案质量评估
- [ ] 支持自定义领域分类
- [ ] 导出为Markdown/PDF格式
- [ ] 答案相似度去重

---

更多详细信息请查看主README文档。
