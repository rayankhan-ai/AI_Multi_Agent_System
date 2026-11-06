# ============================================================
# POSTGRESQL RESEARCH HISTORY
# ============================================================

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.services.database import get_connection


def create_research_metadata(
    research_question: str,
) -> Dict[str, str]:
    """Create metadata for a research execution."""

    return {
        "research_id": str(uuid4()),
        "research_timestamp": datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds"),
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
    """Save research metadata in PostgreSQL."""

    if not report_filename:
        raise ValueError("A report filename is required.")

    research_id = metadata.get("research_id")

    if not research_id:
        raise ValueError("Research ID is missing from metadata.")

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

    created_at = metadata.get(
        "research_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO research_metadata (
                research_id,
                report_filename,
                quality_score,
                total_sources,
                accepted_sources,
                rejected_sources,
                metadata,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)

            ON CONFLICT (research_id)
            DO UPDATE SET
                report_filename = EXCLUDED.report_filename,
                quality_score = EXCLUDED.quality_score,
                total_sources = EXCLUDED.total_sources,
                accepted_sources = EXCLUDED.accepted_sources,
                rejected_sources = EXCLUDED.rejected_sources,
                metadata = EXCLUDED.metadata,
                created_at = EXCLUDED.created_at
            """,
            (
                research_id,
                report_filename,
                quality_score,
                total_sources,
                accepted_sources,
                rejected_sources,
                Jsonb(complete_metadata),
                created_at,
            ),
        )

    return {
        "success": True,
        "metadata_filename": report_filename.replace(
            ".md",
            ".json",
        ),
        "metadata_path": (
            f"database://research_metadata/{research_id}"
        ),
        "metadata": complete_metadata,
    }


def get_research_history() -> Dict[str, Any]:
    """Retrieve research history from PostgreSQL."""

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                research_id,
                report_filename,
                quality_score,
                total_sources,
                accepted_sources,
                rejected_sources,
                metadata,
                created_at
            FROM research_metadata
            ORDER BY created_at DESC
            """
        ).fetchall()

    history = []

    for row in rows:

        record = dict(row)

        # PostgreSQL JSONB is returned as a Python dictionary.
        metadata = record.pop("metadata") or {}

        # Preserve the original history response structure.
        history_record = {
            **metadata,
            "research_id": record["research_id"],
            "report_filename": record["report_filename"],
            "quality_score": record["quality_score"] or 0,
            "total_sources": record["total_sources"] or 0,
            "accepted_sources": record["accepted_sources"] or 0,
            "rejected_sources": record["rejected_sources"] or 0,
            "metadata_filename": record["report_filename"].replace(
                ".md",
                ".json",
            ),
        }

        history.append(history_record)

    return {
        "success": True,
        "total_records": len(history),
        "history": history,
    }


def get_research_by_id(
    research_id: str,
) -> Dict[str, Any]:
    """Retrieve one research history record by its ID."""

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT
                research_id,
                report_filename,
                quality_score,
                total_sources,
                accepted_sources,
                rejected_sources,
                metadata,
                created_at
            FROM research_metadata
            WHERE research_id = %s
            """,
            (research_id,),
        ).fetchone()

    if not row:
        return {
            "success": False,
            "message": (
                f"No research record found for ID: {research_id}"
            ),
        }

    record = dict(row)
    metadata = record.pop("metadata") or {}

    research = {
        **metadata,
        "research_id": record["research_id"],
        "report_filename": record["report_filename"],
        "quality_score": record["quality_score"] or 0,
        "total_sources": record["total_sources"] or 0,
        "accepted_sources": record["accepted_sources"] or 0,
        "rejected_sources": record["rejected_sources"] or 0,
        "metadata_filename": record["report_filename"].replace(
            ".md",
            ".json",
        ),
    }

    return {
        "success": True,
        "research": research,
    }