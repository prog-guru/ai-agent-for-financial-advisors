# app/db_init.py
from sqlalchemy import text
from .db import engine

def init_pgvector():
    """Initialize pgvector extension in PostgreSQL"""
    try:
        with engine.connect() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            print("pgvector extension enabled successfully")
    except Exception as e:
        print(f"Note: Could not enable pgvector extension: {e}")
        print("This is expected if using SQLite for development")

if __name__ == "__main__":
    init_pgvector()