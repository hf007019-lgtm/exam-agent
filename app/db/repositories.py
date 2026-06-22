from typing import Any, Iterable

from app.db.database import connection, json_dumps, json_loads, utc_now


USER_PUBLIC_FIELDS = (
    "id",
    "username",
    "nickname",
    "display_name",
    "phone",
    "email",
    "avatar_url",
    "role",
    "status",
    "is_active",
    "created_at",
    "updated_at",
    "last_login_at",
)
PROFILE_FIELDS = (
    "education_level",
    "degree",
    "major",
    "graduation_year",
    "is_fresh_graduate",
    "political_status",
    "target_region",
    "target_exam_type",
    "target_job_type",
    "score_estimate",
    "work_preference",
    "risk_preference",
)
SESSION_SCENES = {
    "job_recommendation",
    "policy_qa",
    "score_analysis",
    "general_chat",
}
MESSAGE_ROLES = {"user", "assistant", "system", "tool"}


def _row_dict(row, json_fields: Iterable[str] = ()) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for field in json_fields:
        fallback = {}
        if field in {
            "used_tools_json",
            "trace_json",
            "citations_json",
            "sources_json",
            "related_jobs_json",
        }:
            fallback = []
        data[field] = json_loads(data.get(field), fallback)
    for field in ("rag_used", "llm_used", "tool_used", "is_fresh_graduate", "is_active"):
        if field in data and data[field] is not None:
            data[field] = bool(data[field])
    return data


def _public_user(row) -> dict[str, Any] | None:
    data = _row_dict(row)
    if not data:
        return None
    if not data.get("display_name"):
        data["display_name"] = data.get("nickname") or data.get("username") or ""
    if "is_active" not in data or data.get("is_active") is None:
        data["is_active"] = data.get("status") == "active"
    return {field: data.get(field) for field in USER_PUBLIC_FIELDS}


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _public_user(row)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    return _public_user(row)


def get_auth_user_by_username(username: str) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    return _row_dict(row)


def create_password_user(
    *,
    username: str,
    email: str,
    password_hash: str,
    display_name: str = "",
) -> dict[str, Any]:
    now = utc_now()
    clean_username = username.strip()
    clean_display_name = display_name.strip() or clean_username
    if get_user_by_username(clean_username):
        raise ValueError("用户名已存在")
    with connection() as db:
        db.execute(
            """
            INSERT INTO users (
                username, nickname, display_name, email, role, status,
                is_active, password_hash, created_at, updated_at, last_login_at
            ) VALUES (?, ?, ?, ?, 'user', 'active', 1, ?, ?, ?, NULL)
            """,
            (
                clean_username,
                clean_display_name,
                clean_display_name,
                email.strip(),
                password_hash,
                now,
                now,
            ),
        )
        row = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (clean_username,),
        ).fetchone()
    user = _public_user(row)
    if not user:
        raise RuntimeError("创建用户失败")
    return user


def mark_user_login(user_id: int) -> dict[str, Any]:
    now = utc_now()
    with connection() as db:
        db.execute(
            """
            UPDATE users
            SET last_login_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, user_id),
        )
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    user = _public_user(row)
    if not user:
        raise RuntimeError("更新登录时间失败")
    return user


def upsert_dev_user(username: str, nickname: str = "") -> dict[str, Any]:
    now = utc_now()
    clean_username = username.strip()
    requested_nickname = nickname.strip()
    existing = get_user_by_username(clean_username)
    clean_nickname = (
        requested_nickname
        or (existing or {}).get("nickname")
        or clean_username
    )
    with connection() as db:
        db.execute(
            """
            INSERT INTO users (
                username, nickname, display_name, role, status, is_active,
                created_at, updated_at, last_login_at
            ) VALUES (?, ?, ?, 'user', 'active', 1, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                nickname = CASE
                    WHEN excluded.nickname <> '' THEN excluded.nickname
                    ELSE users.nickname
                END,
                display_name = CASE
                    WHEN excluded.display_name <> '' THEN excluded.display_name
                    ELSE users.display_name
                END,
                is_active = 1,
                status = 'active',
                updated_at = excluded.updated_at,
                last_login_at = excluded.last_login_at
            """,
            (clean_username, clean_nickname, clean_nickname, now, now, now),
        )
        row = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (clean_username,),
        ).fetchone()
    user = _public_user(row)
    if not user:
        raise RuntimeError("创建开发用户失败")
    return user


def get_user_profile(user_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return _row_dict(row, ("raw_profile_json",))


def upsert_user_profile(user_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    existing = get_user_profile(user_id) or {}
    now = utc_now()
    values = {field: existing.get(field) for field in PROFILE_FIELDS}
    for field in PROFILE_FIELDS:
        if field in updates:
            values[field] = updates[field]
    raw_profile = dict(existing.get("raw_profile_json") or {})
    raw_profile.update(updates.get("raw_profile_json") or {})
    with connection() as db:
        db.execute(
            """
            INSERT INTO user_profiles (
                user_id, education_level, degree, major, graduation_year,
                is_fresh_graduate, political_status, target_region,
                target_exam_type, target_job_type, score_estimate,
                work_preference, risk_preference, raw_profile_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                education_level = excluded.education_level,
                degree = excluded.degree,
                major = excluded.major,
                graduation_year = excluded.graduation_year,
                is_fresh_graduate = excluded.is_fresh_graduate,
                political_status = excluded.political_status,
                target_region = excluded.target_region,
                target_exam_type = excluded.target_exam_type,
                target_job_type = excluded.target_job_type,
                score_estimate = excluded.score_estimate,
                work_preference = excluded.work_preference,
                risk_preference = excluded.risk_preference,
                raw_profile_json = excluded.raw_profile_json,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                values["education_level"],
                values["degree"],
                values["major"],
                values["graduation_year"],
                _bool_db(values["is_fresh_graduate"]),
                values["political_status"],
                values["target_region"],
                values["target_exam_type"],
                values["target_job_type"],
                values["score_estimate"],
                values["work_preference"],
                values["risk_preference"],
                json_dumps(raw_profile),
                existing.get("created_at") or now,
                now,
            ),
        )
    profile = get_user_profile(user_id)
    if not profile:
        raise RuntimeError("保存用户画像失败")
    return profile


def create_session(user_id: int, title: str, scene: str) -> dict[str, Any]:
    now = utc_now()
    normalized_scene = scene if scene in SESSION_SCENES else "general_chat"
    clean_title = title.strip() or "新会话"
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO chat_sessions (
                user_id, title, scene, status, created_at, updated_at, last_message_at
            ) VALUES (?, ?, ?, 'active', ?, ?, ?)
            """,
            (user_id, clean_title[:120], normalized_scene, now, now, now),
        )
        row = db.execute(
            "SELECT * FROM chat_sessions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _row_dict(row) or {}


def list_sessions(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute(
            """
            SELECT s.*,
                (SELECT COUNT(*) FROM chat_messages m WHERE m.session_id = s.id)
                AS message_count
            FROM chat_sessions s
            WHERE s.user_id = ? AND s.status <> 'deleted'
            ORDER BY COALESCE(s.last_message_at, s.updated_at) DESC, s.id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
    return [_row_dict(row) or {} for row in rows]


def get_session(user_id: int, session_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            """
            SELECT s.*,
                (SELECT COUNT(*) FROM chat_messages m WHERE m.session_id = s.id)
                AS message_count
            FROM chat_sessions s
            WHERE s.id = ? AND s.user_id = ? AND s.status <> 'deleted'
            """,
            (session_id, user_id),
        ).fetchone()
    return _row_dict(row)


def delete_session(user_id: int, session_id: int) -> bool:
    now = utc_now()
    with connection() as db:
        cursor = db.execute(
            """
            UPDATE chat_sessions
            SET status = 'deleted', updated_at = ?
            WHERE id = ? AND user_id = ? AND status <> 'deleted'
            """,
            (now, session_id, user_id),
        )
    return cursor.rowcount > 0


def add_message(
    session_id: int,
    user_id: int | None,
    role: str,
    content: str,
    intent: str = "",
    rag_used: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if role not in MESSAGE_ROLES:
        raise ValueError(f"不支持的消息角色：{role}")
    now = utc_now()
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO chat_messages (
                session_id, user_id, role, content, intent, rag_used,
                created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                role,
                content,
                intent,
                int(rag_used),
                now,
                json_dumps(metadata or {}),
            ),
        )
        db.execute(
            """
            UPDATE chat_sessions
            SET updated_at = ?, last_message_at = ?
            WHERE id = ?
            """,
            (now, now, session_id),
        )
        row = db.execute(
            "SELECT * FROM chat_messages WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _row_dict(row, ("metadata_json",)) or {}


def list_messages(
    user_id: int,
    session_id: int,
    limit: int = 200,
) -> list[dict[str, Any]] | None:
    if not get_session(user_id, session_id):
        return None
    with connection() as db:
        rows = db.execute(
            """
            SELECT * FROM (
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) recent
            ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()
    return [_row_dict(row, ("metadata_json",)) or {} for row in rows]


def get_message_by_id(message_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM chat_messages WHERE id = ?",
            (message_id,),
        ).fetchone()
    return _row_dict(row, ("metadata_json",))


def create_agent_run(data: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO agent_runs (
                user_id, session_id, message_id, request_id, question,
                intent, status, rag_used, rag_answer, llm_used, tool_used,
                used_tools_json, trace_json, citations_json, sources_json,
                latency_ms, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("user_id"),
                data.get("session_id"),
                data.get("message_id"),
                data["request_id"],
                data.get("question") or "",
                data.get("intent") or "",
                data.get("status") or "completed",
                int(bool(data.get("rag_used"))),
                data.get("rag_answer") or "",
                int(bool(data.get("llm_used"))),
                int(bool(data.get("tool_used"))),
                json_dumps(data.get("used_tools") or []),
                json_dumps(data.get("trace") or []),
                json_dumps(data.get("citations") or []),
                json_dumps(data.get("sources") or []),
                max(0, int(data.get("latency_ms") or 0)),
                data.get("error_message") or "",
                now,
            ),
        )
        row = db.execute(
            "SELECT * FROM agent_runs WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _run_row(row) or {}


def add_tool_call(
    agent_run_id: int,
    tool_name: str,
    tool_input: dict[str, Any],
    output_summary: str,
    status: str,
    latency_ms: int = 0,
    error_message: str = "",
) -> dict[str, Any]:
    now = utc_now()
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO tool_calls (
                agent_run_id, tool_name, tool_input_json,
                tool_output_summary, status, latency_ms,
                error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_run_id,
                tool_name,
                json_dumps(tool_input),
                output_summary,
                status,
                max(0, int(latency_ms or 0)),
                error_message,
                now,
            ),
        )
        row = db.execute(
            "SELECT * FROM tool_calls WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _row_dict(row, ("tool_input_json",)) or {}


def list_agent_runs(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute(
            """
            SELECT r.*,
                (SELECT COUNT(*) FROM tool_calls t WHERE t.agent_run_id = r.id)
                AS tool_call_count
            FROM agent_runs r
            WHERE r.user_id = ?
            ORDER BY r.id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
    return [_run_row(row) or {} for row in rows]


def get_agent_run(user_id: int, run_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            """
            SELECT r.*,
                (SELECT COUNT(*) FROM tool_calls t WHERE t.agent_run_id = r.id)
                AS tool_call_count
            FROM agent_runs r
            WHERE r.id = ? AND r.user_id = ?
            """,
            (run_id, user_id),
        ).fetchone()
    return _run_row(row)


def list_tool_calls(user_id: int, run_id: int) -> list[dict[str, Any]] | None:
    if not get_agent_run(user_id, run_id):
        return None
    with connection() as db:
        rows = db.execute(
            """
            SELECT * FROM tool_calls
            WHERE agent_run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()
    return [_row_dict(row, ("tool_input_json",)) or {} for row in rows]


def upsert_favorite(user_id: int, data: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    with connection() as db:
        db.execute(
            """
            INSERT INTO favorite_jobs (
                user_id, job_id, job_name, department_name, region,
                exam_type, raw_job_json, note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, job_id) DO UPDATE SET
                job_name = excluded.job_name,
                department_name = excluded.department_name,
                region = excluded.region,
                exam_type = excluded.exam_type,
                raw_job_json = excluded.raw_job_json,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                data["job_id"],
                data.get("job_name") or "",
                data.get("department_name") or "",
                data.get("region") or "",
                data.get("exam_type") or "",
                json_dumps(data.get("raw_job_json") or {}),
                data.get("note") or "",
                now,
                now,
            ),
        )
        row = db.execute(
            """
            SELECT * FROM favorite_jobs
            WHERE user_id = ? AND job_id = ?
            """,
            (user_id, data["job_id"]),
        ).fetchone()
    return _row_dict(row, ("raw_job_json",)) or {}


def list_favorites(user_id: int) -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute(
            """
            SELECT * FROM favorite_jobs
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [_row_dict(row, ("raw_job_json",)) or {} for row in rows]


def delete_favorite(user_id: int, favorite_id: int) -> bool:
    with connection() as db:
        cursor = db.execute(
            "DELETE FROM favorite_jobs WHERE id = ? AND user_id = ?",
            (favorite_id, user_id),
        )
    return cursor.rowcount > 0


def create_report(user_id: int, data: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO analysis_reports (
                user_id, session_id, title, report_type, content, summary,
                related_jobs_json, citations_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                data.get("session_id"),
                data.get("title") or "分析报告",
                data.get("report_type") or "job_analysis",
                data.get("content") or "",
                data.get("summary") or "",
                json_dumps(data.get("related_jobs_json") or []),
                json_dumps(data.get("citations_json") or []),
                now,
                now,
            ),
        )
        row = db.execute(
            "SELECT * FROM analysis_reports WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _report_row(row) or {}


def list_reports(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute(
            """
            SELECT * FROM analysis_reports
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
    return [_report_row(row) or {} for row in rows]


def get_report(user_id: int, report_id: int) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            """
            SELECT * FROM analysis_reports
            WHERE id = ? AND user_id = ?
            """,
            (report_id, user_id),
        ).fetchone()
    return _report_row(row)


def delete_report(user_id: int, report_id: int) -> bool:
    with connection() as db:
        cursor = db.execute(
            "DELETE FROM analysis_reports WHERE id = ? AND user_id = ?",
            (report_id, user_id),
        )
    return cursor.rowcount > 0


def _run_row(row) -> dict[str, Any] | None:
    return _row_dict(
        row,
        (
            "used_tools_json",
            "trace_json",
            "citations_json",
            "sources_json",
        ),
    )


def _report_row(row) -> dict[str, Any] | None:
    return _row_dict(row, ("related_jobs_json", "citations_json"))


def _bool_db(value: Any) -> int | None:
    if value is None:
        return None
    return int(bool(value))
