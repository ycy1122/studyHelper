-- 创建原始问题表
-- 存储从Excel或手动录入的原始问题文本

CREATE TABLE IF NOT EXISTS source_questions (
    id SERIAL PRIMARY KEY,
    source_title VARCHAR(500) COMMENT '来源标题（如面经标题）',
    original_text TEXT NOT NULL COMMENT '原始问题文本',
    is_extracted BOOLEAN DEFAULT FALSE COMMENT '是否已提取明细问题',
    detail_count INTEGER DEFAULT 0 COMMENT '提取的明细问题数量',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE(original_text) -- 避免重复的原始文本
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_is_extracted ON source_questions(is_extracted);
CREATE INDEX IF NOT EXISTS idx_created_at ON source_questions(created_at);

-- 修改interview_questions表，添加source_question_id字段关联原始问题
ALTER TABLE interview_questions
ADD COLUMN IF NOT EXISTS source_question_id INTEGER REFERENCES source_questions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_source_question_id ON interview_questions(source_question_id);

-- 创建用户练习记录表
CREATE TABLE IF NOT EXISTS practice_records (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES interview_questions(id) ON DELETE CASCADE,
    user_answer TEXT COMMENT '用户的回答',
    ai_score DECIMAL(5,2) COMMENT 'AI评分（0-100）',
    ai_feedback TEXT COMMENT 'AI反馈',
    mastery_level VARCHAR(20) CHECK (mastery_level IN ('不会', '一般', '会了')) COMMENT '掌握程度',
    practice_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '练习时间',
    time_spent INTEGER COMMENT '答题耗时（秒）'
);

-- 为练习记录创建索引
CREATE INDEX IF NOT EXISTS idx_question_id ON practice_records(question_id);
CREATE INDEX IF NOT EXISTS idx_practice_time ON practice_records(practice_time);
CREATE INDEX IF NOT EXISTS idx_mastery_level ON practice_records(mastery_level);

-- 为interview_questions表添加最新掌握程度字段（冗余，便于快速查询）
ALTER TABLE interview_questions
ADD COLUMN IF NOT EXISTS latest_mastery_level VARCHAR(20) CHECK (latest_mastery_level IN ('不会', '一般', '会了', NULL)) COMMENT '最新掌握程度';

CREATE INDEX IF NOT EXISTS idx_latest_mastery_level ON interview_questions(latest_mastery_level);

-- 添加注释
COMMENT ON TABLE source_questions IS '原始问题表 - 存储从Excel或手动录入的原始问题文本';
COMMENT ON TABLE practice_records IS '练习记录表 - 存储用户的答题记录和AI评分';

COMMENT ON COLUMN source_questions.source_title IS '来源标题（如：阿里云Agent算法一面）';
COMMENT ON COLUMN source_questions.original_text IS '原始问题文本（可能包含多个问题）';
COMMENT ON COLUMN source_questions.is_extracted IS '是否已提取明细问题';
COMMENT ON COLUMN source_questions.detail_count IS '提取的明细问题数量';

COMMENT ON COLUMN interview_questions.source_question_id IS '关联的原始问题ID';
COMMENT ON COLUMN interview_questions.latest_mastery_level IS '最新掌握程度（从practice_records同步）';

COMMENT ON COLUMN practice_records.user_answer IS '用户的回答内容';
COMMENT ON COLUMN practice_records.ai_score IS 'AI评分（0-100分）';
COMMENT ON COLUMN practice_records.ai_feedback IS 'AI反馈建议';
COMMENT ON COLUMN practice_records.mastery_level IS '用户标记的掌握程度';
COMMENT ON COLUMN practice_records.time_spent IS '答题耗时（秒）';
