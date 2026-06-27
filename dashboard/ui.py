from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from database.models import Application, Job
from sqlalchemy.orm import Session

console = Console()

class DashboardUI:
    def __init__(self, db_session: Session):
        self.db = db_session

    def display(self):
        # Fetch stats
        apps_today = self.db.query(Application).count() # Simplified, should filter by today
        success_rate = "95%" # Mock calculation
        
        table = Table(title="Recent Applications")
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("Company", style="magenta")
        table.add_column("Title", style="green")
        table.add_column("Score", justify="right", style="yellow")
        table.add_column("Status", style="blue")

        recent_apps = self.db.query(Application).order_by(Application.id.desc()).limit(5).all()
        for app in recent_apps:
            company_name = app.job.company.name if app.job and app.job.company else "Unknown"
            title = app.job.title if app.job else "Unknown"
            table.add_row(str(app.id), company_name, title, str(app.ai_score), app.status)

        layout = Layout()
        layout.split_column(
            Layout(Panel(f"Applications Today: {apps_today} | Success Rate: {success_rate}", title="AI Job Agent Stats")),
            Layout(table)
        )
        
        console.print(layout)
