import pandas as pd
import sys

# 设置输出编码为UTF-8
sys.stdout.reconfigure(encoding='utf-8')

try:
    df = pd.read_excel(r'E:\STUDY\2025-all\studyHelper\baseFiles\interviewQuestions.xlsx')
    print(f'列名: {list(df.columns)}')
    print(f'行数: {len(df)}')
    print('\n前5行数据:')
    for idx, row in df.head(5).iterrows():
        print(f'\n第{idx}行:')
        print(f'  标题: {row.iloc[0][:100] if pd.notna(row.iloc[0]) else "空"}...')
        print(f'  题目: {row.iloc[1][:200] if pd.notna(row.iloc[1]) else "空"}...')
except Exception as e:
    print(f'错误: {e}')
    import traceback
    traceback.print_exc()
