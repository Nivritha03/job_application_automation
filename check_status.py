import sqlite3
from datetime import datetime

def check_status():
    conn = None
    try:
        conn = sqlite3.connect("jobs.db")
        cursor = conn.cursor()
        
        # 1. Overall Lifetime Counts
        cursor.execute("SELECT COUNT(*) FROM jobs")
        total_jobs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'applied' OR applied = 1")
        total_applied = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'dry_run'")
        total_dry_run = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'pending_review'")
        total_pending_review = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'error'")
        total_error = cursor.fetchone()[0]
        
        # 2. Today's Submissions (Local Time)
        today_date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) FROM applications 
            WHERE (status = 'applied' OR applied = 1) 
              AND date_applied LIKE ?
        """, (f"{today_date}%",))
        applied_today = cursor.fetchone()[0]
        
        # 3. Print Dashboard Header
        print("=" * 80)
        print("                         AI JOB AGENT STATUS REPORT                     ")
        print("=" * 80)
        print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)
        print(f"Total Discovered Jobs : {total_jobs}")
        print(f"Real Submissions (All): {total_applied}  (Today: {applied_today})")
        print(f"Dry-Runs Conducted    : {total_dry_run}")
        print(f"Pending Review        : {total_pending_review}")
        print(f"Failed / Errors       : {total_error}")
        print("-" * 80)
        
        # 4. Per-Platform Grid
        platforms = [
            "greenhouse", "lever", "ashby", "workable", "linkedin",
            "naukri", "instahyre", "wellfound", "indeed", "glassdoor",
            "foundit", "hirist", "cutshort"
        ]
        
        print(f"{'Platform':<15} | {'Discovered':<10} | {'Matched':<8} | {'Applied':<8} | {'Dry-Run':<8} | {'Review':<8} | {'Failed':<8}")
        print("-" * 80)
        
        for plat in platforms:
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE site = ?", (plat,))
            disc = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM applications a 
                JOIN jobs j ON a.job_id = j.id 
                WHERE j.site = ? AND a.status IN ('applied', 'dry_run', 'pending_review')
            """, (plat,))
            matched = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM applications a 
                JOIN jobs j ON a.job_id = j.id 
                WHERE j.site = ? AND (a.status = 'applied' OR a.applied = 1)
            """, (plat,))
            app = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM applications a 
                JOIN jobs j ON a.job_id = j.id 
                WHERE j.site = ? AND a.status = 'dry_run'
            """, (plat,))
            dr = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM applications a 
                JOIN jobs j ON a.job_id = j.id 
                WHERE j.site = ? AND a.status = 'pending_review'
            """, (plat,))
            rev = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM applications a 
                JOIN jobs j ON a.job_id = j.id 
                WHERE j.site = ? AND a.status = 'error'
            """, (plat,))
            err = cursor.fetchone()[0]
            
            # Print row
            print(f"{plat.capitalize():<15} | {disc:<10} | {matched:<8} | {app:<8} | {dr:<8} | {rev:<8} | {err:<8}")
            
        print("-" * 80)
        
        # 5. Fetch last 10 applications
        cursor.execute("""
            SELECT j.title, c.name, j.site, a.status, a.date_applied, a.timestamp
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN companies c ON j.company_id = c.id
            ORDER BY COALESCE(a.date_applied, a.timestamp) DESC
            LIMIT 10
        """)
        recent_jobs = cursor.fetchall()
        
        if recent_jobs:
            print("\n--- RECENT APPLICATIONS (LAST 10) ---")
            print(f"{'Company':<15} | {'Job Title':<30} | {'Platform':<10} | {'Status':<10}")
            print("-" * 75)
            for row in recent_jobs:
                title, company, site, status, date_applied, timestamp = row
                disp_company = company[:15]
                disp_title = title[:30]
                disp_site = site[:10]
                disp_status = status[:10]
                print(f"{disp_company:<15} | {disp_title:<30} | {disp_site:<10} | {disp_status:<10}")
        else:
            print("\nNo applications processed yet.")
            
        print("=" * 80)
        
    except Exception as e:
        print(f"Error reading status from database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_status()
