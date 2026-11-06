# ============================================================
# POSTGRESQL RESEARCH REPORT RETRIEVAL
# ============================================================

from pathlib import Path
from typing import Any, Dict

from backend.services.database import get_connection


def validate_report_filename(report_filename: str) -> bool:
    """Accept only a plain Markdown filename."""

    requested_path = Path(report_filename)

    return (
        requested_path.name == report_filename
        and not requested_path.is_absolute()
        and requested_path.suffix.lower() == ".md"
    )


def list_research_reports() -> Dict[str, Any]:
    """List reports stored in PostgreSQL."""

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                r.filename,
                r.title,
                r.content,
                r.created_at,
                m.research_id,
                m.quality_score,
                m.metadata
            FROM research_reports AS r

            LEFT JOIN research_metadata AS m
                ON r.filename = m.report_filename

            ORDER BY r.created_at DESC
            """
        ).fetchall()

    reports = []

    for row in rows:

        content = row["content"] or ""
        metadata = row["metadata"] or {}

        reports.append(
            {
                "report_filename": row["filename"],
                "report_size_bytes": len(
                    content.encode("utf-8")
                ),
                "research_id": row["research_id"] or "",
                "research_question": metadata.get(
                    "research_question",
                    "",
                ),
                "research_timestamp": row["created_at"],
                "quality_score": row["quality_score"] or 0,
                "title": row["title"] or "",
            }
        )

    return {
        "success": True,
        "total_reports": len(reports),
        "reports": reports,
    }


def get_research_report(
    report_filename: str,
) -> Dict[str, Any]:
    """Retrieve a complete Markdown report from PostgreSQL."""

    if not validate_report_filename(report_filename):
        return {
            "success": False,
            "message": (
                "Invalid report filename. "
                "Provide a Markdown filename only."
            ),
        }

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT filename, title, content, created_at
            FROM research_reports
            WHERE filename = %s
            """,
            (report_filename,),
        ).fetchone()

    if not row:
        return {
            "success": False,
            "message": (
                f"Research report '{report_filename}' was not found."
            ),
        }

    return {
        "success": True,
        "report_filename": row["filename"],
        "report_content": row["content"],
        "title": row["title"] or "",
        "created_at": row["created_at"],
    }


def get_research_report_path(report_filename: str):
    """
    Kept temporarily for compatibility.

    Reports are now stored in PostgreSQL, so they do not have
    physical filesystem paths.
    """

    raise RuntimeError(
        "Reports are stored in PostgreSQL. "
        "Use get_research_report() to retrieve report content."
    )