"""Disk-backed preview tasks plus database-backed formal import storage."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.db.import_repository import (
    IMPORT_TARGETS,
    confirm_import_task_data,
    confirm_multi_output_task_data,
    save_import_task_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMPORT_TASK_DIR = PROJECT_ROOT / "data" / "imports"
CLEANED_DATA_DIR = PROJECT_ROOT / "data" / "cleaned"

TARGETS = {
    table_type: (str(config["table"]), f"{config['table']}.json")
    for table_type, config in IMPORT_TARGETS.items()
}


def ensure_import_dirs() -> None:
    IMPORT_TASK_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(task_id: str, file_name: str, content: bytes) -> Path:
    ensure_import_dirs()
    suffix = Path(file_name).suffix.lower()
    upload_path = IMPORT_TASK_DIR / f"{task_id}_{safe_file_name(Path(file_name).stem)}{suffix}"
    upload_path.write_bytes(content)
    return upload_path


def save_task(task: dict[str, Any]) -> None:
    ensure_import_dirs()
    task_path(task["task_id"]).write_text(
        json.dumps(task, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    save_import_task_snapshot(task)


def load_task(task_id: str) -> dict[str, Any]:
    path = task_path(task_id)
    if not path.exists():
        raise FileNotFoundError("导入任务不存在")
    return json.loads(path.read_text(encoding="utf-8"))


def confirm_task(task_id: str) -> dict[str, Any]:
    task = load_task(task_id)
    table_type = str(task.get("detected_type") or "")
    enabled_outputs = [
        output
        for output in (task.get("outputs") or [])
        if isinstance(output, dict) and output.get("enabled", True)
    ]
    output_types_supported = enabled_outputs and all(
        str(output.get("dataset_type") or "") in TARGETS
        for output in enabled_outputs
    )
    if table_type not in TARGETS and not output_types_supported:
        result = _failed_confirmation_result(
            task,
            message="入库失败：当前文件类型不支持入库，请确认表类型和字段映射。",
        )
        _save_confirmation_result(task, result)
        return result

    previous_inserted = int(task.get("inserted_count") or task.get("inserted_rows") or 0)
    if task.get("status") in {"IMPORTED", "PARTIAL_IMPORTED"} and previous_inserted > 0:
        return _stored_confirmation_result(task)

    blocking_reasons = [
        str(reason).strip()
        for reason in task.get("blocking_reasons") or []
        if str(reason).strip()
    ]
    if task.get("status") != "PREVIEW_READY":
        blocking_reasons.append("清洗预览尚未通过类型和字段校验")
    if blocking_reasons:
        result = _failed_confirmation_result(
            task,
            message=f"入库已拦截：{'；'.join(blocking_reasons)}",
        )
        _save_confirmation_result(task, result)
        return result

    valid_rows = [row for row in (task.get("valid_cleaned_rows") or []) if isinstance(row, dict)]
    if enabled_outputs:
        valid_rows = [
            row
            for output in enabled_outputs
            for row in (output.get("valid_cleaned_rows") or [])
            if isinstance(row, dict)
        ]
    if not valid_rows:
        result = _failed_confirmation_result(
            task,
            message="识别完成，但没有有效记录，不能入库。",
        )
        _save_confirmation_result(task, result)
        return result

    save_import_task_snapshot(task)
    result = (
        confirm_multi_output_task_data(task)
        if enabled_outputs
        else confirm_import_task_data(task)
    )
    _save_confirmation_result(task, result)
    return result


def task_path(task_id: str) -> Path:
    if not re.fullmatch(r"import_[a-zA-Z0-9_]+", task_id):
        raise ValueError("导入任务 ID 不合法")
    return IMPORT_TASK_DIR / f"{task_id}.json"


def safe_file_name(value: str) -> str:
    clean = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", value).strip("._")
    return clean[:80] or "upload"


def _failed_confirmation_result(
    task: dict[str, Any],
    *,
    message: str,
) -> dict[str, Any]:
    valid_rows = int(task.get("valid_rows") or 0)
    warning_rows = int(task.get("warning_rows") or 0)
    return {
        "task_id": str(task.get("task_id") or ""),
        "status": "IMPORT_FAILED",
        "target": "",
        "inserted_count": 0,
        "updated_count": 0,
        "skipped_count": warning_rows + valid_rows,
        "warning_count": len(task.get("warnings") or []),
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "dataset_id": "",
        "inserted_rows": 0,
        "skipped_rows": warning_rows + valid_rows,
        "storage": "database",
        "message": message,
    }


def _stored_confirmation_result(task: dict[str, Any]) -> dict[str, Any]:
    inserted_count = int(task.get("inserted_count") or task.get("inserted_rows") or 0)
    skipped_count = int(task.get("skipped_count") or task.get("skipped_rows") or 0)
    return {
        "task_id": str(task.get("task_id") or ""),
        "status": str(task.get("status") or "IMPORTED"),
        "target": str(task.get("target") or ""),
        "inserted_count": inserted_count,
        "updated_count": int(task.get("updated_count") or 0),
        "skipped_count": skipped_count,
        "warning_count": int(task.get("warning_count") or len(task.get("warnings") or [])),
        "valid_rows": int(task.get("valid_rows") or 0),
        "warning_rows": int(task.get("warning_rows") or 0),
        "dataset_id": str(task.get("dataset_id") or ""),
        "inserted_rows": inserted_count,
        "skipped_rows": skipped_count,
        "storage": "database",
        "message": str(task.get("message") or "该导入任务已经完成，无需重复入库。"),
        "output_results": list(task.get("output_results") or []),
    }


def _save_confirmation_result(task: dict[str, Any], result: dict[str, Any]) -> None:
    task.update(
        {
            "status": result["status"],
            "target": result.get("target") or "",
            "inserted_count": int(result.get("inserted_count") or 0),
            "updated_count": int(result.get("updated_count") or 0),
            "skipped_count": int(result.get("skipped_count") or 0),
            "warning_count": int(result.get("warning_count") or 0),
            "dataset_id": str(result.get("dataset_id") or ""),
            "inserted_rows": int(result.get("inserted_count") or 0),
            "skipped_rows": int(result.get("skipped_count") or 0),
            "storage": "database",
            "message": str(result.get("message") or ""),
            "output_results": list(result.get("output_results") or []),
        }
    )
    save_task(task)
