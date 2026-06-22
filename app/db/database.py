import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from app.core.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_INITIALIZED_PATHS: set[str] = set()
_INIT_LOCK = Lock()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    nickname TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'active',
    is_active INTEGER NOT NULL DEFAULT 1,
    password_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    education_level TEXT,
    degree TEXT,
    major TEXT,
    graduation_year INTEGER,
    is_fresh_graduate INTEGER,
    political_status TEXT,
    target_region TEXT,
    target_exam_type TEXT,
    target_job_type TEXT,
    score_estimate REAL,
    work_preference TEXT,
    risk_preference TEXT,
    raw_profile_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '新会话',
    scene TEXT NOT NULL DEFAULT 'general_chat',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_message_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    intent TEXT NOT NULL DEFAULT '',
    rag_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    session_id INTEGER,
    message_id INTEGER,
    request_id TEXT NOT NULL UNIQUE,
    question TEXT NOT NULL,
    intent TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    rag_used INTEGER NOT NULL DEFAULT 0,
    rag_answer TEXT NOT NULL DEFAULT '',
    llm_used INTEGER NOT NULL DEFAULT 0,
    tool_used INTEGER NOT NULL DEFAULT 0,
    used_tools_json TEXT NOT NULL DEFAULT '[]',
    trace_json TEXT NOT NULL DEFAULT '[]',
    citations_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]',
    latency_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_run_id INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    tool_input_json TEXT NOT NULL DEFAULT '{}',
    tool_output_summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favorite_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    job_name TEXT NOT NULL DEFAULT '',
    department_name TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    exam_type TEXT NOT NULL DEFAULT '',
    raw_job_json TEXT NOT NULL DEFAULT '{}',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, job_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id INTEGER,
    title TEXT NOT NULL,
    report_type TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    related_jobs_json TEXT NOT NULL DEFAULT '[]',
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS import_tasks (
    task_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL DEFAULT '',
    detected_type TEXT NOT NULL DEFAULT '',
    detected_type_label TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    province TEXT NOT NULL DEFAULT '',
    exam_type TEXT NOT NULL DEFAULT '',
    year INTEGER,
    total_rows INTEGER NOT NULL DEFAULT 0,
    valid_rows INTEGER NOT NULL DEFAULT 0,
    warning_rows INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PREVIEW_READY',
    target TEXT NOT NULL DEFAULT '',
    inserted_rows INTEGER NOT NULL DEFAULT 0,
    skipped_rows INTEGER NOT NULL DEFAULT 0,
    source_kind TEXT NOT NULL DEFAULT 'imported',
    storage TEXT NOT NULL DEFAULT 'database',
    field_mapping_json TEXT NOT NULL DEFAULT '{}',
    preview_rows_json TEXT NOT NULL DEFAULT '[]',
    import_report_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS import_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    row_index INTEGER,
    level TEXT NOT NULL DEFAULT 'warning',
    message TEXT NOT NULL DEFAULT '',
    raw_value_json TEXT NOT NULL DEFAULT 'null',
    field TEXT NOT NULL DEFAULT '',
    source_column TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES import_tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS import_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    province TEXT NOT NULL DEFAULT '',
    exam_type TEXT NOT NULL DEFAULT '',
    source_keyword TEXT NOT NULL DEFAULT '',
    sheet_keyword TEXT NOT NULL DEFAULT '',
    header_signature TEXT NOT NULL DEFAULT '',
    header_row INTEGER,
    sub_header_row INTEGER,
    data_start_row INTEGER,
    field_mapping_json TEXT NOT NULL DEFAULT '{}',
    outputs_json TEXT NOT NULL DEFAULT '[]',
    required_fields_json TEXT NOT NULL DEFAULT '[]',
    optional_fields_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_task_id TEXT NOT NULL DEFAULT '',
    row_key TEXT NOT NULL UNIQUE,
    year INTEGER,
    province TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    exam_type TEXT NOT NULL DEFAULT '',
    unit_name TEXT NOT NULL DEFAULT '',
    department_name TEXT NOT NULL DEFAULT '',
    job_name TEXT NOT NULL DEFAULT '',
    job_code TEXT NOT NULL DEFAULT '',
    recruit_count INTEGER,
    major_requirement TEXT NOT NULL DEFAULT '',
    degree_requirement TEXT NOT NULL DEFAULT '',
    education_requirement TEXT NOT NULL DEFAULT '',
    political_requirement TEXT NOT NULL DEFAULT '',
    identity_requirement TEXT NOT NULL DEFAULT '',
    grassroots_requirement TEXT NOT NULL DEFAULT '',
    qualification_requirement TEXT NOT NULL DEFAULT '',
    job_description TEXT NOT NULL DEFAULT '',
    contact_phone TEXT NOT NULL DEFAULT '',
    work_address TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    source_file TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    extra_fields_json TEXT NOT NULL DEFAULT '{}',
    source_kind TEXT NOT NULL DEFAULT 'imported',
    storage TEXT NOT NULL DEFAULT 'database',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_score_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_task_id TEXT NOT NULL DEFAULT '',
    row_key TEXT NOT NULL UNIQUE,
    year INTEGER,
    province TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    exam_type TEXT NOT NULL DEFAULT '',
    section_title TEXT NOT NULL DEFAULT '',
    unit_name TEXT NOT NULL DEFAULT '',
    job_name TEXT NOT NULL DEFAULT '',
    job_code TEXT NOT NULL DEFAULT '',
    recruit_count INTEGER,
    interview_count INTEGER,
    major_category TEXT NOT NULL DEFAULT '',
    min_score REAL,
    max_score REAL,
    avg_score REAL,
    source_file TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    extra_fields_json TEXT NOT NULL DEFAULT '{}',
    source_kind TEXT NOT NULL DEFAULT 'imported',
    storage TEXT NOT NULL DEFAULT 'database',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_candidate_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_task_id TEXT NOT NULL DEFAULT '',
    row_key TEXT NOT NULL UNIQUE,
    year INTEGER,
    province TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    exam_type TEXT NOT NULL DEFAULT '',
    data_granularity TEXT NOT NULL DEFAULT 'unknown',
    candidate_no TEXT NOT NULL DEFAULT '',
    candidate_name TEXT NOT NULL DEFAULT '',
    unit_code TEXT NOT NULL DEFAULT '',
    unit_name TEXT NOT NULL DEFAULT '',
    job_code TEXT NOT NULL DEFAULT '',
    job_name TEXT NOT NULL DEFAULT '',
    recruit_count INTEGER,
    xingce_score REAL,
    shenlun_score REAL,
    professional_score REAL,
    written_score REAL,
    interview_score REAL,
    total_score REAL,
    rank INTEGER,
    status TEXT NOT NULL DEFAULT '',
    group_name TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    source_file TEXT NOT NULL DEFAULT '',
    extra_fields_json TEXT NOT NULL DEFAULT '{}',
    source_kind TEXT NOT NULL DEFAULT 'imported',
    storage TEXT NOT NULL DEFAULT 'database',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_review_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_key TEXT NOT NULL UNIQUE,
    import_task_id TEXT NOT NULL DEFAULT '',
    province TEXT NOT NULL DEFAULT '',
    year INTEGER,
    exam_type TEXT NOT NULL DEFAULT '',
    job_code TEXT NOT NULL DEFAULT '',
    job_name TEXT NOT NULL DEFAULT '',
    unit_name TEXT NOT NULL DEFAULT '',
    recruit_count INTEGER,
    candidate_no TEXT NOT NULL DEFAULT '',
    candidate_name TEXT NOT NULL DEFAULT '',
    subject1_name TEXT NOT NULL DEFAULT '',
    subject1_score REAL,
    subject2_name TEXT NOT NULL DEFAULT '',
    subject2_score REAL,
    subject3_name TEXT NOT NULL DEFAULT '',
    subject3_score REAL,
    bonus_score REAL,
    written_score REAL,
    xingce_score REAL,
    shenlun_score REAL,
    professional_score REAL,
    total_score REAL,
    rank INTEGER,
    review_status TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    source_file TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL DEFAULT 'imported',
    storage TEXT NOT NULL DEFAULT 'database',
    raw_row_json TEXT NOT NULL DEFAULT '[]',
    extra_fields_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_signup_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_task_id TEXT NOT NULL DEFAULT '',
    row_key TEXT NOT NULL UNIQUE,
    year INTEGER,
    province TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    exam_type TEXT NOT NULL DEFAULT '',
    unit_name TEXT NOT NULL DEFAULT '',
    job_name TEXT NOT NULL DEFAULT '',
    job_code TEXT NOT NULL DEFAULT '',
    recruit_count INTEGER,
    signup_count INTEGER,
    approved_count INTEGER,
    paid_count INTEGER,
    competition_ratio REAL,
    source_file TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    extra_fields_json TEXT NOT NULL DEFAULT '{}',
    source_kind TEXT NOT NULL DEFAULT 'imported',
    storage TEXT NOT NULL DEFAULT 'database',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_major_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_task_id TEXT NOT NULL DEFAULT '',
    row_key TEXT NOT NULL UNIQUE,
    year INTEGER,
    province TEXT NOT NULL DEFAULT '',
    major_name TEXT NOT NULL DEFAULT '',
    major_code TEXT NOT NULL DEFAULT '',
    major_category TEXT NOT NULL DEFAULT '',
    degree_level TEXT NOT NULL DEFAULT '',
    source_file TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    extra_fields_json TEXT NOT NULL DEFAULT '{}',
    source_kind TEXT NOT NULL DEFAULT 'imported',
    storage TEXT NOT NULL DEFAULT 'database',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_updated
    ON chat_sessions(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session_created
    ON chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_user_created
    ON agent_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run
    ON tool_calls(agent_run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reports_user_created
    ON analysis_reports(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_tasks_updated
    ON import_tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_warnings_task
    ON import_warnings(task_id, id);
CREATE INDEX IF NOT EXISTS idx_import_templates_lookup
    ON import_templates(data_type, province, exam_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_exam_jobs_scope
    ON exam_jobs(province, year, exam_type, job_code);
CREATE INDEX IF NOT EXISTS idx_exam_score_lines_scope
    ON exam_score_lines(province, year, exam_type, job_code);
CREATE INDEX IF NOT EXISTS idx_exam_candidate_scores_scope
    ON exam_candidate_scores(province, year, exam_type, job_code);
CREATE INDEX IF NOT EXISTS idx_exam_review_candidates_scope
    ON exam_review_candidates(province, year, exam_type, job_code);
CREATE INDEX IF NOT EXISTS idx_exam_signup_stats_scope
    ON exam_signup_stats(province, year, exam_type, job_code);
CREATE INDEX IF NOT EXISTS idx_exam_major_catalog_scope
    ON exam_major_catalog(province, year, major_code);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def json_loads(value: Any, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def database_path() -> Path:
    url = str(settings.DATABASE_URL or "").strip()
    prefix = "sqlite:///"
    raw_path = url[len(prefix) :] if url.startswith(prefix) else url
    path = Path(raw_path or "data/exam_agent.db").expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def initialize_database() -> Path:
    path = database_path()
    key = str(path).lower()
    if key in _INITIALIZED_PATHS:
        return path
    with _INIT_LOCK:
        if key in _INITIALIZED_PATHS:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=10)
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA busy_timeout = 5000")
            db.executescript(SCHEMA_SQL)
            _apply_lightweight_migrations(db)
            db.commit()
        finally:
            db.close()
        _INITIALIZED_PATHS.add(key)
    return path


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = initialize_database()
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 5000")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _apply_lightweight_migrations(db: sqlite3.Connection) -> None:
    _ensure_column(
        db,
        table="users",
        column="display_name",
        definition="TEXT NOT NULL DEFAULT ''",
    )
    _ensure_column(
        db,
        table="users",
        column="is_active",
        definition="INTEGER NOT NULL DEFAULT 1",
    )
    _ensure_column(
        db,
        table="exam_candidate_scores",
        column="data_granularity",
        definition="TEXT NOT NULL DEFAULT 'unknown'",
    )
    _ensure_column(
        db,
        table="exam_candidate_scores",
        column="candidate_no",
        definition="TEXT NOT NULL DEFAULT ''",
    )
    _ensure_column(
        db,
        table="exam_candidate_scores",
        column="candidate_name",
        definition="TEXT NOT NULL DEFAULT ''",
    )
    _ensure_column(
        db,
        table="exam_score_lines",
        column="interview_count",
        definition="INTEGER",
    )
    for column in [
        "qualification_requirement",
        "job_description",
        "contact_phone",
        "work_address",
    ]:
        _ensure_column(
            db,
            table="exam_jobs",
            column=column,
            definition="TEXT NOT NULL DEFAULT ''",
        )
    for table in [
        "exam_jobs",
        "exam_score_lines",
        "exam_candidate_scores",
        "exam_review_candidates",
        "exam_signup_stats",
        "exam_major_catalog",
    ]:
        _ensure_column(
            db,
            table=table,
            column="extra_fields_json",
            definition="TEXT NOT NULL DEFAULT '{}'",
        )
    review_candidate_columns = {
        "subject1_name": "TEXT NOT NULL DEFAULT ''",
        "subject1_score": "REAL",
        "subject2_name": "TEXT NOT NULL DEFAULT ''",
        "subject2_score": "REAL",
        "subject3_name": "TEXT NOT NULL DEFAULT ''",
        "subject3_score": "REAL",
        "bonus_score": "REAL",
        "review_status": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in review_candidate_columns.items():
        _ensure_column(
            db,
            table="exam_review_candidates",
            column=column,
            definition=definition,
        )
    for column in ["header_row", "sub_header_row", "data_start_row"]:
        _ensure_column(
            db,
            table="import_templates",
            column=column,
            definition="INTEGER",
        )
    _ensure_column(
        db,
        table="import_templates",
        column="outputs_json",
        definition="TEXT NOT NULL DEFAULT '[]'",
    )
    source_tables = [
        "import_tasks",
        "exam_jobs",
        "exam_score_lines",
        "exam_candidate_scores",
        "exam_review_candidates",
        "exam_signup_stats",
        "exam_major_catalog",
    ]
    for table in source_tables:
        _ensure_column(
            db,
            table=table,
            column="source_kind",
            definition="TEXT NOT NULL DEFAULT 'imported'",
        )
        _ensure_column(
            db,
            table=table,
            column="storage",
            definition="TEXT NOT NULL DEFAULT 'database'",
        )

    # Older cleaned-JSON migrations predate source metadata. Preserve their
    # business rows while classifying them as migration data, not user imports.
    db.execute(
        "UPDATE import_tasks SET source_kind = 'migrated' "
        "WHERE task_id LIKE 'migrate_cleaned_%'"
    )
    for table in source_tables[1:]:
        db.execute(
            f"UPDATE {table} SET source_kind = 'migrated' "
            "WHERE import_task_id LIKE 'migrate_cleaned_%'"
        )


def _ensure_column(
    db: sqlite3.Connection,
    *,
    table: str,
    column: str,
    definition: str,
) -> None:
    existing_columns = {
        str(row[1])
        for row in db.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing_columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
