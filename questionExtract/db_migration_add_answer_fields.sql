-- 数据库迁移脚本：添加答案相关字段
-- 执行时间：2025-12-29

-- 1. 添加新字段
ALTER TABLE interview_questions
ADD COLUMN IF NOT EXISTS has_answer BOOLEAN DEFAULT FALSE COMMENT '是否已生成答案',
ADD COLUMN IF NOT EXISTS answer TEXT COMMENT '答案内容',
ADD COLUMN IF NOT EXISTS keywords TEXT COMMENT '关键词（逗号分隔）',
ADD COLUMN IF NOT EXISTS domain VARCHAR(50) COMMENT '领域分类';

-- 2. 为问题字段添加唯一索引（避免重复问题）
-- 注意：如果已有重复数据，需要先清理
-- 可以先查询重复数据：SELECT question, COUNT(*) FROM interview_questions GROUP BY question HAVING COUNT(*) > 1;

-- 创建唯一索引（如果已存在则跳过）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'interview_questions'
        AND indexname = 'idx_unique_question'
    ) THEN
        CREATE UNIQUE INDEX idx_unique_question ON interview_questions(question);
    END IF;
END$$;

-- 3. 添加领域字段的检查约束（确保只能是指定的领域）
ALTER TABLE interview_questions
DROP CONSTRAINT IF EXISTS check_domain_values;

ALTER TABLE interview_questions
ADD CONSTRAINT check_domain_values
CHECK (domain IN (
    '大模型',
    'RAG',
    '记忆管理',
    'Langchain语法',
    '智能体框架',
    '效果评测',
    '工程化部署实践',
    '其他'
));

-- 4. 为新字段添加索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_has_answer ON interview_questions(has_answer);
CREATE INDEX IF NOT EXISTS idx_domain ON interview_questions(domain);

-- 5. 查看表结构
\d interview_questions

-- 6. 查看未生成答案的问题数量
SELECT COUNT(*) as unanswered_count
FROM interview_questions
WHERE has_answer = FALSE OR has_answer IS NULL;

COMMENT ON COLUMN interview_questions.has_answer IS '是否已生成答案';
COMMENT ON COLUMN interview_questions.answer IS '答案内容';
COMMENT ON COLUMN interview_questions.keywords IS '关键词（逗号分隔）';
COMMENT ON COLUMN interview_questions.domain IS '领域分类：大模型/RAG/记忆管理/Langchain语法/智能体框架/效果评测/工程化部署实践/其他';
