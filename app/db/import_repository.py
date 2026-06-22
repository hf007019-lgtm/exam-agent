"""SQLite repository for structured import tasks and cleaned exam data."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.db.database import connection, json_dumps, json_loads, utc_now
from app.imports.cleaners import build_row_key, is_valid_year, parse_year
from app.imports.import_type_registry import get_import_type
from app.tools.province_registry import (
    DEFAULT_DATA_YEAR,
    detect_province_in_text,
    get_province_name,
    get_province_slug,
    normalize_province_slug,
)


def _registered_target(type_key: str) -> dict[str, Any]:
    config = get_import_type(type_key)
    return {
        "table": str(config.get("target_table") or ""),
        "kind": str(config.get("kind") or "other"),
        "label": str(config.get("label") or type_key),
        "catalog_group": str(config.get("catalog_group") or "other"),
        "score_like": bool(config.get("score_like")),
    }


IMPORT_TARGETS = {
    "job_table": {
        **_registered_target("job_table"),
        "fields": [
            "year",
            "province",
            "region",
            "exam_type",
            "unit_name",
            "department_name",
            "job_name",
            "job_code",
            "recruit_count",
            "major_requirement",
            "degree_requirement",
            "education_requirement",
            "political_requirement",
            "identity_requirement",
            "grassroots_requirement",
            "qualification_requirement",
            "job_description",
            "contact_phone",
            "work_address",
            "remark",
            "source_file",
            "source_sheet",
            "extra_fields_json",
        ],
    },
    "score_line_table": {
        **_registered_target("score_line_table"),
        "fields": [
            "year",
            "province",
            "region",
            "exam_type",
            "section_title",
            "unit_name",
            "job_name",
            "job_code",
            "recruit_count",
            "interview_count",
            "major_category",
            "min_score",
            "max_score",
            "avg_score",
            "source_file",
            "source_sheet",
            "extra_fields_json",
        ],
    },
    "candidate_score_table": {
        **_registered_target("candidate_score_table"),
        "fields": [
            "year",
            "province",
            "region",
            "exam_type",
            "data_granularity",
            "candidate_no",
            "candidate_name",
            "unit_code",
            "unit_name",
            "job_code",
            "job_name",
            "recruit_count",
            "xingce_score",
            "shenlun_score",
            "professional_score",
            "written_score",
            "interview_score",
            "total_score",
            "rank",
            "status",
            "group_name",
            "remark",
            "source_sheet",
            "source_file",
            "extra_fields_json",
        ],
    },
    "review_candidate_list": {
        **_registered_target("review_candidate_list"),
        "fields": [
            "province",
            "year",
            "exam_type",
            "job_code",
            "job_name",
            "unit_name",
            "recruit_count",
            "candidate_no",
            "candidate_name",
            "subject1_name",
            "subject1_score",
            "subject2_name",
            "subject2_score",
            "subject3_name",
            "subject3_score",
            "bonus_score",
            "written_score",
            "xingce_score",
            "shenlun_score",
            "professional_score",
            "total_score",
            "rank",
            "review_status",
            "remark",
            "source_file",
            "source_sheet",
            "raw_row_json",
            "extra_fields_json",
        ],
    },
    "signup_table": {
        **_registered_target("signup_table"),
        "fields": [
            "year",
            "province",
            "region",
            "exam_type",
            "unit_name",
            "job_name",
            "job_code",
            "recruit_count",
            "signup_count",
            "approved_count",
            "paid_count",
            "competition_ratio",
            "source_file",
            "source_sheet",
            "extra_fields_json",
        ],
    },
    "major_catalog": {
        **_registered_target("major_catalog"),
        "fields": [
            "year",
            "province",
            "major_name",
            "major_code",
            "major_category",
            "degree_level",
            "source_file",
            "source_sheet",
            "extra_fields_json",
        ],
    },
}


DATASET_ROW_VIEWS: dict[str, dict[str, Any]] = {
    "job_table": {
        "columns": [
            ("job_code", "职位代码", "job_code"),
            ("job_name", "岗位名称", "job_name"),
            ("unit_name", "招录单位", "unit_name"),
            ("region", "地区", "region"),
            ("recruit_count", "招录人数", "recruit_count"),
            ("major_requirement", "专业要求", "major_requirement"),
            ("education_requirement", "学历要求", "education_requirement"),
            ("degree_requirement", "学位要求", "degree_requirement"),
            ("qualification_requirement", "资格条件", "qualification_requirement"),
            ("job_description", "职位简介", "job_description"),
            ("contact_phone", "咨询电话", "contact_phone"),
            ("work_address", "单位地址", "work_address"),
            ("remark", "备注", "remark"),
        ],
        "search_fields": ["job_code", "job_name", "unit_name", "department_name", "region"],
    },
    "score_line_table": {
        "columns": [
            ("job_code", "职位代码", "job_code"),
            ("job_name", "岗位名称", "job_name"),
            ("unit_name", "招录单位", "unit_name"),
            ("min_score", "最低进面分", "min_score"),
            ("max_score", "最高分", "max_score"),
            ("avg_score", "平均分", "avg_score"),
            ("recruit_count", "招录人数", "recruit_count"),
            ("interview_count", "进面人数", "interview_count"),
        ],
        "search_fields": ["job_code", "job_name", "unit_name", "section_title", "region"],
    },
    "candidate_score_table": {
        "columns": [
            ("job_code", "职位代码", "job_code"),
            ("job_name", "岗位名称", "job_name"),
            ("unit_name", "招录单位", "unit_name"),
            ("written_score", "笔试成绩", "written_score"),
            ("interview_score", "面试成绩", "interview_score"),
            ("total_score", "总成绩", "total_score"),
            ("rank", "排名", "rank"),
            ("status", "状态", "status"),
            ("source_sheet", "来源 Sheet", "source_sheet"),
        ],
        "search_fields": ["job_code", "job_name", "unit_name"],
    },
    "review_candidate_list": {
        "columns": [
            ("job_code", "职位代码", "job_code"),
            ("job_name", "岗位名称", "job_name"),
            ("unit_name", "招录单位", "unit_name"),
            ("recruit_count", "招录人数", "recruit_count"),
            ("xingce_score", "行测成绩", "xingce_score"),
            ("shenlun_score", "申论成绩", "shenlun_score"),
            ("professional_score", "专业成绩", "professional_score"),
            ("bonus_score", "加分", "bonus_score"),
            ("written_score", "笔试成绩", "written_score"),
            ("rank", "排名", "rank"),
            ("review_status", "资格标志", "review_status"),
            ("source_sheet", "来源 Sheet", "source_sheet"),
        ],
        "detail_fields": [
            ("科目1名称", "subject1_name"),
            ("科目1成绩", "subject1_score"),
            ("科目2名称", "subject2_name"),
            ("科目2成绩", "subject2_score"),
            ("科目3名称", "subject3_name"),
            ("科目3成绩", "subject3_score"),
        ],
        "search_fields": ["job_code", "job_name", "unit_name"],
    },
    "signup_table": {
        "columns": [
            ("job_code", "职位代码", "job_code"),
            ("job_name", "岗位名称", "job_name"),
            ("unit_name", "招录单位", "unit_name"),
            ("recruit_count", "招录人数", "recruit_count"),
            ("apply_count", "报名人数", "signup_count"),
            ("approved_count", "审核通过人数", "approved_count"),
            ("paid_count", "缴费人数", "paid_count"),
            ("competition_ratio", "竞争比", "competition_ratio"),
        ],
        "search_fields": ["job_code", "job_name", "unit_name", "region"],
    },
    "major_catalog": {
        "columns": [
            ("major_code", "专业代码", "major_code"),
            ("major_name", "专业名称", "major_name"),
            ("major_category", "专业类别", "major_category"),
            ("degree_level", "学历层次", "degree_level"),
        ],
        "search_fields": ["major_code", "major_name", "major_category", "degree_level"],
    },
}

SENSITIVE_DATASET_DISPLAY_FIELDS = {
    "candidate_name",
    "candidate_no",
    "admission_ticket",
    "id_card",
    "identity_card",
    "personal_phone",
    "mobile",
    "phone",
    "raw_row_json",
    "extra_fields_json",
}
ALLOWED_DATASET_PHONE_FIELDS = {"contact_phone", "consult_phone", "unit_phone"}
SENSITIVE_DATASET_FIELD_MARKERS = (
    "姓名",
    "准考证",
    "身份证",
    "个人电话",
    "手机号",
    "联系电话",
    "联系方式",
    "原始行",
)

PUBLIC_JOB_EXTRA_FIELD_ALIASES = {
    "agency_level": ["机构层级", "机构级别", "单位层级"],
    "is_public_service": ["是否参公", "是否参照公务员法管理", "参照公务员法管理"],
    "is_law_enforcement": ["是否行政执法类", "是否行政执法", "行政执法类"],
    "qualification_requirement": ["资格条件", "报考资格条件", "资格要求"],
    "job_description": ["职位简介", "岗位简介", "职位描述", "岗位描述"],
    "contact_phone": ["咨询电话", "单位咨询电话"],
    "work_address": ["单位地址", "工作地址", "办公地址"],
    "remark": ["备注", "其他要求", "其他条件"],
}


def save_import_task_snapshot(task: dict[str, Any]) -> None:
    """Persist preview metadata and warnings to the database audit tables."""
    task_id = str(task.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("导入任务 ID 不能为空")

    now = utc_now()
    defaults = _task_default_fields(task)
    source_kind = _normalize_source_kind(task.get("source_kind"))
    storage = "database"
    if parse_year(defaults.get("year")) is None:
        defaults["year"] = _infer_year_from_text(task.get("file_name")) or DEFAULT_DATA_YEAR
    with connection() as db:
        db.execute(
            """
            INSERT INTO import_tasks (
                task_id, file_name, detected_type, detected_type_label,
                confidence, province, exam_type, year, total_rows,
                valid_rows, warning_rows, status, target, inserted_rows,
                skipped_rows, source_kind, storage,
                field_mapping_json, preview_rows_json,
                import_report_json, created_at, updated_at, confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                file_name = excluded.file_name,
                detected_type = excluded.detected_type,
                detected_type_label = excluded.detected_type_label,
                confidence = excluded.confidence,
                province = excluded.province,
                exam_type = excluded.exam_type,
                year = excluded.year,
                total_rows = excluded.total_rows,
                valid_rows = excluded.valid_rows,
                warning_rows = excluded.warning_rows,
                status = excluded.status,
                target = excluded.target,
                inserted_rows = excluded.inserted_rows,
                skipped_rows = excluded.skipped_rows,
                source_kind = excluded.source_kind,
                storage = excluded.storage,
                field_mapping_json = excluded.field_mapping_json,
                preview_rows_json = excluded.preview_rows_json,
                import_report_json = excluded.import_report_json,
                updated_at = excluded.updated_at,
                confirmed_at = COALESCE(import_tasks.confirmed_at, excluded.confirmed_at)
            """,
            (
                task_id,
                str(task.get("file_name") or ""),
                str(task.get("detected_type") or ""),
                str(task.get("detected_type_label") or ""),
                _float_or_zero(task.get("confidence")),
                defaults["province"],
                defaults["exam_type"],
                defaults["year"],
                _int_or_zero(task.get("total_rows")),
                _int_or_zero(task.get("valid_rows")),
                _int_or_zero(task.get("warning_rows")),
                str(task.get("status") or "PREVIEW_READY"),
                str(task.get("target") or ""),
                _int_or_zero(task.get("inserted_rows")),
                _int_or_zero(task.get("skipped_rows")),
                source_kind,
                storage,
                json_dumps(task.get("field_mapping") or {}),
                json_dumps(task.get("preview_rows") or []),
                json_dumps(task.get("import_report") or {}),
                now,
                now,
                task.get("confirmed_at"),
            ),
        )
        db.execute("DELETE FROM import_warnings WHERE task_id = ?", (task_id,))
        warning_rows = [
            (
                task_id,
                _optional_int(warning.get("row_index")),
                str(warning.get("level") or "warning"),
                str(warning.get("message") or ""),
                json_dumps(warning.get("raw_value")),
                str(warning.get("field") or ""),
                str(warning.get("source_column") or ""),
                now,
            )
            for warning in (task.get("warnings") or [])
            if isinstance(warning, dict)
        ]
        if warning_rows:
            db.executemany(
                """
                INSERT INTO import_warnings (
                    task_id, row_index, level, message, raw_value_json,
                    field, source_column, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                warning_rows,
            )


def confirm_import_task_data(task: dict[str, Any]) -> dict[str, Any]:
    """Write valid cleaned rows into the formal structured-data tables."""
    task_id = str(task.get("task_id") or "").strip()
    table_type = str(task.get("detected_type") or "").strip()
    config = IMPORT_TARGETS.get(table_type)
    if not task_id:
        raise ValueError("导入任务 ID 不能为空")
    if not config:
        raise ValueError("当前任务未识别为可入库的数据类型")

    target_table = str(config["table"])
    fields = list(config["fields"])
    valid_rows = [
        row for row in (task.get("valid_cleaned_rows") or [])
        if isinstance(row, dict)
    ]
    valid_row_count = len(valid_rows)
    warning_row_count = _int_or_zero(task.get("warning_rows"))
    warning_count = len([
        warning for warning in (task.get("warnings") or [])
        if isinstance(warning, dict)
    ])
    if valid_row_count <= 0:
        now = utc_now()
        with connection() as db:
            db.execute(
                """
                UPDATE import_tasks
                SET status = 'IMPORT_FAILED',
                    target = '',
                    inserted_rows = 0,
                    skipped_rows = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (warning_row_count, now, task_id),
            )
        return {
            "task_id": task_id,
            "status": "IMPORT_FAILED",
            "target": "",
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_count": warning_row_count,
            "warning_count": warning_count,
            "valid_rows": 0,
            "warning_rows": warning_row_count,
            "dataset_id": "",
            "inserted_rows": 0,
            "skipped_rows": warning_row_count,
            "storage": "database",
            "message": "识别完成，但没有有效记录，不能入库。",
        }
    defaults = _task_default_fields(task)
    source_kind = _normalize_source_kind(task.get("source_kind"))
    storage = "database"
    inserted_rows = 0
    duplicate_rows = 0
    adopted_seed_rows = 0
    corrected_year_rows = 0
    now = utc_now()

    columns = [
        "import_task_id",
        "row_key",
        "source_kind",
        "storage",
        *fields,
        "created_at",
        "updated_at",
    ]
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    sql = f"INSERT OR IGNORE INTO {target_table} ({column_sql}) VALUES ({placeholders})"

    with connection() as db:
        for row in valid_rows:
            protected_row, year_was_corrected = _protect_import_row(
                table_type=table_type,
                row=row,
                task=task,
                defaults=defaults,
            )
            if year_was_corrected:
                corrected_year_rows += 1
            row_key = str(protected_row.get("_row_key_override") or "").strip()
            if not row_key:
                row_key = build_row_key(table_type, protected_row)
            values = [
                task_id,
                row_key,
                source_kind,
                storage,
                *[_db_value(field, protected_row.get(field)) for field in fields],
                now,
                now,
            ]
            cursor = db.execute(sql, values)
            if cursor.rowcount:
                inserted_rows += 1
            else:
                duplicate_rows += 1
                if source_kind == "builtin_seed":
                    adopted = db.execute(
                        f"""
                        UPDATE {target_table}
                        SET import_task_id = ?,
                            source_kind = 'builtin_seed',
                            storage = 'database',
                            source_file = ?,
                            updated_at = ?
                        WHERE row_key = ?
                          AND source_kind <> 'builtin_seed'
                        """,
                        (
                            task_id,
                            str(protected_row.get("source_file") or task.get("file_name") or ""),
                            now,
                            row_key,
                        ),
                    )
                    adopted_seed_rows += int(adopted.rowcount or 0)

        if corrected_year_rows:
            _append_task_warning_once(
                task,
                field="year",
                message=f"检测到非法年份字段，已使用导入任务年份 {defaults['year']}",
                raw_value=f"{corrected_year_rows} rows",
            )

        skipped_rows = warning_row_count + duplicate_rows
        updated_rows = adopted_seed_rows
        dataset_id = ""
        if inserted_rows > 0:
            dataset_exam_type = "exam_type" if table_type != "major_catalog" else "'' AS exam_type"
            dataset_row = db.execute(
                f"""
                SELECT province, year, {dataset_exam_type}, source_file, source_kind
                FROM {target_table}
                WHERE import_task_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (task_id,),
            ).fetchone()
            if dataset_row and is_valid_year(dataset_row["year"]):
                dataset_id = _build_dataset_id(
                    data_type=table_type,
                    province=str(dataset_row["province"] or ""),
                    year=int(dataset_row["year"]),
                    exam_type=str(dataset_row["exam_type"] or ""),
                    source_file=str(dataset_row["source_file"] or ""),
                    import_task_id=task_id,
                    source_kind=_normalize_source_kind(dataset_row["source_kind"]),
                )

        if inserted_rows <= 0:
            final_status = "IMPORT_FAILED"
            message = "入库失败：有效记录未写入数据库，请查看错误原因。"
        elif skipped_rows > 0:
            final_status = "PARTIAL_IMPORTED"
            message = f"部分入库成功：成功写入 {inserted_rows} 条，跳过 {skipped_rows} 条。"
        else:
            final_status = "IMPORTED"
            message = f"入库完成：成功写入 {inserted_rows} 条，跳过 0 条。"
        db.execute(
            """
            UPDATE import_tasks
            SET status = ?,
                target = ?,
                inserted_rows = ?,
                skipped_rows = ?,
                updated_at = ?,
                confirmed_at = COALESCE(confirmed_at, ?)
            WHERE task_id = ?
            """,
            (final_status, target_table, inserted_rows, skipped_rows, now, now, task_id),
        )

    return {
        "task_id": task_id,
        "status": final_status,
        "target": target_table,
        "inserted_count": inserted_rows,
        "updated_count": updated_rows,
        "skipped_count": skipped_rows,
        "warning_count": warning_count,
        "valid_rows": valid_row_count,
        "warning_rows": warning_row_count,
        "dataset_id": dataset_id,
        "inserted_rows": inserted_rows,
        "skipped_rows": skipped_rows,
        "storage": storage,
        "source_kind": source_kind,
        "adopted_seed_rows": adopted_seed_rows,
        "message": message,
    }


def confirm_multi_output_task_data(task: dict[str, Any]) -> dict[str, Any]:
    """Confirm each enabled output of one mixed-Sheet task independently."""
    outputs = [
        output
        for output in (task.get("outputs") or [])
        if isinstance(output, dict) and output.get("enabled", True)
    ]
    if not outputs:
        raise ValueError("当前混合表没有启用任何输出数据集")

    output_results: list[dict[str, Any]] = []
    for output in outputs:
        dataset_type = str(output.get("dataset_type") or "").strip()
        if dataset_type not in IMPORT_TARGETS:
            raise ValueError(f"输出数据类型不受支持：{dataset_type or 'unknown'}")
        child_task = {
            **task,
            "detected_type": dataset_type,
            "detected_type_label": str(
                output.get("dataset_type_label")
                or IMPORT_TARGETS[dataset_type].get("label")
                or dataset_type
            ),
            "valid_cleaned_rows": list(output.get("valid_cleaned_rows") or []),
            "preview_rows": list(output.get("preview_rows") or []),
            "valid_rows": _int_or_zero(output.get("valid_rows")),
            "warning_rows": _int_or_zero(output.get("warning_rows")),
            "warnings": list(output.get("warnings") or []),
            "field_mapping": dict(output.get("field_mapping") or {}),
        }
        result = confirm_import_task_data(child_task)
        output_results.append(
            {
                **result,
                "dataset_type": dataset_type,
                "dataset_type_label": child_task["detected_type_label"],
            }
        )

    inserted_count = sum(_int_or_zero(item.get("inserted_count")) for item in output_results)
    updated_count = sum(_int_or_zero(item.get("updated_count")) for item in output_results)
    skipped_count = sum(_int_or_zero(item.get("skipped_count")) for item in output_results)
    warning_count = sum(_int_or_zero(item.get("warning_count")) for item in output_results)
    valid_rows = sum(_int_or_zero(item.get("valid_rows")) for item in output_results)
    warning_rows = sum(_int_or_zero(item.get("warning_rows")) for item in output_results)
    failed_outputs = [item for item in output_results if _int_or_zero(item.get("inserted_count")) <= 0]
    if inserted_count <= 0:
        status = "IMPORT_FAILED"
        message = "入库失败：所有输出数据集均未写入有效记录。"
    elif skipped_count > 0 or failed_outputs:
        status = "PARTIAL_IMPORTED"
        message = f"多输出入库部分完成：成功写入 {inserted_count} 条，跳过 {skipped_count} 条。"
    else:
        status = "IMPORTED"
        message = f"多输出入库完成：成功写入 {inserted_count} 条，跳过 0 条。"
    targets = list(dict.fromkeys(str(item.get("target") or "") for item in output_results if item.get("target")))
    dataset_ids = [str(item.get("dataset_id") or "") for item in output_results if item.get("dataset_id")]
    now = utc_now()
    with connection() as db:
        db.execute(
            """
            UPDATE import_tasks
            SET status = ?, target = ?, inserted_rows = ?, skipped_rows = ?,
                updated_at = ?, confirmed_at = COALESCE(confirmed_at, ?)
            WHERE task_id = ?
            """,
            (
                status,
                ",".join(targets),
                inserted_count,
                skipped_count,
                now,
                now,
                str(task.get("task_id") or ""),
            ),
        )
    return {
        "task_id": str(task.get("task_id") or ""),
        "status": status,
        "target": ",".join(targets),
        "inserted_count": inserted_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "warning_count": warning_count,
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "dataset_id": dataset_ids[0] if dataset_ids else "",
        "inserted_rows": inserted_count,
        "skipped_rows": skipped_count,
        "storage": "database",
        "message": message,
        "output_results": output_results,
    }


def delete_import_task_data(task_id: str) -> dict[str, Any]:
    """Delete database rows produced by a single import task."""
    clean_task_id = str(task_id or "").strip()
    if not clean_task_id:
        raise ValueError("导入任务 ID 不能为空")

    deleted_rows = 0
    with connection() as db:
        task = db.execute(
            "SELECT task_id, storage FROM import_tasks WHERE task_id = ?",
            (clean_task_id,),
        ).fetchone()
        if not task:
            return {}
        if str(task["storage"] or "") != "database":
            raise ValueError("仅允许删除数据库数据集")

        for config in IMPORT_TARGETS.values():
            table = str(config["table"])
            cursor = db.execute(
                f"DELETE FROM {table} WHERE import_task_id = ? AND storage = 'database'",
                (clean_task_id,),
            )
            deleted_rows += int(cursor.rowcount or 0)

        db.execute(
            "DELETE FROM import_warnings WHERE task_id = ?",
            (clean_task_id,),
        )
        db.execute(
            "DELETE FROM import_tasks WHERE task_id = ?",
            (clean_task_id,),
        )

    return {
        "task_id": clean_task_id,
        "status": "DELETED",
        "deleted_rows": deleted_rows,
        "message": "已删除该导入任务写入的数据库记录。",
    }


def delete_dataset_data(dataset_id: str) -> dict[str, Any]:
    """Delete one database dataset selected by its stable catalog id."""
    clean_dataset_id = str(dataset_id or "").strip()
    if not clean_dataset_id:
        raise ValueError("数据集 ID 不能为空")

    dataset = next(
        (
            item
            for item in list_imported_dataset_summaries()
            if item.get("dataset_id") == clean_dataset_id
        ),
        None,
    )
    if not dataset:
        return {}
    if dataset.get("storage") != "database":
        raise ValueError("仅允许删除数据库数据集")

    table_type = str(dataset.get("data_type") or "")
    config = IMPORT_TARGETS.get(table_type)
    if not config:
        raise ValueError("当前数据集类型不支持删除")
    table = str(config["table"])
    import_task_id = str(dataset.get("import_task_id") or "").strip()

    with connection() as db:
        if import_task_id:
            cursor = db.execute(
                f"DELETE FROM {table} "
                "WHERE import_task_id = ? AND storage = 'database'",
                (import_task_id,),
            )
        else:
            where = [
                "storage = 'database'",
                "province = ?",
                "year = ?",
                "source_file = ?",
            ]
            params: list[Any] = [
                dataset.get("province_slug") or "",
                dataset.get("year"),
                dataset.get("source_file") or "",
            ]
            if table_type != "major_catalog":
                where.append("exam_type = ?")
                params.append(dataset.get("exam_type") or "")
            cursor = db.execute(
                f"DELETE FROM {table} WHERE {' AND '.join(where)}",
                params,
            )
        deleted_rows = int(cursor.rowcount or 0)

        if import_task_id:
            remaining_rows = sum(
                int(
                    db.execute(
                        f"SELECT COUNT(*) FROM {target['table']} "
                        "WHERE import_task_id = ?",
                        (import_task_id,),
                    ).fetchone()[0]
                    or 0
                )
                for target in IMPORT_TARGETS.values()
            )
            if remaining_rows == 0:
                db.execute("DELETE FROM import_warnings WHERE task_id = ?", (import_task_id,))
                db.execute(
                    "DELETE FROM import_tasks WHERE task_id = ? AND storage = 'database'",
                    (import_task_id,),
                )

    return {
        "dataset_id": clean_dataset_id,
        "task_id": import_task_id,
        "status": "DELETED",
        "deleted_rows": deleted_rows,
        "message": "已删除该数据库数据集。",
    }


def get_import_task_status(task_id: str) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            """
            SELECT task_id, status, target, inserted_rows, skipped_rows
            FROM import_tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
    return dict(row) if row else None


def save_import_template(
    *,
    template_name: str,
    data_type: str,
    province: str = "",
    exam_type: str = "",
    source_keyword: str = "",
    sheet_keyword: str = "",
    header_signature: str = "",
    header_row: int | None = None,
    sub_header_row: int | None = None,
    data_start_row: int | None = None,
    field_mapping: dict[str, str] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    required_fields: list[str] | None = None,
    optional_fields: list[str] | None = None,
) -> dict[str, Any]:
    if data_type not in IMPORT_TARGETS:
        raise ValueError("模板数据类型不受支持")
    clean_name = str(template_name or "").strip()
    if not clean_name:
        raise ValueError("模板名称不能为空")
    now = utc_now()
    with connection() as db:
        cursor = db.execute(
            """
            INSERT INTO import_templates (
                template_name, data_type, province, exam_type, source_keyword,
                sheet_keyword, header_signature, header_row, sub_header_row,
                data_start_row, field_mapping_json, outputs_json,
                required_fields_json, optional_fields_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_name,
                data_type,
                str(province or "").strip(),
                str(exam_type or "").strip(),
                str(source_keyword or "").strip(),
                str(sheet_keyword or "").strip(),
                str(header_signature or "").strip(),
                header_row,
                sub_header_row,
                data_start_row,
                json_dumps(field_mapping or {}),
                json_dumps(outputs or []),
                json_dumps(required_fields or []),
                json_dumps(optional_fields or []),
                now,
                now,
            ),
        )
        row = db.execute(
            "SELECT * FROM import_templates WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _template_row(row) or {}


def list_import_templates(
    *,
    data_type: str = "",
    province: str = "",
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if data_type:
        where.append("data_type = ?")
        params.append(data_type)
    aliases = _province_aliases(province)
    if aliases:
        placeholders = ", ".join("?" for _ in aliases)
        where.append(f"province IN ({placeholders})")
        params.extend(aliases)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with connection() as db:
        rows = db.execute(
            f"""
            SELECT *
            FROM import_templates
            {where_sql}
            ORDER BY updated_at DESC, id DESC
            """,
            params,
        ).fetchall()
    return [_template_row(row) or {} for row in rows]


def find_matching_import_template(
    *,
    data_type: str,
    province: str = "",
    exam_type: str = "",
    file_name: str = "",
    sheet_names: list[str] | None = None,
    header_signatures: list[str] | None = None,
) -> dict[str, Any] | None:
    if data_type not in IMPORT_TARGETS:
        return None
    best: tuple[float, dict[str, Any]] | None = None
    for template in list_import_templates(data_type=data_type):
        score = _template_match_score(
            template=template,
            province=province,
            exam_type=exam_type,
            file_name=file_name,
            sheet_text=" ".join(sheet_names or []),
            header_signatures=header_signatures or [],
        )
        if score < 45:
            continue
        if best is None or score > best[0]:
            best = (score, template)
    return best[1] if best else None


def list_imported_dataset_summaries() -> list[dict[str, Any]]:
    """Return all database-backed dataset summaries for the data center."""
    datasets: list[dict[str, Any]] = []
    with connection() as db:
        for table_type, config in IMPORT_TARGETS.items():
            table = str(config["table"])
            select_exam_type = "exam_type" if table_type != "major_catalog" else "'' AS exam_type"
            select_granularity = (
                "data_granularity"
                if table_type == "candidate_score_table"
                else "'' AS data_granularity"
            )
            group_fields = [
                "import_task_id",
                "province",
                "year",
                "source_file",
                "source_kind",
                "storage",
            ]
            if table_type != "major_catalog":
                group_fields.append("exam_type")
            if table_type == "candidate_score_table":
                group_fields.append("data_granularity")
            group_sql = ", ".join(group_fields)
            rows = db.execute(
                f"""
                SELECT
                    import_task_id,
                    province,
                    year,
                    {select_exam_type},
                    {select_granularity},
                    source_file,
                    source_kind,
                    storage,
                    COUNT(*) AS record_count,
                    MAX(updated_at) AS updated_at
                FROM {table}
                WHERE year BETWEEN 1900 AND 2100
                GROUP BY {group_sql}
                HAVING COUNT(*) > 0
                ORDER BY COALESCE(year, 0) DESC, province, source_file
                """
            ).fetchall()
            for row in rows:
                if not is_valid_year(row["year"]):
                    continue
                province = _friendly_province(row["province"])
                year = int(row["year"])
                exam_type = str(row["exam_type"] or "").strip()
                source_kind = _normalize_source_kind(row["source_kind"])
                storage = str(row["storage"] or "database").strip() or "database"
                import_task_id = str(row["import_task_id"] or "").strip()
                source_file = str(row["source_file"] or "").strip()
                dataset_id = _build_dataset_id(
                    data_type=table_type,
                    province=str(row["province"] or ""),
                    year=year,
                    exam_type=exam_type,
                    source_file=source_file,
                    import_task_id=import_task_id,
                    source_kind=source_kind,
                )
                title = _friendly_imported_dataset_title(
                    province=province,
                    year=year,
                    exam_type=exam_type,
                    data_type=str(config["label"]),
                    source_kind=source_kind,
                )
                datasets.append(
                    {
                        "dataset_id": dataset_id,
                        "kind": config["kind"],
                        "catalog_group": config["catalog_group"],
                        "data_type": table_type,
                        "data_type_label": config["label"],
                        "score_like": bool(config["score_like"]),
                        "province": province,
                        "province_slug": str(row["province"] or ""),
                        "year": year,
                        "exam_type": exam_type,
                        "data_granularity": str(row["data_granularity"] or ""),
                        "record_count": int(row["record_count"] or 0),
                        "source_file": source_file,
                        "source_display_name": _friendly_source_name(
                            province=province,
                            year=year,
                            data_type=table_type,
                            source_kind=source_kind,
                            source_file=source_file,
                        ),
                        "task_id": import_task_id,
                        "import_task_id": import_task_id,
                        "status": "可用",
                        "storage": storage,
                        "target_table": table,
                        "origin": source_kind,
                        "source_kind": source_kind,
                        "updated_at": row["updated_at"],
                        "name": title,
                        "title": title,
                    }
                )
    return datasets


def get_imported_dataset_rows(
    dataset_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    keyword: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
) -> dict[str, Any]:
    """Return one page of normalized rows from a database-backed dataset."""
    clean_dataset_id = str(dataset_id or "").strip()
    dataset = next(
        (
            item
            for item in list_imported_dataset_summaries()
            if item.get("dataset_id") == clean_dataset_id
        ),
        None,
    )
    if not dataset:
        raise FileNotFoundError("数据集不存在或已被删除。")

    table_type = str(dataset.get("data_type") or "")
    target = IMPORT_TARGETS.get(table_type)
    view = DATASET_ROW_VIEWS.get(table_type)
    if not target or not view:
        raise ValueError("当前数据类型暂不支持在线查看。")
    if dataset.get("storage") != "database":
        raise ValueError("当前数据集不是数据库明细，暂不支持在线查看。")

    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(int(page_size or 50), 200))
    normalized_order = str(sort_order or "asc").strip().lower()
    if normalized_order not in {"asc", "desc"}:
        raise ValueError("排序方向只支持 asc 或 desc。")

    columns = [
        column
        for column in view["columns"]
        if not _is_sensitive_dataset_display_field(column[0])
    ]
    sort_fields = {key: expression for key, _, expression in columns}
    clean_sort_by = str(sort_by or "").strip()
    if clean_sort_by and clean_sort_by not in sort_fields:
        raise ValueError("当前字段不支持排序。")

    table = str(target["table"])
    where = [
        "storage = ?",
        "province = ?",
        "year = ?",
        "source_file = ?",
        "source_kind = ?",
        "import_task_id = ?",
    ]
    params: list[Any] = [
        dataset.get("storage") or "database",
        dataset.get("province_slug") or "",
        dataset.get("year"),
        dataset.get("source_file") or "",
        dataset.get("source_kind") or "imported",
        dataset.get("import_task_id") or "",
    ]
    if table_type != "major_catalog":
        where.append("exam_type = ?")
        params.append(dataset.get("exam_type") or "")
    if table_type == "candidate_score_table":
        where.append("data_granularity = ?")
        params.append(dataset.get("data_granularity") or "")

    clean_keyword = str(keyword or "").strip()
    if clean_keyword:
        search_fields = [
            field
            for field in view.get("search_fields") or []
            if not _is_sensitive_dataset_display_field(field)
        ]
        search_sql = " OR ".join(
            f"COALESCE(CAST({field} AS TEXT), '') LIKE ? ESCAPE '\\'"
            for field in search_fields
        )
        where.append(f"({search_sql})")
        pattern = f"%{_escape_like_keyword(clean_keyword)}%"
        params.extend(pattern for _ in search_fields)

    where_sql = " AND ".join(where)
    detail_fields = list(view.get("detail_fields") or [])
    select_fields = [f"{expression} AS {key}" for key, _, expression in columns]
    select_fields.append("extra_fields_json AS __extra_fields_json")
    select_fields.extend(
        f"{expression} AS __detail_{index}"
        for index, (_, expression) in enumerate(detail_fields)
    )
    sort_expression = sort_fields.get(clean_sort_by, "id")
    offset = (safe_page - 1) * safe_page_size

    with connection() as db:
        total = int(
            db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {where_sql}",
                params,
            ).fetchone()[0]
            or 0
        )
        rows = db.execute(
            f"""
            SELECT {', '.join(select_fields)}
            FROM {table}
            WHERE {where_sql}
            ORDER BY {sort_expression} {normalized_order.upper()}, id ASC
            LIMIT ? OFFSET ?
            """,
            (*params, safe_page_size, offset),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        source_row = dict(row)
        extra_fields = json_loads(source_row.pop("__extra_fields_json", "{}"), {})
        if not isinstance(extra_fields, dict):
            extra_fields = {}
        for index, (label, _) in enumerate(detail_fields):
            value = source_row.pop(f"__detail_{index}", None)
            if value not in {None, ""}:
                extra_fields.setdefault(label, value)
        source_row["extra_fields_json"] = json_dumps(extra_fields)
        items.append(sanitize_dataset_row_for_display(source_row, table_type))

    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    return {
        "dataset_id": clean_dataset_id,
        "title": dataset.get("title") or dataset.get("name") or "招考数据",
        "data_type": table_type,
        "data_type_label": dataset.get("data_type_label") or target.get("label") or table_type,
        "province": dataset.get("province") or "",
        "year": dataset.get("year"),
        "exam_type": dataset.get("exam_type") or "",
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": total_pages,
        "columns": [{"key": key, "label": label} for key, label, _ in columns],
        "items": items,
        "privacy_notice": (
            "已隐藏姓名、准考证号等个人敏感信息；原表字段仅用于在线核对，不参与查询筛选或 Agent 分析。"
            if table_type in {"review_candidate_list", "candidate_score_table"}
            else "原表字段仅用于在线核对，不参与查询筛选或 Agent 分析；其中的敏感字段会被过滤。"
        ),
        "message": "" if total else "该数据集暂无可查看明细。",
    }


def _escape_like_keyword(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def sanitize_dataset_row_for_display(row: dict[str, Any], data_type: str = "") -> dict[str, Any]:
    """Remove personal or raw source fields before dataset rows leave the backend."""
    source_row = dict(row or {})
    extra_fields = json_loads(source_row.pop("extra_fields_json", "{}"), {})
    display_row = {
        key: value
        for key, value in source_row.items()
        if not _is_sensitive_dataset_display_field(key)
    }
    display_row["extra_fields"] = sanitize_extra_fields_for_display(extra_fields)
    return display_row


def sanitize_extra_fields_for_display(extra_fields: Any) -> dict[str, Any]:
    """Keep audit-only source fields while removing personal or raw values."""
    if not isinstance(extra_fields, dict):
        return {}
    sanitized: dict[str, Any] = {}
    for field_name, value in extra_fields.items():
        if _is_sensitive_dataset_display_field(field_name):
            continue
        sanitized[str(field_name)] = _sanitize_extra_field_value(value)
    return sanitized


def _sanitize_extra_field_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_extra_fields_for_display(value)
    if isinstance(value, list):
        return [_sanitize_extra_field_value(item) for item in value]
    if not isinstance(value, str):
        return value
    if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", value):
        return "[已隐藏]"
    if re.search(r"(?<!\d)\d{17}[\dXx](?!\d)", value):
        return "[已隐藏]"
    if re.fullmatch(r"\s*\d{12,22}\s*", value):
        return "[已隐藏]"
    return value


def is_sensitive_dataset_display_field(field_name: Any) -> bool:
    """Public privacy predicate shared by import preview and dataset viewer."""
    return _is_sensitive_dataset_display_field(field_name)


def _is_sensitive_dataset_display_field(field_name: Any) -> bool:
    normalized = str(field_name or "").strip().lower()
    if not normalized:
        return False
    if normalized in ALLOWED_DATASET_PHONE_FIELDS:
        return False
    if normalized in SENSITIVE_DATASET_DISPLAY_FIELDS:
        return True
    if normalized.endswith("_phone"):
        return True
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    if compact in {
        "candidatename",
        "candidateno",
        "admissionticket",
        "idcard",
        "identitycard",
        "personalphone",
        "mobile",
        "mobilenumber",
        "mobilephone",
        "phonenumber",
        "telephone",
        "tel",
        "rawrowjson",
    }:
        return True
    return any(marker in str(field_name or "") for marker in SENSITIVE_DATASET_FIELD_MARKERS)


def list_imported_jobs(
    *,
    province: str = "",
    year: int | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    return _list_imported_rows(
        "job_table",
        province=province,
        year=year,
        limit=limit,
    )


def list_imported_score_lines(
    *,
    province: str = "",
    year: int | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    return _list_imported_rows(
        "score_line_table",
        province=province,
        year=year,
        limit=limit,
    )


def list_imported_candidate_scores(
    *,
    province: str = "",
    year: int | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    return _list_imported_rows(
        "candidate_score_table",
        province=province,
        year=year,
        limit=limit,
    )


def list_imported_review_candidates(
    *,
    province: str = "",
    year: int | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    return _list_imported_rows(
        "review_candidate_list",
        province=province,
        year=year,
        limit=limit,
    )


def list_imported_signup_stats(
    *,
    province: str = "",
    year: int | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    return _list_imported_rows(
        "signup_table",
        province=province,
        year=year,
        limit=limit,
    )


def _list_imported_rows(
    table_type: str,
    *,
    province: str = "",
    year: int | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    config = IMPORT_TARGETS[table_type]
    table = str(config["table"])
    where: list[str] = []
    params: list[Any] = []

    aliases = _province_aliases(province)
    if aliases:
        placeholders = ", ".join("?" for _ in aliases)
        if table_type in {"major_catalog", "review_candidate_list"}:
            where.append(f"province IN ({placeholders})")
            params.extend(aliases)
        else:
            where.append(
                f"(province IN ({placeholders}) OR region IN ({placeholders}))"
            )
            params.extend(aliases)
            params.extend(aliases)
    if year is not None:
        where.append("year = ?")
        params.append(int(year))

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    safe_limit = max(1, min(int(limit or 5000), 100000))
    with connection() as db:
        rows = db.execute(
            f"""
            SELECT *
            FROM {table}
            {where_sql}
            ORDER BY COALESCE(year, 0) DESC, id ASC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if table_type == "job_table":
            _merge_public_job_extra_fields(item)
        item.pop("extra_fields_json", None)
        item.pop("raw_row_json", None)
        result.append(item)
    return result


def _merge_public_job_extra_fields(row: dict[str, Any]) -> None:
    """Promote only known public job fields from legacy audit extras."""
    extra_fields = json_loads(row.get("extra_fields_json"), {})
    if not isinstance(extra_fields, dict):
        return
    normalized_extras = {
        _normalize_public_job_extra_key(key): value
        for key, value in extra_fields.items()
        if str(key or "").strip()
    }
    for target_field, aliases in PUBLIC_JOB_EXTRA_FIELD_ALIASES.items():
        if str(row.get(target_field) or "").strip():
            continue
        for alias in aliases:
            value = normalized_extras.get(_normalize_public_job_extra_key(alias))
            if value is not None and str(value).strip():
                row[target_field] = value
                break


def _normalize_public_job_extra_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").strip().lower())


def _task_default_fields(task: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row for row in (task.get("valid_cleaned_rows") or task.get("preview_rows") or [])
        if isinstance(row, dict)
    ]
    first = rows[0] if rows else {}
    task_year = parse_year(task.get("year"))
    file_year = _infer_year_from_text(task.get("file_name"))
    row_year = parse_year(first.get("year"))
    selected_year = task_year or file_year or row_year
    province = (
        str(task.get("province") or "").strip()
        or str(first.get("province") or "").strip()
        or _infer_province_slug(str(task.get("file_name") or ""))
    )
    exam_type = (
        str(task.get("exam_type") or "").strip()
        or str(first.get("exam_type") or "").strip()
        or _infer_exam_type(str(task.get("file_name") or ""))
    )
    return {
        "province": province,
        "exam_type": exam_type,
        "year": selected_year,
    }


def _protect_import_row(
    *,
    table_type: str,
    row: dict[str, Any],
    task: dict[str, Any],
    defaults: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    protected = dict(row)
    fallback_year = parse_year(defaults.get("year")) or parse_year(task.get("year"))
    if fallback_year is None:
        fallback_year = _infer_year_from_text(task.get("file_name")) or DEFAULT_DATA_YEAR
    raw_year_value = protected.get("year")
    raw_year = _optional_int(raw_year_value)
    year_was_corrected = (
        raw_year_value is not None
        and str(raw_year_value).strip() != ""
        and not is_valid_year(raw_year)
    )
    protected["year"] = fallback_year

    fallback_province = str(defaults.get("province") or task.get("province") or "").strip()
    if not fallback_province:
        fallback_province = _infer_province_slug(str(task.get("file_name") or ""))
    if fallback_province:
        protected["province"] = fallback_province

    fallback_exam_type = str(defaults.get("exam_type") or task.get("exam_type") or "").strip()
    if not fallback_exam_type:
        fallback_exam_type = _infer_exam_type(str(task.get("file_name") or ""))
    if fallback_exam_type:
        protected["exam_type"] = fallback_exam_type

    protected["source_file"] = str(protected.get("source_file") or task.get("file_name") or "").strip()
    if table_type == "candidate_score_table":
        protected["data_granularity"] = str(
            protected.get("data_granularity")
            or task.get("data_granularity")
            or "unknown"
        ).strip()
    return protected, year_was_corrected


def _append_task_warning_once(
    task: dict[str, Any],
    *,
    field: str,
    message: str,
    raw_value: Any,
) -> None:
    warnings = task.setdefault("warnings", [])
    if any(
        isinstance(warning, dict)
        and warning.get("field") == field
        and warning.get("message") == message
        for warning in warnings
    ):
        return
    warnings.append(
        {
            "row_index": None,
            "level": "warning",
            "message": message,
            "raw_value": raw_value,
            "field": field,
            "source_column": "",
        }
    )


def _infer_year_from_text(value: Any) -> int | None:
    text = str(value or "")
    full_year = re.search(r"(?<!\d)(20\d{2})(?!\d)", text)
    if full_year:
        return int(full_year.group(1))
    short_year = re.search(r"(?<!\d)(\d{2})年", text)
    if not short_year:
        return None
    year = int(short_year.group(1))
    return 2000 + year if year < 50 else 1900 + year


def _infer_province_slug(value: str) -> str:
    detected = detect_province_in_text(value)
    return str(detected.get("slug") or "")


def _infer_exam_type(value: str) -> str:
    if any(keyword in value for keyword in ["公务员", "省考", "国考", "市考"]):
        return "公务员"
    if "事业单位" in value:
        return "事业单位"
    return ""


def _province_aliases(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    slug = get_province_slug(text) or detect_province_in_text(text).get("slug", "")
    normalized_slug = normalize_province_slug(slug or text)
    name = get_province_name(normalized_slug)
    aliases = [text, normalized_slug, name]
    return [item for item in dict.fromkeys(item for item in aliases if item)]


def _friendly_province(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return get_province_name(text) or detect_province_in_text(text).get("province") or text


def _friendly_imported_dataset_title(
    *,
    province: str,
    year: int,
    exam_type: str,
    data_type: str,
    source_kind: str = "imported",
) -> str:
    prefix = " ".join(part for part in [province, str(year)] if part)
    display_type = (
        "进面分数参考"
        if data_type == "进面分数线" and source_kind == "builtin_seed"
        else data_type
    )
    typed_name = f"{exam_type}{display_type}" if exam_type else display_type
    return f"{prefix} {typed_name}".strip()


def _build_dataset_id(
    *,
    data_type: str,
    province: str,
    year: int,
    exam_type: str,
    source_file: str,
    import_task_id: str,
    source_kind: str,
) -> str:
    identity = "\x1f".join(
        [
            data_type,
            province,
            str(year),
            exam_type,
            source_file,
            import_task_id,
            source_kind,
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"ds_{digest}"


def _friendly_source_name(
    *,
    province: str,
    year: int,
    data_type: str,
    source_kind: str,
    source_file: str,
) -> str:
    labels = {
        "job_table": "公务员考试职位表",
        "score_line_table": "公务员考试进面分数参考",
        "candidate_score_table": "公务员考试成绩汇总",
        "review_candidate_list": "公务员考试资格复审名单",
        "signup_table": "公务员考试报名统计",
        "major_catalog": "招考专业目录",
    }
    return f"{year} 年{province}{labels.get(data_type, '招考数据')}"


def _template_row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["field_mapping"] = json_loads(data.pop("field_mapping_json", "{}"), {})
    data["outputs"] = json_loads(data.pop("outputs_json", "[]"), [])
    data["required_fields"] = json_loads(data.pop("required_fields_json", "[]"), [])
    data["optional_fields"] = json_loads(data.pop("optional_fields_json", "[]"), [])
    return data


def _template_match_score(
    *,
    template: dict[str, Any],
    province: str,
    exam_type: str,
    file_name: str,
    sheet_text: str,
    header_signatures: list[str],
) -> float:
    header_score = _header_signature_score(
        str(template.get("header_signature") or ""),
        header_signatures,
    )
    if header_score >= 0.55:
        return 1000 + (header_score * 100)

    source_keyword = str(template.get("source_keyword") or "").strip()
    sheet_keyword = str(template.get("sheet_keyword") or "").strip()
    if source_keyword and _keyword_matches(source_keyword, file_name):
        return 500 + (20 if sheet_keyword and _keyword_matches(sheet_keyword, sheet_text) else 0)

    score = 0.0
    template_province = str(template.get("province") or "").strip()
    if template_province:
        score += 60 if template_province in _province_aliases(province) else -30
    template_exam_type = str(template.get("exam_type") or "").strip()
    if template_exam_type:
        score += 30 if template_exam_type == str(exam_type or "").strip() else -15
    if sheet_keyword and _keyword_matches(sheet_keyword, sheet_text):
        score += 10
    return score


def _keyword_matches(keyword: str, text: str) -> bool:
    normalized_text = str(text or "").lower()
    parts = [
        item.strip().lower()
        for item in str(keyword or "")
        .replace("，", ",")
        .replace("；", ",")
        .replace(";", ",")
        .split(",")
        if item.strip()
    ]
    return any(part in normalized_text for part in parts)


def _header_signature_score(template_signature: str, signatures: list[str]) -> float:
    template_tokens = _signature_tokens(template_signature)
    if not template_tokens:
        return 0.0
    best_score = 0.0
    for signature in signatures:
        tokens = _signature_tokens(signature)
        if not tokens:
            continue
        best_score = max(
            best_score,
            len(template_tokens & tokens) / max(len(template_tokens | tokens), 1),
        )
    return best_score


def _signature_tokens(signature: str) -> set[str]:
    return {
        token
        for token in str(signature or "").split("|")
        if token
    }


NUMERIC_FIELDS = {
    "year",
    "recruit_count",
    "interview_count",
    "signup_count",
    "approved_count",
    "paid_count",
    "competition_ratio",
    "min_score",
    "max_score",
    "avg_score",
    "xingce_score",
    "shenlun_score",
    "professional_score",
    "subject1_score",
    "subject2_score",
    "subject3_score",
    "bonus_score",
    "written_score",
    "interview_score",
    "total_score",
    "rank",
}


def _db_value(field: str, value: Any) -> Any:
    if value is None:
        return None if field in NUMERIC_FIELDS else ""
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if field in NUMERIC_FIELDS:
        return text if text else None
    return text


def _normalize_source_kind(value: Any) -> str:
    source_kind = str(value or "imported").strip().lower()
    if source_kind not in {"imported", "builtin_seed", "migrated"}:
        return "imported"
    return source_kind


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int_or_zero(value: Any) -> int:
    parsed = _optional_int(value)
    return parsed if parsed is not None else 0


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _decode_json_field(value: Any, fallback: Any) -> Any:
    return json_loads(value, fallback)

# === Review/candidate score sample aggregation for Agent cards ===
def _safe_float_for_summary(value: Any) -> float | None:
    """Convert stored SQLite values to float without treating '-' as zero."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "—", "--", "无", "暂无", "None", "null"}:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _summary_stats(values: list[float]) -> dict[str, float | None]:
    clean = [float(item) for item in values if item is not None]
    if not clean:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "avg": round(sum(clean) / len(clean), 2),
    }


def _exam_type_aliases_for_summary(exam_type: Any) -> list[str]:
    text = str(exam_type or "").strip()
    aliases: list[str] = []
    if text:
        aliases.append(text)
    if text in {"省考", "国考", "公务员", "公考"} or not text:
        aliases.extend(["公务员", "省考", "国考", "公考"])
    if "事业" in text:
        aliases.extend(["事业单位", "事业编"])
    return list(dict.fromkeys(item for item in aliases if item))


def _build_score_sample_where(
    *,
    province: str = "",
    year: int | None = None,
    exam_type: str = "",
    job_code: str = "",
    job_name: str = "",
    unit_name: str = "",
) -> tuple[str, list[Any]]:
    where: list[str] = []
    params: list[Any] = []

    aliases = _province_aliases(province)
    if aliases:
        placeholders = ", ".join("?" for _ in aliases)
        where.append(f"province IN ({placeholders})")
        params.extend(aliases)

    if year is not None:
        where.append("year = ?")
        params.append(int(year))

    exam_aliases = _exam_type_aliases_for_summary(exam_type)
    if exam_aliases:
        placeholders = ", ".join("?" for _ in exam_aliases)
        where.append(f"exam_type IN ({placeholders})")
        params.extend(exam_aliases)

    clean_code = str(job_code or "").strip()
    if clean_code:
        where.append("job_code = ?")
        params.append(clean_code)
    else:
        # 只有没有职位代码时才允许文本兜底，避免误把相似岗位混到一起。
        text_filters: list[str] = []
        if job_name:
            text_filters.append("job_name LIKE ?")
            params.append(f"%{str(job_name).strip()}%")
        if unit_name:
            text_filters.append("unit_name LIKE ?")
            params.append(f"%{str(unit_name).strip()}%")
        if text_filters:
            where.append("(" + " AND ".join(text_filters) + ")")

    where_sql = " AND ".join(where) if where else "1=1"
    return where_sql, params


def _aggregate_score_sample_rows(rows: list[Any], *, source_type: str) -> dict[str, Any]:
    values: dict[str, list[float]] = {
        "written_score": [],
        "xingce_score": [],
        "shenlun_score": [],
        "professional_score": [],
        "interview_score": [],
        "total_score": [],
        "rank": [],
    }
    for row in rows:
        data = dict(row)
        for key in values:
            number = _safe_float_for_summary(data.get(key))
            if number is not None:
                values[key].append(number)

    sample_count = len(rows)
    is_review_sample = source_type == "review_candidate_sample"
    prefix = "review" if is_review_sample else "candidate"
    source_label = "资格复审名单成绩样本" if is_review_sample else "候选人成绩样本"
    result: dict[str, Any] = {
        "score_source_type": source_type,
        "score_match_type": source_type,
        "score_sample_count": sample_count,
        "sample_count": sample_count,
        "score_data_source_label": source_label,
        "score_match_reason": (
            "该数据由资格复审名单按岗位聚合得到，不等同于官方最低进面分。"
            if is_review_sample
            else "该数据由候选人成绩表按岗位聚合得到，不等同于岗位官方最低进面分。"
        ),
    }
    if not is_review_sample:
        result["candidate_score_sample_count"] = sample_count
    for key, numbers in values.items():
        stats = _summary_stats(numbers)
        result[f"{key}_min"] = stats["min"]
        result[f"{key}_max"] = stats["max"]
        result[f"{key}_avg"] = stats["avg"]
        result[f"{key}_count"] = len(numbers)
        if key == "rank":
            result[f"{prefix}_rank_min"] = stats["min"]
            result[f"{prefix}_rank_max"] = stats["max"]
        else:
            result[f"{prefix}_{key}_min"] = stats["min"]
            result[f"{prefix}_{key}_avg"] = stats["avg"]
            result[f"{prefix}_{key}_max"] = stats["max"]
    return result


def get_review_score_summary_by_job(
    *,
    province: str = "",
    year: int | None = None,
    exam_type: str = "",
    job_code: str = "",
    job_name: str = "",
    unit_name: str = "",
) -> dict[str, Any] | None:
    """Return aggregate review-candidate score sample for one job without personal fields."""
    where_sql, params = _build_score_sample_where(
        province=province,
        year=year,
        exam_type=exam_type,
        job_code=job_code,
        job_name=job_name,
        unit_name=unit_name,
    )
    with connection() as db:
        rows = db.execute(
            f"""
            SELECT written_score, xingce_score, shenlun_score, professional_score,
                   total_score, rank
            FROM exam_review_candidates
            WHERE {where_sql}
            """,
            params,
        ).fetchall()
    if not rows:
        return None
    return _aggregate_score_sample_rows(rows, source_type="review_candidate_sample")


def get_candidate_score_summary_by_job(
    *,
    province: str = "",
    year: int | None = None,
    exam_type: str = "",
    job_code: str = "",
    job_name: str = "",
    unit_name: str = "",
) -> dict[str, Any] | None:
    """Return aggregate candidate-score sample for one job without personal fields."""
    where_sql, params = _build_score_sample_where(
        province=province,
        year=year,
        exam_type=exam_type,
        job_code=job_code,
        job_name=job_name,
        unit_name=unit_name,
    )
    with connection() as db:
        rows = db.execute(
            f"""
            SELECT written_score, xingce_score, shenlun_score, professional_score,
                   interview_score, total_score, rank
            FROM exam_candidate_scores
            WHERE {where_sql}
            """,
            params,
        ).fetchall()
    if not rows:
        return None
    return _aggregate_score_sample_rows(rows, source_type="candidate_score_sample")
