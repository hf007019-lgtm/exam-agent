"""Migrate bundled exam CSV seed files into the SQLite business tables."""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DATA_ROOT = PROJECT_ROOT / "app" / "data"
ROOT_DATA_ROOT = PROJECT_ROOT / "data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.import_repository import (  # noqa: E402
    IMPORT_TARGETS,
    confirm_import_task_data,
    save_import_task_snapshot,
)
from app.imports.cleaners import build_row_key, is_valid_year  # noqa: E402
from app.tools.province_registry import (  # noqa: E402
    detect_province_in_text,
    get_province_slug,
    normalize_province_slug,
)


FILENAME_PATTERNS = (
    re.compile(r"^jobs_(?P<province>[a-z_]+)_(?P<year>\d{4})(?:_.*)?\.csv$", re.I),
    re.compile(r"^job_scores_(?P<province>[a-z_]+)_(?P<year>\d{4})(?:_.*)?\.csv$", re.I),
)


def main() -> int:
    reports = migrate_builtin_csvs()
    migrated = sum(1 for item in reports if item["status"] == "migrated")
    skipped = len(reports) - migrated
    print(f"迁移完成：成功处理 {migrated} 个文件，跳过 {skipped} 个文件。")
    return 0


def migrate_builtin_csvs(
    data_roots: Iterable[Path] | None = None,
) -> list[dict[str, Any]]:
    """Migrate supported jobs/scores/legacy CSV files and return a report."""
    roots = list(data_roots or (APP_DATA_ROOT, ROOT_DATA_ROOT))
    reports: list[dict[str, Any]] = []
    for path in _iter_seed_files(roots):
        table_type = _table_type_for_path(path)
        if not table_type:
            reports.append(_skip_report(path, "文件名无法对应职位表或分数线表"))
            continue

        raw_rows = _read_csv(path)
        defaults = _infer_file_defaults(path, raw_rows)
        if not defaults["province"] or not is_valid_year(defaults["year"]):
            reports.append(
                _skip_report(path, "无法确定单一省份和合法年份，未写入数据库")
            )
            continue

        cleaned_rows, invalid_rows = _normalize_rows(
            path=path,
            table_type=table_type,
            raw_rows=raw_rows,
            defaults=defaults,
        )
        if not cleaned_rows:
            reports.append(_skip_report(path, "字段不完整或没有可迁移数据行"))
            continue

        task = _build_seed_task(
            path=path,
            table_type=table_type,
            rows=cleaned_rows,
            invalid_rows=invalid_rows,
            defaults=defaults,
        )
        save_import_task_snapshot(task)
        result = confirm_import_task_data(task)
        duplicate_rows = max(0, len(cleaned_rows) - int(result["inserted_rows"]))
        relative_path = _display_path(path)
        print(
            f"迁移 {relative_path} -> {result['target']}："
            f"插入 {result['inserted_rows']} 条，跳过重复 {duplicate_rows} 条"
        )
        if invalid_rows:
            print(f"  另跳过字段不完整数据行 {invalid_rows} 条")
        adopted_seed_rows = int(result.get("adopted_seed_rows") or 0)
        if adopted_seed_rows:
            print(f"  已将 {adopted_seed_rows} 条同键旧记录标记为内置种子数据")
        reports.append(
            {
                "path": relative_path,
                "status": "migrated",
                "table_type": table_type,
                "target": result["target"],
                "inserted_rows": int(result["inserted_rows"]),
                "duplicate_rows": duplicate_rows,
                "invalid_rows": invalid_rows,
                "adopted_seed_rows": adopted_seed_rows,
                "source_kind": "builtin_seed",
                "storage": "database",
            }
        )
    if not reports:
        print("未发现可迁移的内置 CSV，正常退出。")
    return reports


def _iter_seed_files(roots: Iterable[Path]) -> list[Path]:
    files: dict[str, Path] = {}
    for root in roots:
        for folder in ("jobs", "scores", "legacy"):
            source_dir = Path(root) / folder
            if not source_dir.exists():
                continue
            for path in sorted(source_dir.glob("*.csv")):
                files[str(path.resolve()).lower()] = path
    return sorted(files.values(), key=lambda path: str(path).lower())


def _table_type_for_path(path: Path) -> str:
    parent = path.parent.name.lower()
    name = path.name.lower()
    if parent == "jobs" or name.startswith("jobs"):
        return "job_table"
    if parent == "scores" or name.startswith(("scores", "job_scores")):
        return "score_line_table"
    return ""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def _infer_file_defaults(path: Path, rows: list[dict[str, str]]) -> dict[str, Any]:
    province = ""
    year: int | None = None
    for pattern in FILENAME_PATTERNS:
        match = pattern.match(path.name)
        if match:
            province = normalize_province_slug(match.group("province"))
            year = _optional_int(match.group("year"))
            break

    if not province:
        detected = detect_province_in_text(path.stem)
        province = str(detected.get("slug") or "")
    if year is None:
        year_match = re.search(r"(?<!\d)(19\d{2}|20\d{2}|2100)(?!\d)", path.stem)
        year = _optional_int(year_match.group(1)) if year_match else None

    row_provinces = {
        _province_slug(row.get("province") or row.get("region") or "")
        for row in rows
    } - {""}
    row_years = {
        parsed
        for parsed in (_optional_int(row.get("year")) for row in rows)
        if is_valid_year(parsed)
    }
    if not province and len(row_provinces) == 1:
        province = next(iter(row_provinces))
    if year is None and len(row_years) == 1:
        year = next(iter(row_years))

    exam_types = {
        _exam_type(row.get("target") or row.get("exam_type") or "")
        for row in rows
    } - {""}
    exam_type = next(iter(exam_types)) if len(exam_types) == 1 else "公务员"
    return {"province": province, "year": year, "exam_type": exam_type}


def _normalize_rows(
    *,
    path: Path,
    table_type: str,
    raw_rows: list[dict[str, str]],
    defaults: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid_rows = 0
    for raw in raw_rows:
        row = (
            _normalize_job_row(raw, path, defaults)
            if table_type == "job_table"
            else _normalize_score_row(raw, path, defaults)
        )
        if row is None:
            invalid_rows += 1
            continue
        rows.append(row)
    _assign_seed_row_keys(table_type, rows)
    return rows, invalid_rows


def _assign_seed_row_keys(table_type: str, rows: list[dict[str, Any]]) -> None:
    """Keep distinct seed rows when a source reuses short position codes."""
    fingerprints_by_base: dict[str, dict[str, str]] = {}
    for row in rows:
        base_key = build_row_key(table_type, row)
        fingerprint = _row_fingerprint(table_type, row)
        fingerprints = fingerprints_by_base.setdefault(base_key, {})
        if fingerprint in fingerprints:
            row["_row_key_override"] = fingerprints[fingerprint]
            continue
        if not fingerprints:
            extended_key = base_key
        else:
            digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
            extended_key = f"{base_key}|seed|{digest}"
        fingerprints[fingerprint] = extended_key
        row["_row_key_override"] = extended_key


def _row_fingerprint(table_type: str, row: dict[str, Any]) -> str:
    fields = (
        [
            "province",
            "year",
            "region",
            "unit_name",
            "department_name",
            "job_name",
            "job_code",
            "recruit_count",
            "major_requirement",
        ]
        if table_type == "job_table"
        else [
            "province",
            "year",
            "region",
            "section_title",
            "unit_name",
            "job_name",
            "job_code",
            "interview_count",
            "min_score",
            "max_score",
        ]
    )
    return "\x1f".join(str(row.get(field) or "").strip() for field in fields)


def _normalize_job_row(
    raw: dict[str, str],
    path: Path,
    defaults: dict[str, Any],
) -> dict[str, Any] | None:
    job_code = _position_code(raw.get("position_code") or raw.get("job_code") or raw.get("job_id"))
    unit_name = _text(raw.get("unit") or raw.get("unit_name") or raw.get("department"))
    job_name = _text(raw.get("position_name") or raw.get("job_name") or raw.get("position"))
    if not job_code or not (unit_name or job_name):
        return None
    return {
        "year": defaults["year"],
        "province": defaults["province"],
        "region": _text(raw.get("city") or raw.get("district") or raw.get("region")),
        "exam_type": defaults["exam_type"],
        "unit_name": unit_name,
        "department_name": _text(raw.get("department")),
        "job_name": job_name,
        "job_code": job_code,
        "recruit_count": _optional_int(raw.get("recruit_count") or raw.get("headcount")),
        "major_requirement": _text(raw.get("major_required") or raw.get("major_requirement")),
        "degree_requirement": _text(raw.get("degree") or raw.get("degree_requirement")),
        "education_requirement": _text(raw.get("education") or raw.get("education_required")),
        "political_requirement": _text(raw.get("political_requirement")),
        "identity_requirement": _text(raw.get("identity_required") or raw.get("identity_requirement")),
        "grassroots_requirement": _text(raw.get("grassroots_requirement")),
        "remark": _text(raw.get("remark") or raw.get("notes")),
        "source_file": path.name,
        "source_sheet": "",
    }


def _normalize_score_row(
    raw: dict[str, str],
    path: Path,
    defaults: dict[str, Any],
) -> dict[str, Any] | None:
    min_score = _optional_float(raw.get("min_interview_score") or raw.get("min_score"))
    job_code = _position_code(raw.get("position_code") or raw.get("job_code") or raw.get("score_id"))
    unit_name = _text(raw.get("unit") or raw.get("unit_name") or raw.get("department"))
    job_name = _text(raw.get("position_name") or raw.get("job_name") or raw.get("position_type"))
    if min_score is None or not (job_code or unit_name or job_name):
        return None
    return {
        "year": defaults["year"],
        "province": defaults["province"],
        "region": _text(raw.get("city") or raw.get("region")),
        "exam_type": defaults["exam_type"],
        "section_title": _text(raw.get("department")),
        "unit_name": unit_name,
        "job_name": job_name,
        "job_code": job_code,
        "recruit_count": _optional_int(raw.get("recruit_count")),
        "interview_count": _optional_int(raw.get("interview_count")),
        "major_category": _text(raw.get("major_category") or raw.get("position_type")),
        "min_score": min_score,
        "max_score": _optional_float(raw.get("max_interview_score") or raw.get("max_score")),
        "avg_score": _optional_float(raw.get("avg_interview_score") or raw.get("avg_score")),
        "source_file": path.name,
        "source_sheet": "",
    }


def _build_seed_task(
    *,
    path: Path,
    table_type: str,
    rows: list[dict[str, Any]],
    invalid_rows: int,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    digest = hashlib.sha1(_display_path(path).encode("utf-8")).hexdigest()[:12]
    config = IMPORT_TARGETS[table_type]
    return {
        "task_id": f"builtin_seed_{table_type}_{digest}",
        "file_name": path.name,
        "detected_type": table_type,
        "detected_type_label": str(config["label"]),
        "confidence": 1.0,
        "province": defaults["province"],
        "exam_type": defaults["exam_type"],
        "year": defaults["year"],
        "total_rows": len(rows) + invalid_rows,
        "valid_rows": len(rows),
        "warning_rows": invalid_rows,
        "preview_rows": rows[:20],
        "field_mapping": {},
        "warnings": [],
        "warning_summary": [],
        "import_report": {
            "source": "builtin_csv_seed",
            "source_file": path.name,
            "invalid_rows": invalid_rows,
        },
        "status": "PREVIEW_READY",
        "target": str(config["table"]),
        "inserted_rows": 0,
        "skipped_rows": 0,
        "source_kind": "builtin_seed",
        "storage": "database",
        "valid_cleaned_rows": rows,
    }


def _skip_report(path: Path, reason: str) -> dict[str, Any]:
    display_path = _display_path(path)
    print(f"跳过 {display_path}：{reason}")
    return {"path": display_path, "status": "skipped", "reason": reason}


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _province_slug(value: Any) -> str:
    text = _text(value)
    return get_province_slug(text) or str(detect_province_in_text(text).get("slug") or "")


def _exam_type(value: Any) -> str:
    text = _text(value)
    if "事业" in text:
        return "事业单位"
    if any(keyword in text for keyword in ("公务员", "省考", "国考")):
        return "公务员"
    return ""


def _position_code(value: Any) -> str:
    text = _text(value)
    groups = re.findall(r"\d+", text)
    if not groups:
        return text
    return max(enumerate(groups), key=lambda item: (len(item[1]), item[0]))[1]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_int(value: Any) -> int | None:
    try:
        text = _text(value)
        return int(float(text)) if text else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        text = _text(value)
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
