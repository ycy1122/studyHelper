"""
Database Migration: Add analysis_status to job_analyses table
添加AI分析状态字段
"""

import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from questionExtract.config import DATABASE_URL

print("=" * 80)
print("Database Migration: Add analysis_status to job_analyses")
print("=" * 80)
print()

engine = create_engine(DATABASE_URL)

# SQL for adding status column
ADD_COLUMN_SQL = """
-- Add analysis_status column
-- Values: 'pending' (未开始), 'processing' (进行中), 'completed' (已完成), 'failed' (失败)
ALTER TABLE job_analyses
ADD COLUMN IF NOT EXISTS analysis_status VARCHAR(20) DEFAULT 'pending';

-- Create index for faster filtering
CREATE INDEX IF NOT EXISTS idx_job_analyses_status
ON job_analyses(analysis_status);

-- Update existing records
-- If analysis_result is NULL, status should be 'pending'
-- If analysis_result contains '分析失败', status should be 'failed'
-- Otherwise status should be 'completed'
UPDATE job_analyses
SET analysis_status = CASE
    WHEN analysis_result IS NULL THEN 'pending'
    WHEN analysis_result LIKE '%分析失败%' THEN 'failed'
    ELSE 'completed'
END
WHERE analysis_status = 'pending';
"""

try:
    print("Step 1: Connecting to database...")
    with engine.connect() as conn:
        print("[OK] Connected to database")
        print()

        print("Step 2: Adding analysis_status column...")
        conn.execute(text(ADD_COLUMN_SQL))
        conn.commit()
        print("[OK] Column added successfully")
        print()

        print("Step 3: Verifying changes...")
        result = conn.execute(text("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'job_analyses'
            AND column_name = 'analysis_status'
        """))

        column = result.fetchone()
        if column:
            print(f"[OK] Column 'analysis_status' exists:")
            print(f"  Type: {column[1]}")
            print(f"  Default: {column[2]}")
        else:
            print("[WARN] Column not found after migration")

        # Show count by status
        result = conn.execute(text("""
            SELECT analysis_status, COUNT(*)
            FROM job_analyses
            GROUP BY analysis_status
        """))

        print()
        print("Current status distribution:")
        for row in result:
            print(f"  {row[0]}: {row[1]}")

except Exception as e:
    print(f"[FAIL] Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 80)
print("[SUCCESS] Migration completed!")
print("=" * 80)
