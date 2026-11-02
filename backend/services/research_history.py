# ============================================================
# PART 18 - RESEARCH HISTORY SERVICE
# ============================================================

# json reads and writes metadata using JSON format.
import json

# datetime handles dates and times.
from datetime import datetime, timezone

# Path manages filesystem paths.
from pathlib import Path

# Any and Dict describe dictionary data types.
from typing import Any, Dict

# uuid4 generates a unique ID for each research task.
from uuid import uuid4


# Folder where Markdown reports and JSON metadata are saved.
REPORTS_DIRECTORY = Path("reports")


def create_research_metadata(research_question: str) -> Dict[str, str]:
    """
    Create unique metadata for a new research task.
    """

    # Generate a unique identifier.
    research_id = str(uuid4())

    # Record the current UTC date and time.
    research_timestamp = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    # Return the initial metadata.
    return {
        "research_id": research_id,
        "research_timestamp": research_timestamp,
        "research_question": research_question.strip(),
    }


def save_research_metadata(
    metadata: Dict[str, Any],
    report_filename: str,
    quality_score: int = 0,
    total_sources: int = 0,
    accepted_sources: int = 0,
    rejected_sources: int = 0,
) -> Dict[str, Any]:
    """
    Save research metadata as a JSON file.
    """

    # Create the reports folder if it does not exist.
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Remove the extension from the Markdown filename.
    report_stem = Path(report_filename).stem

    # Use the same filename for the JSON metadata.
    metadata_filename = f"{report_stem}.json"

    # Resolve the reports folder to its absolute path.
    reports_root = REPORTS_DIRECTORY.resolve()

    # Build the full path to the metadata file.
    metadata_path = (reports_root / metadata_filename).resolve()

    # Prevent the metadata file from being saved outside reports.
    if metadata_path.parent != reports_root:
        raise ValueError(
            "Invalid metadata filename: path must remain inside the reports directory."
        )

    # Combine the research details and statistics.
    complete_metadata = {
        **metadata,
        "report_filename": report_filename,
        "quality_score": quality_score,
        "source_statistics": {
            "total_sources": total_sources,
            "accepted_sources": accepted_sources,
            "rejected_sources": rejected_sources,
        },
    }

    # Convert the metadata dictionary into readable JSON.
    metadata_path.write_text(
        json.dumps(
            complete_metadata,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Return information about the saved JSON file.
    return {
        "success": True,
        "metadata_filename": metadata_filename,
        "metadata_path": str(metadata_path),
        "metadata": complete_metadata,
    }


def get_research_history() -> Dict[str, Any]:
    """
    Read saved JSON metadata files and return research history.
    """

    # Create an empty list for the history records.
    history = []

    # Create the reports folder if it does not exist.
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Find every JSON metadata file in the reports folder.
    metadata_files = REPORTS_DIRECTORY.glob("*.json")

    # Read each metadata file.
    for metadata_file in metadata_files:

        try:
            # Read the JSON file as text.
            metadata_text = metadata_file.read_text(
                encoding="utf-8"
            )

            # Convert the JSON text into a Python dictionary.
            metadata = json.loads(metadata_text)

            # Add the filename for reference.
            metadata["metadata_filename"] = metadata_file.name

            # Add this research task to the history list.
            history.append(metadata)

        except (json.JSONDecodeError, OSError) as error:
            # Skip invalid or unreadable metadata files.
            print(
                f"Warning: Could not read {metadata_file.name}: {error}"
            )

    # Sort the history so the newest research appears first.
    history.sort(
        key=lambda item: item.get("research_timestamp", ""),
        reverse=True,
    )

    # Return the history and the total number of records.
    return {
        "success": True,
        "total_records": len(history),
        "history": history,
    }
    
# ============================================================
# PART 19 - GET ONE RESEARCH RECORD
# ============================================================

def get_research_by_id(research_id: str) -> Dict[str, Any]:
    """
    Retrieve one research record using its unique research ID.
    """

    # Retrieve all saved research history records.
    history_result = get_research_history()

    # Search through the saved records.
    for record in history_result["history"]:

        # Compare the requested ID with the saved ID.
        if record.get("research_id") == research_id:

            # Return the matching research record.
            return {
                "success": True,
                "research": record,
            }

    # Return a not-found response if the ID does not exist.
    return {
        "success": False,
        "message": f"No research record found for ID: {research_id}",
    }