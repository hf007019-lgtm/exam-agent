"""Safely remove one bad structured import from the local SQLite database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import connection
from app.db.import_repository import IMPORT_TARGETS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按 source_file 或 import_task_id 清理一次错误导入，不删除数据库文件。"
    )
    parser.add_argument("--source-file", default="", help="例如：2025黑龙江省考上岸分数汇总.xlsx")
    parser.add_argument("--task-id", default="", help="例如：import_xxx")
    args = parser.parse_args()

    source_file = str(args.source_file or "").strip()
    task_id = str(args.task_id or "").strip()
    if not source_file and not task_id:
        parser.error("必须提供 --source-file 或 --task-id")

    result = cleanup_bad_import(source_file=source_file, task_id=task_id)
    print("清理完成")
    print(f"- source_file: {source_file or '(未指定)'}")
    print(f"- task_ids: {', '.join(result['task_ids']) or '(无匹配任务)'}")
    for table, count in result["deleted_rows"].items():
        print(f"- {table}: 删除 {count} 行")
    print(f"- import_warnings: 删除 {result['deleted_warnings']} 行")
    print(f"- import_tasks: 删除 {result['deleted_tasks']} 行")
    return 0


def cleanup_bad_import(*, source_file: str = "", task_id: str = "") -> dict[str, Any]:
    source_file = str(source_file or "").strip()
    task_id = str(task_id or "").strip()
    deleted_rows: dict[str, int] = {}

    with connection() as db:
        task_ids = _find_task_ids(db, source_file=source_file, task_id=task_id)
        for config in IMPORT_TARGETS.values():
            table = str(config["table"])
            deleted_rows[table] = _delete_table_rows(
                db,
                table=table,
                source_file=source_file,
                task_ids=task_ids,
            )

        deleted_warnings = _delete_task_scoped_rows(db, "import_warnings", task_ids)
        deleted_tasks = _delete_import_tasks(db, source_file=source_file, task_ids=task_ids)

    return {
        "task_ids": task_ids,
        "deleted_rows": deleted_rows,
        "deleted_warnings": deleted_warnings,
        "deleted_tasks": deleted_tasks,
    }


def _find_task_ids(db: Any, *, source_file: str, task_id: str) -> list[str]:
    task_ids: list[str] = []
    if task_id:
        row = db.execute(
            "SELECT task_id FROM import_tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row:
            task_ids.append(str(row["task_id"]))
    if source_file:
        rows = db.execute(
            "SELECT task_id FROM import_tasks WHERE file_name = ?",
            (source_file,),
        ).fetchall()
        task_ids.extend(str(row["task_id"]) for row in rows)
    return list(dict.fromkeys(task_ids))


def _delete_table_rows(
    db: Any,
    *,
    table: str,
    source_file: str,
    task_ids: list[str],
) -> int:
    deleted = 0
    if task_ids:
        placeholders = ", ".join("?" for _ in task_ids)
        cursor = db.execute(
            f"DELETE FROM {table} WHERE import_task_id IN ({placeholders})",
            task_ids,
        )
        deleted += int(cursor.rowcount or 0)
    if source_file:
        cursor = db.execute(
            f"DELETE FROM {table} WHERE source_file = ?",
            (source_file,),
        )
        deleted += int(cursor.rowcount or 0)
    return deleted


def _delete_task_scoped_rows(db: Any, table: str, task_ids: list[str]) -> int:
    if not task_ids:
        return 0
    placeholders = ", ".join("?" for _ in task_ids)
    cursor = db.execute(
        f"DELETE FROM {table} WHERE task_id IN ({placeholders})",
        task_ids,
    )
    return int(cursor.rowcount or 0)


def _delete_import_tasks(db: Any, *, source_file: str, task_ids: list[str]) -> int:
    deleted = 0
    if task_ids:
        placeholders = ", ".join("?" for _ in task_ids)
        cursor = db.execute(
            f"DELETE FROM import_tasks WHERE task_id IN ({placeholders})",
            task_ids,
        )
        deleted += int(cursor.rowcount or 0)
    if source_file:
        cursor = db.execute(
            "DELETE FROM import_tasks WHERE file_name = ?",
            (source_file,),
        )
        deleted += int(cursor.rowcount or 0)
    return deleted


if __name__ == "__main__":
    raise SystemExit(main())
