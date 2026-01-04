"""
Database Migration: Add Chat Tables

Creates tables for chatbot functionality:
- chat_conversations: Chat sessions
- chat_messages: Individual messages
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.database import DATABASE_URL

print("=" * 80)
print("Database Migration: Adding Chat Tables")
print("=" * 80)
print()

# Create engine
engine = create_engine(DATABASE_URL)

# SQL for creating tables
CREATE_TABLES_SQL = """
-- Chat Conversations Table
CREATE TABLE IF NOT EXISTS chat_conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    user_id INTEGER,
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_session_id
    ON chat_conversations(session_id);

-- Chat Messages Table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    model_used VARCHAR(50),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost DECIMAL(10, 6),
    latency FLOAT,
    rag_used BOOLEAN DEFAULT FALSE,
    rag_sources TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT fk_session
        FOREIGN KEY (session_id)
        REFERENCES chat_conversations(session_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
    ON chat_messages(session_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
    ON chat_messages(created_at DESC);
"""

try:
    print("Step 1: Connecting to database...")
    with engine.connect() as conn:
        print("[SUCCESS] Connected to database")
        print()

        print("Step 2: Creating chat tables...")
        # Execute SQL
        conn.execute(text(CREATE_TABLES_SQL))
        conn.commit()
        print("[SUCCESS] Chat tables created")
        print()

        # Verify tables exist
        print("Step 3: Verifying tables...")
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('chat_conversations', 'chat_messages')
            ORDER BY table_name
        """))

        tables = [row[0] for row in result]
        print(f"Found tables: {tables}")
        print()

        if 'chat_conversations' in tables and 'chat_messages' in tables:
            print("[SUCCESS] Migration completed successfully!")
            print()
            print("Created tables:")
            print("  - chat_conversations")
            print("  - chat_messages")
        else:
            print("[WARNING] Some tables may not have been created")

except Exception as e:
    print(f"[ERROR] Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 80)
print("Next steps:")
print("1. Configure LLM settings in config/llm_config.yaml")
print("2. Start backend: restart_backend.bat")
print("3. Access chatbot at /chat page")
print("=" * 80)
