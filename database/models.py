from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    url = Column(String)
    
    jobs = relationship("Job", back_populates="company")

class Job(Base):
    __tablename__ = 'jobs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_job_id = Column(String, unique=True, nullable=True) # ID from Redrob or ATS
    title = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    location = Column(String)
    salary = Column(String)
    description = Column(Text)
    skills = Column(String) # Comma separated
    job_type = Column(String) # Internal or External
    external_url = Column(String)
    posting_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job")

class Resume(Base):
    __tablename__ = 'resumes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    applications = relationship("Application", back_populates="resume")

class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    resume_id = Column(Integer, ForeignKey('resumes.id'), nullable=True)
    status = Column(String, default="pending") # pending, applied, rejected, manual_review
    ai_score = Column(Float)
    ats_type = Column(String)
    application_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
    
    job = relationship("Job", back_populates="applications")
    resume = relationship("Resume", back_populates="applications")

class Log(Base):
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String)
    message = Column(Text)
