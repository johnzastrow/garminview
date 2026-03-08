from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent / "templates"


def generate_weekly_pdf(data: dict) -> bytes:
    """Render the weekly report HTML template and convert to PDF bytes."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("weekly_report.html")
    html_content = template.render(**data)
    return HTML(string=html_content).write_pdf()
