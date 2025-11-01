# reset_db.py
from app.db import engine
from app.models import Base
from app.db_init import init_pgvector

# Enable pgvector extension
init_pgvector()

# Drop all tables and recreate
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Database reset complete")