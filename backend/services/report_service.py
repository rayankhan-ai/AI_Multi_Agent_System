# ============================================================
# POSTGRESQL RESEARCH REPORT STORAGE
# ============================================================

import re
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional

from backend.services.database import get_connection


def create_safe_filename(title: str) -> str:
    """Convert a report title into a safe filename."""

    if not title or not title.strip():
        title = "research_report"

    filename = title.lower().strip()
    filename = re.sub(r"\s+", "_", filename)
    filename = re.sub(r"[^a-z0-9_-]", "", filename)

    if not filename:
        filename = "research_report"

    return filename[:80]


def save_research_report(
    report_content: str,
    title: Optional[str] = None,
) -> dict:
    """
    Save a Markdown research report in PostgreSQL.

    The report is stored in the research_reports table.
    No local report file is created.
    """

    if not report_content or not report_content.strip():
        return {
            "success": False,
            "message": "Cannot save an empty research report.",
            "file_path": "",
            "filename": "",
        }

    try:
        report_title = title

        if not report_title:
            for line in report_content.splitlines():
                if line.strip().startswith("# "):
                    report_title = line.strip()[2:].strip()
                    break

        if not report_title:
            report_title = "research_report"

        safe_title = create_safe_filename(report_title)

        timestamp = datetime.now(timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = f"{safe_title}_{timestamp}.md"

        with get_connection() as connection:

            # Prevent filename collisions.
            existing = connection.execute(
                """
                SELECT filename
                FROM research_reports
                WHERE filename = %s
                """,
                (filename,),
            ).fetchone()

            if existing:
                filename = (
                    f"{safe_title}_{timestamp}_{uuid4().hex[:8]}.md"
                )

            # Save the complete Markdown content in PostgreSQL.
            connection.execute(
                """
                INSERT INTO research_reports (
                    filename,
                    title,
                    content,
                    created_at
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    filename,
                    report_title,
                    report_content,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        return {
            "success": True,
            "message": "Research report saved successfully in PostgreSQL.",
            "file_path": f"database://research_reports/{filename}",
            "filename": filename,
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Unable to save the research report: {error}",
            "file_path": "",
            "filename": "",
        }