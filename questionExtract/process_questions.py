"""
主脚本：批量处理Excel中的面试题目并保存到数据库
"""
import pandas as pd
import logging
import sys
from typing import List, Dict
from question_parser import QuestionParser, DatabaseManager
from question_refiner import QuestionRefiner
from config import (
    QWEN_API_KEY,
    QWEN_BASE_URL,
    QWEN_MODEL,
    QUESTION_EXTRACTION_PROMPT,
    DATABASE_URL,
    EXCEL_FILE_PATH
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('question_processing.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def read_excel(file_path: str) -> pd.DataFrame:
    """
    读取Excel文件

    Args:
        file_path: Excel文件路径

    Returns:
        DataFrame对象
    """
    logger.info(f"正在读取Excel文件: {file_path}")
    df = pd.read_excel(file_path)
    logger.info(f"成功读取 {len(df)} 行数据")
    logger.info(f"列名: {list(df.columns)}")
    return df


def process_excel_to_database(
    excel_path: str,
    parser: QuestionParser,
    db_manager: DatabaseManager,
    refiner: QuestionRefiner = None,
    start_row: int = 0,
    end_row: int = None
) -> Dict[str, int]:
    """
    处理Excel文件并保存到数据库

    Args:
        excel_path: Excel文件路径
        parser: 问题解析器
        db_manager: 数据库管理器
        refiner: 问题改写器（可选）
        start_row: 起始行（包含）
        end_row: 结束行（不包含），None表示处理到末尾

    Returns:
        统计信息字典
    """
    # 读取Excel
    df = read_excel(excel_path)

    # 获取列名（第一列是标题，第二列是题目）
    title_column = df.columns[0]
    question_column = df.columns[1]

    # 处理行范围
    if end_row is None:
        end_row = len(df)

    df_subset = df.iloc[start_row:end_row]
    logger.info(f"准备处理第 {start_row} 到第 {end_row} 行（共 {len(df_subset)} 行）")

    # 统计信息
    stats = {
        'total_rows': len(df_subset),
        'processed_rows': 0,
        'total_questions': 0,
        'failed_rows': 0
    }

    # 准备批量插入的记录
    all_records = []

    # 逐行处理
    for idx, row in df_subset.iterrows():
        try:
            source_title = str(row[title_column]) if pd.notna(row[title_column]) else '未命名'
            original_text = str(row[question_column]) if pd.notna(row[question_column]) else ''

            if not original_text.strip():
                logger.warning(f"第 {idx} 行的题目内容为空，跳过")
                stats['failed_rows'] += 1
                continue

            logger.info(f"\n{'=' * 80}")
            logger.info(f"处理第 {idx} 行: {source_title[:50]}...")
            logger.info(f"原始文本长度: {len(original_text)} 字符")

            # 调用解析器识别问题
            questions = parser.parse_questions(original_text)

            if not questions:
                logger.warning(f"第 {idx} 行未识别到问题")
                stats['failed_rows'] += 1
                continue

            logger.info(f"识别到 {len(questions)} 个问题:")
            for q_idx, question in enumerate(questions, 1):
                logger.info(f"  {q_idx}. {question[:100]}{'...' if len(question) > 100 else ''}")

            # 构造记录
            for q_idx, question in enumerate(questions, 1):
                record = {
                    'source_title': source_title,
                    'question': question,
                    'question_index': q_idx,
                    'original_text': original_text
                }

                # 如果提供了改写器，则改写问题
                if refiner:
                    refined = refiner.refine_question(question)
                    if refined:
                        record['refined_question'] = refined
                        logger.info(f"  改写: {refined[:100]}{'...' if len(refined) > 100 else ''}")

                all_records.append(record)

            stats['processed_rows'] += 1
            stats['total_questions'] += len(questions)

        except Exception as e:
            logger.error(f"处理第 {idx} 行时出错: {e}", exc_info=True)
            stats['failed_rows'] += 1

    # 批量插入数据库
    if all_records:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"准备插入 {len(all_records)} 条记录到数据库...")
        inserted_count = db_manager.insert_questions(all_records)
        logger.info(f"成功插入 {inserted_count} 条记录")
    else:
        logger.warning("没有记录需要插入")

    return stats


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("开始处理面试题目")
    logger.info("=" * 80)

    try:
        # 初始化问题解析器
        logger.info("初始化问题解析器...")
        parser = QuestionParser(
            api_key=QWEN_API_KEY,
            base_url=QWEN_BASE_URL,
            model=QWEN_MODEL,
            prompt_template=QUESTION_EXTRACTION_PROMPT
        )

        # 初始化数据库管理器
        logger.info("初始化数据库管理器...")
        db_manager = DatabaseManager(DATABASE_URL)

        # 初始化问题改写器
        logger.info("初始化问题改写器...")
        refiner = QuestionRefiner(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)

        # 创建数据表
        logger.info("创建数据表...")
        db_manager.create_tables()

        # 处理Excel文件
        stats = process_excel_to_database(
            excel_path=EXCEL_FILE_PATH,
            parser=parser,
            db_manager=db_manager,
            refiner=refiner
        )

        # 输出统计信息
        logger.info("\n" + "=" * 80)
        logger.info("处理完成！统计信息：")
        logger.info(f"  总行数: {stats['total_rows']}")
        logger.info(f"  成功处理: {stats['processed_rows']}")
        logger.info(f"  失败行数: {stats['failed_rows']}")
        logger.info(f"  识别问题总数: {stats['total_questions']}")

        # 验证数据库
        total_in_db = db_manager.get_question_count()
        logger.info(f"  数据库中问题总数: {total_in_db}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"程序执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
