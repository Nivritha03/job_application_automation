import sys
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from core.database import SessionLocal, init_db
from core.models import DBRun, DBJob, DBApplication, DBCompany
from core.browser import PlaywrightManager
from core.plugins import APPLY_ENGINES
from core.models import Job
from loguru import logger

console = Console()

def show_dashboard():
    init_db()
    
    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]AI JOB AGENT - OPERATIONAL CONTROL DASHBOARD[/bold cyan]",
            border_style="cyan"
        ))
        
        console.print("[bold yellow]Menu Options:[/bold yellow]")
        console.print("  [bold green]1.[/bold green] View Run Metrics Summary")
        console.print("  [bold green]2.[/bold green] Manage Pending Review Queue")
        console.print("  [bold green]3.[/bold green] View Retry Queue")
        console.print("  [bold green]4.[/bold green] View Learned Company Profiles")
        console.print("  [bold green]5.[/bold green] Exit Dashboard")
        console.print("")
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5"], default="1")
        
        db = SessionLocal()
        try:
            if choice == "1":
                _show_summary(db)
            elif choice == "2":
                _manage_review_queue(db)
            elif choice == "3":
                _view_retry_queue(db)
            elif choice == "4":
                _view_company_profiles(db)
            elif choice == "5":
                console.print("[bold green]Exiting operational dashboard. Goodbye![/bold green]")
                break
        except Exception as e:
            console.print(f"[bold red]Dashboard Error: {e}[/bold red]")
            time.sleep(2)
        finally:
            db.close()

def _show_summary(db):
    run = db.query(DBRun).order_by(DBRun.timestamp.desc()).first()
    if not run:
        console.print(Panel("[yellow]No runs found in database.[/yellow]"))
        Prompt.ask("\nPress Enter to return to main menu")
        return
        
    table = Table(title="Last Run Statistics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim", width=25)
    table.add_column("Count", justify="right")
    
    table.add_row("Jobs Discovered", str(run.jobs_found))
    table.add_row("Eligible Matches", str(run.jobs_eligible), style="cyan")
    table.add_row("Applied Applications", str(run.jobs_applied), style="green")
    table.add_row("Skipped Throttled", str(run.jobs_skipped), style="yellow")
    table.add_row("Errors Logged", str(run.errors), style="red")
    
    # Aggregated Lifetime metrics
    total_discovered = db.query(DBJob).count()
    total_applied = db.query(DBApplication).filter(DBApplication.applied == True).count()
    total_pending_review = db.query(DBApplication).filter(DBApplication.status == "pending_review").count()
    total_otp_stalled = db.query(DBApplication).filter(DBApplication.status == "otp_required").count()
    total_retries = db.query(DBApplication).filter(DBApplication.status == "failed_retry").count()
    
    table_lifetime = Table(title="Lifetime Database Totals", show_header=True, header_style="bold blue")
    table_lifetime.add_column("Status Category", style="dim", width=25)
    table_lifetime.add_column("Total Count", justify="right")
    table_lifetime.add_row("Total Jobs Scanned", str(total_discovered))
    table_lifetime.add_row("Total Submitted (Applied)", str(total_applied), style="green")
    table_lifetime.add_row("Pending Human Review", str(total_pending_review), style="yellow")
    table_lifetime.add_row("OTP Stalled Verification", str(total_otp_stalled), style="magenta")
    table_lifetime.add_row("Rescheduled Retries", str(total_retries), style="cyan")
    
    console.print("\n")
    console.print(Panel(table, expand=False, border_style="magenta"))
    console.print(Panel(table_lifetime, expand=False, border_style="blue"))
    console.print("\n")
    Prompt.ask("Press Enter to return to main menu")

def _manage_review_queue(db):
    pending_apps = db.query(DBApplication).filter(DBApplication.status == "pending_review").all()
    if not pending_apps:
        console.print(Panel("[bold green]No applications are currently waiting for human review.[/bold green]"))
        Prompt.ask("\nPress Enter to return to main menu")
        return
        
    console.print(f"\n[bold yellow]Found {len(pending_apps)} applications pending review:[/bold yellow]\n")
    
    for idx, app in enumerate(pending_apps, 1):
        db_job = app.job
        if not db_job:
            continue
            
        console.print(Panel(
            f"[bold cyan]Application #{idx}[/bold cyan]\n"
            f"  [bold]Job Title:[/bold]   {db_job.title}\n"
            f"  [bold]Company:[/bold]     {db_job.company.name}\n"
            f"  [bold]Location:[/bold]    {db_job.location}\n"
            f"  [bold]Resume Template:[/bold] {app.resume_used}\n"
            f"  [bold]Screenshot:[/bold]  {app.screenshot_path}\n",
            border_style="yellow"
        ))
        
        action = Prompt.ask(
            "Select action for this application",
            choices=["y", "n", "s"],
            default="y"
        ) # y = approve & submit, n = reject & drop, s = skip for later
        
        if action == "y":
            console.print("[bold green]Submitting application via browser...[/bold green]")
            # Initialize playwright session
            try:
                with PlaywrightManager(headless=False) as context:
                    page = context.new_page()
                    
                    # Convert to Pydantic Job model
                    job = Job(
                        id=db_job.external_job_id,
                        title=db_job.title,
                        company=db_job.company.name,
                        location=db_job.location,
                        salary=db_job.salary,
                        description=db_job.description,
                        requirements=db_job.requirements,
                        url=db_job.url,
                        skills=db_job.skills.split(",") if db_job.skills else [],
                        resume_used=app.resume_used
                    )
                    
                    apply_class = APPLY_ENGINES.get(db_job.site, APPLY_ENGINES["universal"])
                    apply_engine = apply_class(page)
                    
                    # Run live submit apply
                    success = apply_engine.apply(job, dry_run=False)
                    
                    if success:
                        app.applied = True
                        app.status = "applied"
                        app.date_applied = datetime.utcnow()
                        app.error_message = ""
                        console.print(f"[bold green][OK] Application to '{db_job.title}' submitted successfully![/bold green]")
                    else:
                        console.print(f"[bold red][FAIL] Submission failed or requested verification code.[/bold red]")
                        # Check if verification code was requested
                        # Save state
                        from core.pipeline import Pipeline
                        temp_pipeline = Pipeline(site=db_job.site)
                        failure_type = temp_pipeline._classify_failure(page)
                        app.failure_type = failure_type
                        if failure_type == "OTP_REQUIRED":
                            app.status = "otp_required"
                        else:
                            app.status = "failed_retry"
                            app.retry_after = datetime.utcnow()
            except Exception as e:
                console.print(f"[bold red]Submission failed with error: {e}[/bold red]")
                
            db.commit()
            time.sleep(1.5)
            
        elif action == "n":
            console.print(f"[bold red]Dropped application to {db_job.title}.[/bold red]")
            app.status = "rejected"
            db.commit()
            time.sleep(1)
            
        elif action == "s":
            console.print("Skipped.")
            continue

def _view_retry_queue(db):
    retries = db.query(DBApplication).filter(DBApplication.status == "failed_retry").all()
    if not retries:
        console.print(Panel("[bold green]Retry queue is empty.[/bold green]"))
        Prompt.ask("\nPress Enter to return to main menu")
        return
        
    table = Table(title="Active Retry Queue", show_header=True, header_style="bold cyan")
    table.add_column("Job Title", style="dim")
    table.add_column("Company")
    table.add_column("Attempt", justify="center")
    table.add_column("Scheduled Retry After", justify="center")
    table.add_column("Last Error Details")
    
    for r in retries:
        db_job = r.job
        retry_time_str = r.retry_after.strftime("%Y-%m-%d %H:%M:%S") if r.retry_after else "N/A"
        table.add_row(
            db_job.title if db_job else "unknown",
            db_job.company.name if db_job and db_job.company else "unknown",
            str(r.retry_count),
            retry_time_str,
            r.error_message or "Unknown failure"
        )
        
    console.print("\n")
    console.print(table)
    console.print("\n")
    Prompt.ask("Press Enter to return to main menu")

def _view_company_profiles(db):
    companies = db.query(DBCompany).all()
    if not companies:
        console.print(Panel("[bold yellow]No company capability profiles learned yet.[/bold yellow]"))
        Prompt.ask("\nPress Enter to return to main menu")
        return
        
    table = Table(title="Learned Company Capability Profiles", show_header=True, header_style="bold green")
    table.add_column("Company Board", style="bold")
    table.add_column("OTP Always Required", justify="center")
    table.add_column("Easy Apply", justify="center")
    table.add_column("Resume First", justify="center")
    table.add_column("Questions count", justify="center")
    table.add_column("Avg Completion", justify="right")
    
    for c in companies:
        table.add_row(
            c.name,
            "Yes" if c.otp_required else "No",
            "Yes" if c.supports_easy_apply else "No",
            "Yes" if c.resume_upload_first else "No",
            str(c.questions_count or 0),
            f"{c.average_completion_time or 0.0:.1f}s"
        )
        
    console.print("\n")
    console.print(table)
    console.print("\n")
    Prompt.ask("Press Enter to return to main menu")
