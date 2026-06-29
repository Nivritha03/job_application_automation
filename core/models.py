from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# -------------------------------------------------------------------
# Pydantic Data Models (Passed between Pipeline Engines)
# -------------------------------------------------------------------

class Job(BaseModel):
    id: Optional[str] = None
    title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    description: str = ""
    requirements: str = ""
    url: str = ""
    skills: List[str] = Field(default_factory=list)
    score: int = 0
    would_apply: bool = False
    applied: bool = False
    resume_used: str = ""
    status: str = "discovered" # discovered, filtered, applied, error
    error_message: str = ""
    screenshot_path: str = ""
    failure_type: Optional[str] = None
    retry_after: Optional[datetime] = None
    platform: str = ""
    
# -------------------------------------------------------------------
# SQLAlchemy Models (Database Persistence)
# -------------------------------------------------------------------
class DBCompany(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    otp_required = Column(Boolean, default=False)
    supports_easy_apply = Column(Boolean, default=True)
    resume_upload_first = Column(Boolean, default=False)
    questions_count = Column(Integer, default=0)
    average_completion_time = Column(Float, default=0.0)
    jobs = relationship("DBJob", back_populates="company")

class DBJob(Base):
    __tablename__ = 'jobs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_job_id = Column(String, unique=True, nullable=True)
    site = Column(String)
    title = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    location = Column(String)
    salary = Column(String)
    description = Column(Text)
    skills = Column(String)
    requirements = Column(Text)
    url = Column(String, unique=True)
    apply_url = Column(String)
    search_keyword = Column(String)
    job_hash = Column(String, unique=True, nullable=True)
    date_found = Column(DateTime, default=datetime.utcnow)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("DBCompany", back_populates="jobs")
    application = relationship("DBApplication", back_populates="job", uselist=False)

class DBApplication(Base):
    __tablename__ = 'applications'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    resume_used = Column(String)
    match_score = Column(Integer)
    applied = Column(Boolean, default=False)
    status = Column(String) # applied, skipped, error
    error_message = Column(Text)
    failure_type = Column(String) # OTP_REQUIRED, CAPTCHA_TRIGGERED, etc.
    screenshot_path = Column(String)
    date_applied = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    retry_after = Column(DateTime, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("DBJob", back_populates="application")

class DBRun(Base):
    __tablename__ = 'runs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    site = Column(String)
    jobs_found = Column(Integer, default=0)
    jobs_eligible = Column(Integer, default=0)
    jobs_applied = Column(Integer, default=0)
    jobs_skipped = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DBError(Base):
    __tablename__ = 'errors'
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, nullable=True)
    job_title = Column(String)
    error_message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DBScreenshot(Base):
    __tablename__ = 'screenshots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_title = Column(String)
    step = Column(String)
    path = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
