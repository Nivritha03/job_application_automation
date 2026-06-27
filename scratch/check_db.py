from core.database import SessionLocal, init_db
from core.models import DBCompany, DBApplication, DBJob

init_db()
db = SessionLocal()

print("--- COMPANIES IN DB ---")
companies = db.query(DBCompany).all()
for c in companies:
    print(f"Company: {c.name}")
    print(f"  OTP Required: {c.otp_required}")
    print(f"  Supports Easy Apply: {c.supports_easy_apply}")
    print(f"  Resume Upload First: {c.resume_upload_first}")
    print(f"  Questions Count: {c.questions_count}")
    print(f"  Average Completion Time: {c.average_completion_time:.2f}s")
    
print("\n--- APPLICATIONS IN DB ---")
apps = db.query(DBApplication).all()
for a in apps:
    job = db.query(DBJob).filter(DBJob.id == a.job_id).first()
    print(f"Job: {job.title if job else 'unknown'} at {job.company.name if job and job.company else 'unknown'}")
    print(f"  Resume Used: {a.resume_used}")
    print(f"  Applied: {a.applied}")
    print(f"  Status: {a.status}")
    print(f"  Failure Type: {a.failure_type}")
    print(f"  Error Message: {a.error_message}")
    
db.close()
