-- 面试题目数据库表结构
CREATE TABLE IF NOT EXISTS interview_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_title VARCHAR(500) COMMENT '原始标题',
    question TEXT NOT NULL COMMENT '单个问题',
    question_index INT COMMENT '问题在原始文本中的序号',
    original_text TEXT COMMENT '原始题目文本（用于追溯）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_source_title (source_title),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='面试题目表';
