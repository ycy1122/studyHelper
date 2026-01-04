"""
批量生成答案脚本 - 为所有未生成答案的问题生成答案、关键词和领域分类
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import logging
from question_parser import DatabaseManager
from answer_generator import AnswerGenerator
from config import (
    QWEN_API_KEY,
    QWEN_BASE_URL,
    QWEN_MODEL,
    DATABASE_URL
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('answer_generation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def main(batch_size: int = 10, max_questions: int = None):
    """
    主函数 - 批量生成答案

    Args:
        batch_size: 每批处理的数量
        max_questions: 最多处理的问题数量，None表示处理所有
    """
    logger.info("=" * 80)
    logger.info("开始批量生成答案")
    logger.info("=" * 80)

    try:
        # 初始化答案生成器
        logger.info("初始化答案生成器...")
        generator = AnswerGenerator(
            api_key=QWEN_API_KEY,
            base_url=QWEN_BASE_URL,
            model=QWEN_MODEL
        )

        # 初始化数据库管理器
        logger.info("初始化数据库管理器...")
        db = DatabaseManager(DATABASE_URL)

        # 查询统计信息
        total = db.get_question_count()
        answered = db.get_answered_count()
        unanswered = total - answered

        logger.info(f"\n当前数据统计：")
        logger.info(f"  总问题数: {total}")
        logger.info(f"  已有答案: {answered}")
        logger.info(f"  待生成答案: {unanswered}")

        if unanswered == 0:
            logger.info("\n所有问题都已有答案，无需处理")
            return

        # 确定本次要处理的数量
        process_count = max_questions if max_questions and max_questions < unanswered else unanswered
        logger.info(f"\n本次将处理 {process_count} 个问题")

        # 获取未生成答案的问题
        logger.info(f"\n获取未生成答案的问题...")
        questions = db.get_unanswered_questions(limit=process_count)
        logger.info(f"成功获取 {len(questions)} 个待处理问题")

        # 批量生成答案
        success_count = 0
        failed_count = 0

        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(questions) + batch_size - 1) // batch_size

            logger.info(f"\n{'=' * 80}")
            logger.info(f"处理批次 {batch_num}/{total_batches}（本批 {len(batch)} 个问题）")
            logger.info(f"{'=' * 80}")

            # 生成答案
            results = generator.batch_generate(batch)

            # 保存到数据库
            for result in results:
                try:
                    success = db.update_answer(
                        question_id=result['id'],
                        answer=result['answer'],
                        keywords=result['keywords'],
                        domain=result['domain']
                    )

                    if success:
                        success_count += 1
                        logger.info(f"✓ 问题ID {result['id']} 保存成功")
                    else:
                        failed_count += 1
                        logger.error(f"✗ 问题ID {result['id']} 保存失败")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"✗ 问题ID {result['id']} 保存时出错: {e}")

            # 未成功生成答案的问题
            generated_ids = {r['id'] for r in results}
            for q in batch:
                if q['id'] not in generated_ids:
                    failed_count += 1

        # 输出最终统计
        logger.info("\n" + "=" * 80)
        logger.info("批量生成答案完成！")
        logger.info("=" * 80)
        logger.info(f"  成功: {success_count}")
        logger.info(f"  失败: {failed_count}")
        logger.info(f"  总计: {len(questions)}")

        # 查询更新后的统计
        final_answered = db.get_answered_count()
        final_unanswered = total - final_answered
        logger.info(f"\n更新后统计：")
        logger.info(f"  已有答案: {final_answered}")
        logger.info(f"  待生成答案: {final_unanswered}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"程序执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='批量生成面试题答案')
    parser.add_argument('--batch-size', type=int, default=10, help='每批处理的数量（默认10）')
    parser.add_argument('--max', type=int, default=None, help='最多处理的问题数量（默认处理所有）')

    args = parser.parse_args()

    main(batch_size=args.batch_size, max_questions=args.max)
