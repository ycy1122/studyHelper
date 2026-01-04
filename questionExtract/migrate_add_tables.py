"""
数据库迁移脚本 - 添加source_questions和practice_records表
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import create_engine, text
from config import DATABASE_URL
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_migration():
    """执行数据库迁移"""
    logger.info("=" * 80)
    logger.info("开始执行数据库迁移 - 添加新表")
    logger.info("=" * 80)

    engine = create_engine(DATABASE_URL)

    migration_sql = """
    -- 1. 创建原始问题表
    CREATE TABLE IF NOT EXISTS source_questions (
        id SERIAL PRIMARY KEY,
        source_title VARCHAR(500),
        original_text TEXT NOT NULL,
        is_extracted BOOLEAN DEFAULT FALSE,
        detail_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(original_text)
    );

    -- 2. 创建练习记录表
    CREATE TABLE IF NOT EXISTS practice_records (
        id SERIAL PRIMARY KEY,
        question_id INTEGER NOT NULL REFERENCES interview_questions(id) ON DELETE CASCADE,
        user_answer TEXT,
        ai_score DECIMAL(5,2),
        ai_feedback TEXT,
        mastery_level VARCHAR(20) CHECK (mastery_level IN ('不会', '一般', '会了')),
        practice_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        time_spent INTEGER
    );

    -- 3. 修改interview_questions表
    ALTER TABLE interview_questions
    ADD COLUMN IF NOT EXISTS source_question_id INTEGER REFERENCES source_questions(id) ON DELETE SET NULL;

    ALTER TABLE interview_questions
    ADD COLUMN IF NOT EXISTS latest_mastery_level VARCHAR(20);

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'check_latest_mastery_level'
        ) THEN
            ALTER TABLE interview_questions
            ADD CONSTRAINT check_latest_mastery_level
            CHECK (latest_mastery_level IN ('不会', '一般', '会了', NULL));
        END IF;
    END$$;

    -- 4. 创建索引
    CREATE INDEX IF NOT EXISTS idx_sq_is_extracted ON source_questions(is_extracted);
    CREATE INDEX IF NOT EXISTS idx_sq_created_at ON source_questions(created_at);
    CREATE INDEX IF NOT EXISTS idx_iq_source_question_id ON interview_questions(source_question_id);
    CREATE INDEX IF NOT EXISTS idx_pr_question_id ON practice_records(question_id);
    CREATE INDEX IF NOT EXISTS idx_pr_practice_time ON practice_records(practice_time);
    CREATE INDEX IF NOT EXISTS idx_pr_mastery_level ON practice_records(mastery_level);
    CREATE INDEX IF NOT EXISTS idx_iq_latest_mastery_level ON interview_questions(latest_mastery_level);
    """

    try:
        with engine.begin() as conn:
            logger.info("执行迁移SQL...")
            conn.execute(text(migration_sql))
            logger.info("✓ 表和索引创建成功")

            # 查询统计信息
            result = conn.execute(text("""
                SELECT
                    (SELECT COUNT(*) FROM source_questions) as source_count,
                    (SELECT COUNT(*) FROM interview_questions) as detail_count,
                    (SELECT COUNT(*) FROM practice_records) as practice_count
            """))
            row = result.fetchone()

            logger.info(f"\n当前数据统计：")
            logger.info(f"  原始问题数: {row[0]}")
            logger.info(f"  明细问题数: {row[1]}")
            logger.info(f"  练习记录数: {row[2]}")

        logger.info("\n" + "=" * 80)
        logger.info("数据库迁移完成！")
        logger.info("=" * 80)

        # 从现有数据迁移到source_questions
        logger.info("\n开始迁移现有数据到source_questions表...")
        migrate_existing_data(engine)

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def migrate_existing_data(engine):
    """将现有的original_text数据迁移到source_questions表"""
    try:
        with engine.begin() as conn:
            # 获取所有不同的original_text和source_title组合
            result = conn.execute(text("""
                SELECT DISTINCT source_title, original_text
                FROM interview_questions
                WHERE original_text IS NOT NULL
                ORDER BY source_title
            """))
            rows = result.fetchall()

            if not rows:
                logger.info("没有需要迁移的数据")
                return

            logger.info(f"找到 {len(rows)} 个不同的原始文本")

            # 插入到source_questions
            for row in rows:
                source_title = row[0]
                original_text = row[1]

                # 计算该原始文本对应的明细问题数量
                count_result = conn.execute(text("""
                    SELECT COUNT(*) FROM interview_questions
                    WHERE original_text = :original_text
                """), {'original_text': original_text})
                detail_count = count_result.scalar()

                # 插入source_questions（如果不存在）
                conn.execute(text("""
                    INSERT INTO source_questions (source_title, original_text, is_extracted, detail_count)
                    VALUES (:source_title, :original_text, TRUE, :detail_count)
                    ON CONFLICT (original_text) DO NOTHING
                """), {
                    'source_title': source_title,
                    'original_text': original_text,
                    'detail_count': detail_count
                })

            # 更新interview_questions的source_question_id
            conn.execute(text("""
                UPDATE interview_questions iq
                SET source_question_id = sq.id
                FROM source_questions sq
                WHERE iq.original_text = sq.original_text
                AND iq.source_question_id IS NULL
            """))

            updated = conn.execute(text("""
                SELECT COUNT(*) FROM interview_questions WHERE source_question_id IS NOT NULL
            """)).scalar()

            logger.info(f"✓ 成功迁移数据，关联了 {updated} 条明细问题")

    except Exception as e:
        logger.error(f"数据迁移失败: {e}")
        raise


if __name__ == "__main__":
    run_migration()
