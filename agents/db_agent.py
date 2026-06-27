from database.database import SessionLocal, init_db
from database.models import Job, Company, Application
from loguru import logger
from datetime import datetime

class DBAgent:
    def __init__(self):
        init_db()
        self.db = SessionLocal()
        
    def __del__(self):
        try:
            self.db.close()
        except:
            pass

    def get_or_create_company(self, name: str) -> Company:
        company = self.db.query(Company).filter(Company.name == name).first()
        if not company:
            company = Company(name=name)
            self.db.add(company)
            self.db.commit()
            self.db.refresh(company)
        return company

    def job_exists(self, url: str) -> bool:
        if not url:
            return False
        return self.db.query(Job).filter(Job.external_url == url).first() is not None

    def save_evaluation(self, job_details: dict, match_score: int, would_apply: bool):
        url = job_details.get("url")
        if not url or self.job_exists(url):
            return
            
        company_name = job_details.get("company", "Unknown Company")
        company = self.get_or_create_company(company_name)
        
        # Save Job
        job = Job(
            title=job_details.get("title", "Unknown"),
            company_id=company.id,
            description=job_details.get("description", ""),
            external_url=url,
            posting_date=datetime.utcnow()
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Save Application Record
        app = Application(
            job_id=job.id,
            status="would_apply" if would_apply else "skipped",
            ai_score=match_score,
            notes="profile.json / skills.json"
        )
        self.db.add(app)
        self.db.commit()
        
        status_str = "SAVED TO APPLY" if would_apply else "SAVED AS SKIPPED"
        logger.info(f"DB Entry Created: {status_str} -> {job.title} at {company.name}")
