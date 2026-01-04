"""
批量改写问题脚本
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import argparse
from question_refiner import QuestionRefiner
from question_parser import DatabaseManager
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
import time


def refine_all_questions(max_count: int = None):
    """批量改写问题"""
    print("=" * 80)
    print("批量改写面试问题")
    print("=" * 80)
    print()

    # 初始化
    from config import DATABASE_URL
    refiner = QuestionRefiner(QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL)
    db_manager = DatabaseManager(DATABASE_URL)

    # 获取所有需要改写的问题（refined_question为NULL的）
    print("[1/3] 获取需要改写的问题...")
    questions = db_manager.get_questions_without_refined(limit=max_count)
    total = len(questions)

    if total == 0:
        print("✓ 所有问题都已改写完成！")
        return

    print(f"✓ 找到 {total} 个需要改写的问题")
    print()

    # 批量改写
    print(f"[2/3] 开始改写问题...")
    print()

    success_count = 0
    fail_count = 0

    for i, (question_id, question_text) in enumerate(questions, 1):
        print(f"[{i}/{total}] ID={question_id}")
        print(f"  原始: {question_text[:80]}{'...' if len(question_text) > 80 else ''}")

        # 改写问题
        refined = refiner.refine_question(question_text)

        if refined:
            # 保存到数据库
            if db_manager.update_refined_question(question_id, refined):
                print(f"  改写: {refined[:80]}{'...' if len(refined) > 80 else ''}")
                print(f"  ✓ 保存成功")
                success_count += 1
            else:
                print(f"  ✗ 保存失败")
                fail_count += 1
        else:
            print(f"  ✗ 改写失败")
            fail_count += 1

        print()

        # 避免API限流
        if i < total:
            time.sleep(0.5)

    # 统计
    print("=" * 80)
    print(f"[3/3] 改写完成！")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  总计: {total}")
    print("=" * 80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='批量改写面试问题')
    parser.add_argument('--max', type=int, default=None,
                        help='最多改写的问题数量（默认全部）')
    args = parser.parse_args()

    refine_all_questions(max_count=args.max)


if __name__ == "__main__":
    main()
