"""Migrate legacy data/cleaned JSON files into the SQLite structured tables."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.import_repository import IMPORT_TARGETS, confirm_import_task_data, save_import_task_snapshot


CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"
FILE_TYPE_MAP = {
    "exam_jobs.json": "job_table",
    "exam_score_lines.json": "score_line_table",
    "exam_candidate_scores.json": "candidate_score_table",
    "exam_signup_stats.json": "signup_table",
    "exam_major_catalog.json": "major_catalog",
}


def main() -> int:
    if not CLEANED_DIR.exists():
        print("data/cleaned 不存在，无需迁移。")
        return 0

    migrated_any = False
    for file_name, table_type in FILE_TYPE_MAP.items():
        path = CLEANED_DIR / file_name
        if not path.exists():
            continue
        migrated_any = True
        rows = _load_rows(path)
        print(f"发现 {path.relative_to(PROJECT_ROOT).as_posix()}")
        if not rows:
            print(f"写入 {IMPORT_TARGETS[table_type]['table']}：0 条，跳过重复 0 条")
            continue
        task = _build_migration_task(path, table_type, rows)
        save_import_task_snapshot(task)
        result = confirm_import_task_data(task)
        skipped_rows = int(result.get("skipped_rows") or 0)
        print(
            f"写入 {result['target']}：{result['inserted_rows']} 条，"
            f"跳过重复 {skipped_rows} 条"
        )

    if not migrated_any:
        print("data/cleaned 下没有可迁移 JSON，正常退出。")
    print("迁移完成")
    return 0


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = (
            payload.get("rows")
            or payload.get("items")
            or payload.get("data")
            or payload.get("valid_cleaned_rows")
            or []
        )
    else:
        candidates = []
    return [row for row in candidates if isinstance(row, dict)]


def _build_migration_task(
    path: Path,
    table_type: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    config = IMPORT_TARGETS[table_type]
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    task_id = f"migrate_cleaned_{table_type}_{digest}"
    cleaned_rows = [
        {
            **row,
            "source_file": row.get("source_file") or path.name,
        }
        for row in rows
    ]
    return {
        "task_id": task_id,
        "file_name": path.name,
        "detected_type": table_type,
        "detected_type_label": str(config["label"]),
        "confidence": 1.0,
        "province": "",
        "exam_type": "",
        "year": None,
        "total_rows": len(cleaned_rows),
        "valid_rows": len(cleaned_rows),
        "warning_rows": 0,
        "preview_rows": cleaned_rows[:20],
        "field_mapping": {},
        "warnings": [],
        "warning_summary": [],
        "import_report": {
            "source": "legacy_cleaned_json",
            "source_file": path.name,
        },
        "status": "PREVIEW_READY",
        "source_kind": "migrated",
        "storage": "database",
        "target": str(config["table"]),
        "inserted_rows": 0,
        "skipped_rows": 0,
        "valid_cleaned_rows": cleaned_rows,
    }


if __name__ == "__main__":
    raise SystemExit(main())
