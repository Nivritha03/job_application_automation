import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from core.models import Base

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "sqlite:///jobs.db")

engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    with engine.begin() as conn:
        # Check applications columns
        app_cols = [c["name"] for c in inspector.get_columns("applications")]
        new_app_cols = {
            "skip_reason": "TEXT",
            "validation_error": "TEXT",
            "ai_attempts": "INTEGER DEFAULT 0",
            "company_reply": "TEXT"
        }
        for col, col_type in new_app_cols.items():
            if col not in app_cols:
                conn.execute(text(f"ALTER TABLE applications ADD COLUMN {col} {col_type}"))
                
        # Check jobs columns
        job_cols = [c["name"] for c in inspector.get_columns("jobs")]
        new_job_cols = {
            "country": "TEXT",
            "is_remote": "BOOLEAN DEFAULT 0"
        }
        for col, col_type in new_job_cols.items():
            if col not in job_cols:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
