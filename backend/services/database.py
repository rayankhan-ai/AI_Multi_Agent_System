# ============================================================
# CENTRALIZED POSTGRESQL DATABASE
# AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# ============================================================

import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load local environment variables.
# Host-provided environment variables take priority.
load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)

DATABASE_URL = os.getenv("DATABASE_URL")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Create a PostgreSQL connection.

    Dictionary-style rows allow access using column names.
    """

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Check your environment variables."
        )

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=10,
    )


# ============================================================
# DATABASE SCHEMA
# ============================================================

DATABASE_SCHEMA = [

    # --------------------------------------------------------
    # 1. RESEARCH TASKS
    # --------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS research_tasks (
        task_id TEXT PRIMARY KEY,
        research_question TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        error TEXT,
        report_filename TEXT,
        quality_score INTEGER,
        result_json TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        priority TEXT NOT NULL DEFAULT 'normal'
    )
    """,

    # --------------------------------------------------------
    # 2. AGENT EXECUTION LOGS
    # --------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS agent_execution_logs (
        log_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        duration_seconds DOUBLE PRECISION,
        input_summary TEXT,
        output_summary TEXT,
        error_message TEXT
    )
    """,

    # --------------------------------------------------------
    # 3. AGENT RETRY LOGS
    # --------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS agent_retry_logs (
        retry_id TEXT PRIMARY KEY,
        task_id TEXT,
        agent_name TEXT NOT NULL,
        attempt_number INTEGER NOT NULL,
        max_attempts INTEGER NOT NULL,
        status TEXT NOT NULL,
        error_message TEXT,
        delay_seconds DOUBLE PRECISION,
        created_at TEXT NOT NULL
    )
    """,

    # --------------------------------------------------------
    # 4. WORKFLOW TRACES
    # --------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS workflow_traces (
        trace_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        research_question TEXT,
        workflow_status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        duration_seconds DOUBLE PRECISION,
        event_count INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        trace_events TEXT
    )
    """,

    # --------------------------------------------------------
    # 5. TASK DEPENDENCIES
    # --------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS task_dependencies (
        task_id TEXT NOT NULL,
        depends_on_task_id TEXT NOT NULL,

        PRIMARY KEY (
            task_id,
            depends_on_task_id
        ),

        CHECK (
            task_id != depends_on_task_id
        )
    )
    """,

    # --------------------------------------------------------
    # 6. RESEARCH REPORTS
    # --------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS research_reports (
        filename TEXT PRIMARY KEY,
        title TEXT,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,

    # --------------------------------------------------------
    # 7. RESEARCH METADATA
    # --------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS research_metadata (
        research_id TEXT PRIMARY KEY,
        report_filename TEXT NOT NULL,
        quality_score INTEGER,
        total_sources INTEGER DEFAULT 0,
        accepted_sources INTEGER DEFAULT 0,
        rejected_sources INTEGER DEFAULT 0,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TEXT NOT NULL
    )
    """,
]


# ============================================================
# DATABASE INDEXES
# ============================================================

DATABASE_INDEXES = [

    """
    CREATE INDEX IF NOT EXISTS
    idx_research_tasks_status
    ON research_tasks(status)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_research_tasks_priority
    ON research_tasks(priority)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_research_tasks_created_at
    ON research_tasks(created_at)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_agent_logs_task_id
    ON agent_execution_logs(task_id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_agent_logs_agent_name
    ON agent_execution_logs(agent_name)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_retry_logs_task_id
    ON agent_retry_logs(task_id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_workflow_traces_task_id
    ON workflow_traces(task_id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_dependencies_task_id
    ON task_dependencies(task_id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_dependencies_parent
    ON task_dependencies(depends_on_task_id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_research_metadata_report
    ON research_metadata(report_filename)
    """,
]


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def initialize_database():
    """
    Create all required PostgreSQL tables and indexes.

    Existing records are preserved because we use
    CREATE TABLE IF NOT EXISTS.
    """

    with get_connection() as connection:

        # Create tables.
        for statement in DATABASE_SCHEMA:
            connection.execute(statement)

        # Create indexes.
        for statement in DATABASE_INDEXES:
            connection.execute(statement)

    return {
        "success": True,
        "tables_created": len(DATABASE_SCHEMA),
        "indexes_created": len(DATABASE_INDEXES),
        "message": "PostgreSQL database schema initialized successfully.",
    }


# ============================================================
# TEST DATABASE CONNECTION
# ============================================================

def test_database_connection():
    """Verify that PostgreSQL is reachable."""

    with get_connection() as connection:

        result = connection.execute(
            """
            SELECT
                current_database() AS database_name,
                version() AS server_version
            """
        ).fetchone()

        return {
            "success": True,
            "database": result["database_name"],
            "server": result["server_version"].split(",")[0],
            "message": "PostgreSQL connection successful.",
        }


# ============================================================
# VERIFY DATABASE TABLES
# ============================================================

def verify_database_tables():
    """Return the names of the project database tables."""

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        ).fetchall()

    return [
        row["table_name"]
        for row in rows
    ]