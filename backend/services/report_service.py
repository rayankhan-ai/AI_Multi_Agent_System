# ============================================================
# - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# - REPORT SAVING SERVICE
# ============================================================

# Import re to clean report titles for filenames.
import re

# Import datetime to generate unique timestamps.
from datetime import datetime

# Import Path to work with filesystem paths.
from pathlib import Path

# Import typing for type hints.
from typing import Optional

from backend.services.storage_paths import REPORTS_DIRECTORY

# Use the centralized report storage directory.
REPORTS_FOLDER = REPORTS_DIRECTORY

def create_safe_filename(title: str) -> str:
    """
    Convert a report title into a filename-safe string.
    """

    # Replace missing titles with a default title.
    if not title or not title.strip():
        title = "research_report"

    # Convert the title to lowercase.
    filename = title.lower().strip()

    # Replace spaces and repeated whitespace with underscores.
    filename = re.sub(r"\s+", "_", filename)

    # Remove characters that are unsafe or unsuitable for filenames.
    filename = re.sub(r"[^a-z0-9_-]", "", filename)

    # Avoid an empty filename after cleaning.
    if not filename:
        filename = "research_report"

    # Limit the length to keep filenames manageable.
    return filename[:80]


def save_research_report(
    report_content: str,
    title: Optional[str] = None,
) -> dict:
    """
    Save a research report as a Markdown file.

    Parameters:
        report_content: The generated Markdown report.
        title: Optional title used to create the filename.

    Returns:
        A dictionary containing the save status and file information.
    """

    # Reject empty report content.
    if not report_content or not report_content.strip():
        return {
            "success": False,
            "message": "Cannot save an empty research report.",
            "file_path": "",
            "filename": "",
        }

    try:
        # Create the reports directory if it does not exist.
        REPORTS_FOLDER.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Use a provided title or extract one from the report.
        report_title = title

        if not report_title:
            for line in report_content.splitlines():
                # Use the first Markdown heading as the title.
                if line.strip().startswith("# "):
                    report_title = line.strip()[2:].strip()
                    break

        # Apply a default title if no heading was found.
        if not report_title:
            report_title = "research_report"

        # Clean the title before using it in a filename.
        safe_title = create_safe_filename(report_title)

        # Generate a timestamp to reduce filename collisions.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Construct the Markdown filename.
        filename = f"{safe_title}_{timestamp}.md"

        # Construct the full file path.
        file_path = REPORTS_FOLDER / filename

        # Save the report using UTF-8 encoding.
        file_path.write_text(
            report_content,
            encoding="utf-8",
        )

        # Return information about the saved report.
        return {
            "success": True,
            "message": "Research report saved successfully.",
            "file_path": str(file_path),
            "filename": filename,
        }

    except OSError as error:
        # Handle filesystem errors such as permission problems.
        return {
            "success": False,
            "message": (
                "Unable to save the research report: "
                f"{type(error).__name__}: {error}"
            ),
            "file_path": "",
            "filename": "",
        }