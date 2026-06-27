import sqlite3
import pandas as pd

def main():
    conn = sqlite3.connect("jobs.db")
    
    print("\n--- COMPANIES TABLE ---")
    df_companies = pd.read_sql_query("SELECT * FROM companies", conn)
    print(df_companies)
    
    print("\n--- JOBS TABLE ---")
    df_jobs = pd.read_sql_query("SELECT id, site, title, company_id, location, url, apply_url, search_keyword, date_found FROM jobs", conn)
    print(df_jobs)
    
    print("\n--- APPLICATIONS TABLE ---")
    df_applications = pd.read_sql_query("SELECT id, job_id, resume_used, match_score, applied, status, date_applied, retry_count FROM applications", conn)
    print(df_applications)
    
    print("\n--- SCREENSHOTS TABLE ---")
    df_screenshots = pd.read_sql_query("SELECT * FROM screenshots", conn)
    print(df_screenshots)
    
    print("\n--- RUNS TABLE ---")
    df_runs = pd.read_sql_query("SELECT * FROM runs", conn)
    print(df_runs)

    print("\n--- ERRORS TABLE ---")
    try:
        df_errors = pd.read_sql_query("SELECT * FROM errors", conn)
        print(df_errors)
    except Exception as e:
        print("No errors or table not found:", e)

    conn.close()

if __name__ == "__main__":
    main()
