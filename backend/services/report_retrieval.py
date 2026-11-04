# ============================================================
#  RESEARCH REPORT RETRIEVAL SERVICE
# ============================================================

# Path helps us safely work with filesystem paths.
from pathlib import Path

# Dict and Any describe the returned dictionary.
from typing import Any, Dict

from backend.services.storage_paths import REPORTS_DIRECTORY


def list_research_reports() -> Dict[str, Any]:
    """
    Return a list of saved Markdown research reports.
    """

    # Create the reports folder if it does not exist.
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Resolve the folder to its absolute location.
    reports_root = REPORTS_DIRECTORY.resolve()

    # Store information about each report.
    reports = []

    # Find Markdown files in the reports folder.
    for report_path in reports_root.glob("*.md"):

        # Ignore anything that is not a regular file.
        if not report_path.is_file():
            continue

        # Read the matching JSON metadata file, if available.
        metadata_path = report_path.with_suffix(".json")

        # Use empty metadata when no JSON file exists.
        metadata = {}

        if metadata_path.is_file():
            try:
                import json

                metadata = json.loads(
                    metadata_path.read_text(encoding="utf-8")
                )

            except (json.JSONDecodeError, OSError):
                # A damaged metadata file should not hide the report.
                metadata = {}

        # Add useful information about this report.
        reports.append(
            {
                "report_filename": report_path.name,
                "report_size_bytes": report_path.stat().st_size,
                "research_id": metadata.get("research_id", ""),
                "research_question": metadata.get(
                    "research_question",
                    "",
                ),
                "research_timestamp": metadata.get(
                    "research_timestamp",
                    "",
                ),
                "quality_score": metadata.get("quality_score", 0),
            }
        )

    # Show the newest research first when timestamps are available.
    reports.sort(
        key=lambda item: item.get("research_timestamp", ""),
        reverse=True,
    )

    # Return the list and number of reports.
    return {
        "success": True,
        "total_reports": len(reports),
        "reports": reports,
    }


def get_research_report(report_filename: str) -> Dict[str, Any]:
    """
    Retrieve the contents of one Markdown research report.
    """

    # Accept only a plain filename, not a path to another directory.
    requested_path = Path(report_filename)

    if (
        requested_path.name != report_filename
        or requested_path.is_absolute()
        or requested_path.suffix.lower() != ".md"
    ):
        return {
            "success": False,
            "message": "Invalid report filename. Provide a Markdown filename only.",
        }

    # Resolve the reports folder.
    reports_root = REPORTS_DIRECTORY.resolve()

    # Build the path to the requested report.
    report_path = (reports_root / report_filename).resolve()

    # Ensure the final path stays directly inside the reports folder.
    if report_path.parent != reports_root:
        return {
            "success": False,
            "message": "Invalid report path.",
        }

    # Return a clear message when the file does not exist.
    if not report_path.is_file():
        return {
            "success": False,
            "message": f"Research report '{report_filename}' was not found.",
        }

    try:
        # Read the complete Markdown report.
        report_content = report_path.read_text(encoding="utf-8")

    except OSError as error:
        # Handle filesystem errors gracefully.
        return {
            "success": False,
            "message": f"Could not read the research report: {error}",
        }

    # Return the report filename and content.
    return {
        "success": True,
        "report_filename": report_path.name,
        "report_content": report_content,
    }
    
# ============================================================
#  PREPARE REPORT FOR DOWNLOAD
# ============================================================

def get_research_report_path(report_filename: str) -> Path:
    """
    Validate a report filename and return its full filesystem path.

    Raises ValueError when the filename is invalid.
    Raises FileNotFoundError when the report does not exist.
    """

    # Convert the supplied filename into a Path object.
    requested_path = Path(report_filename)

    # Only accept a plain Markdown filename.
    if (
        requested_path.name != report_filename
        or requested_path.is_absolute()
        or requested_path.suffix.lower() != ".md"
    ):
        raise ValueError(
            "Invalid report filename. Provide a Markdown filename only."
        )

    # Resolve the reports directory to its absolute path.
    reports_root = REPORTS_DIRECTORY.resolve()

    # Build the full path to the requested report.
    report_path = (reports_root / report_filename).resolve()

    # Ensure the report remains directly inside the reports directory.
    if report_path.parent != reports_root:
        raise ValueError("Invalid report path.")

    # Ensure the requested file exists and is a regular file.
    if not report_path.is_file():
        raise FileNotFoundError(
            f"Research report '{report_filename}' was not found."
        )

    # Return the validated path.
    return report_path