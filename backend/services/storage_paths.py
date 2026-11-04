# ============================================================
# CENTRALIZED STORAGE CONFIGURATION
# AI MULTI-AGENT RESEARCH AND AUTOMATION SYSTEM
# ============================================================

# Import os to read environment variables.
import os

# Import Path to manage filesystem paths.
from pathlib import Path


# Find the project root directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Read the storage directory from environment variables.
# Local development uses the project root.
# Render deployment uses /var/data.
DATA_DIRECTORY = Path(
    os.getenv("APP_DATA_DIR", str(PROJECT_ROOT))
).expanduser()


# Create the storage directory if it does not exist.
DATA_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


# Central SQLite database used by all backend services.
DATABASE_PATH = DATA_DIRECTORY / "research_tasks.db"


# Central directory for Markdown reports and JSON metadata.
REPORTS_DIRECTORY = DATA_DIRECTORY / "reports"


# Create the reports directory automatically.
REPORTS_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)