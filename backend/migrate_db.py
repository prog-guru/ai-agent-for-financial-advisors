# migrate_db.py
from sqlalchemy import text
from app.db import engine

def migrate_database():
    with engine.connect() as conn:
        try:
            # Add missing columns to existing users table
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS sub VARCHAR(128)"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(256) DEFAULT ''"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS picture VARCHAR(512) DEFAULT ''"))
            
            # Create indexes
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_sub ON users (sub)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
            
            conn.commit()
            print("Database migration completed")
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    migrate_database()