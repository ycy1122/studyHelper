"""
数据库迁移脚本 - 执行表结构更新
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
    logger.info("开始执行数据库迁移")
    logger.info("=" * 80)

    engine = create_engine(DATABASE_URL)

    migration_sql = """
    -- 1. 添加新字段
    ALTER TABLE interview_questions
    ADD COLUMN IF NOT EXISTS has_answer BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS answer TEXT,
    ADD COLUMN IF NOT EXISTS keywords TEXT,
    ADD COLUMN IF NOT EXISTS domain VARCHAR(50);

    -- 2. 添加领域字段的检查约束
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'check_domain_values'
        ) THEN
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
        END IF;
    END$$;

    -- 3. 为新字段添加索引
    CREATE INDEX IF NOT EXISTS idx_has_answer ON interview_questions(has_answer);
    CREATE INDEX IF NOT EXISTS idx_domain ON interview_questions(domain);
    """

    try:
        with engine.begin() as conn:
            logger.info("执行迁移SQL...")
            conn.execute(text(migration_sql))
            logger.info("✓ 字段添加成功")

            # 查询统计信息
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN has_answer = TRUE THEN 1 END) as answered,
                    COUNT(CASE WHEN has_answer = FALSE OR has_answer IS NULL THEN 1 END) as unanswered
                FROM interview_questions
            """))
            row = result.fetchone()

            logger.info(f"\n当前数据统计：")
            logger.info(f"  总问题数: {row[0]}")
            logger.info(f"  已有答案: {row[1]}")
            logger.info(f"  未有答案: {row[2]}")

        logger.info("\n" + "=" * 80)
        logger.info("数据库迁移完成！")
        logger.info("=" * 80)

        # 尝试为question字段添加唯一索引
        logger.info("\n尝试为question字段添加唯一索引...")
        try:
            with engine.begin() as conn:
                # 先检查是否有重复
                result = conn.execute(text("""
                    SELECT question, COUNT(*) as cnt
                    FROM interview_questions
                    GROUP BY question
                    HAVING COUNT(*) > 1
                    LIMIT 5
                """))
                duplicates = result.fetchall()

                if duplicates:
                    logger.warning(f"发现 {len(duplicates)} 个重复问题，示例：")
                    for dup in duplicates[:3]:
                        logger.warning(f"  - {dup[0][:80]}... (重复{dup[1]}次)")
                    logger.warning("\n建议先清理重复数据，然后再添加唯一索引")
                    logger.warning("清理命令：DELETE FROM interview_questions WHERE id NOT IN (SELECT MIN(id) FROM interview_questions GROUP BY question);")
                else:
                    # 没有重复，添加唯一索引
                    conn.execute(text("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_question
                        ON interview_questions(question)
                    """))
                    logger.info("✓ 唯一索引添加成功")

        except Exception as e:
            logger.warning(f"添加唯一索引时出现警告: {e}")
            logger.info("可以稍后手动添加唯一索引")

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
