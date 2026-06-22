"""Service layer for structured exam data import previews and confirmation."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from app.db.import_repository import (
    delete_dataset_data,
    delete_import_task_data,
    find_matching_import_template,
    get_imported_dataset_rows,
    list_import_templates,
    is_sensitive_dataset_display_field,
    save_import_template,
    sanitize_dataset_row_for_display,
)
from app.imports.cleaners import clean_table_rows, clean_value, normalize_header
from app.imports.field_mapper import (
    editable_standard_fields_for,
    field_mapping_by_source,
    header_signature_for_result,
    map_fields,
    map_fields_from_source_mapping,
    source_headers_for_result,
    standard_fields_for,
)
from app.imports.file_reader import SUPPORTED_FILE_EXTENSIONS, RawTable, read_import_file
from app.imports.import_store import confirm_task, load_task, save_task, save_uploaded_file
from app.imports.import_type_registry import (
    IMPORT_TYPE_REGISTRY,
    get_import_type,
    is_importable_type,
    list_public_import_types,
)
from app.imports.report_builder import build_import_report
from app.imports.table_detector import (
    JOB_STRUCTURAL_GROUPS,
    TYPE_LABELS,
    detect_table_type,
    mixed_output_label,
    recommend_dataset_outputs,
)
from app.tools.province_registry import detect_province_in_text


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
LOW_CONFIDENCE_THRESHOLD = 0.75
TYPE_SCORE_GAP_THRESHOLD = 0.12
SCORE_FIELDS = ["total_score", "written_score", "interview_score"]
NON_IMPORTABLE_TABLE_TYPES = {
    type_key
    for type_key in IMPORT_TYPE_REGISTRY
    if not is_importable_type(type_key)
}
PROVINCE_HINTS = {
    "福建省": "fujian",
    "福建": "fujian",
    "上海市": "shanghai",
    "上海": "shanghai",
    "黑龙江省": "heilongjiang",
    "黑龙江": "heilongjiang",
}


def process_uploaded_file(
    *,
    file_name: str,
    content: bytes,
    province: str | None = None,
    exam_type: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    """Persist an uploaded file, build a preview, and save the V1 task."""
    _validate_upload(file_name, content)
    task_id = f"import_{uuid.uuid4().hex}"
    upload_path = save_uploaded_file(task_id, file_name, content)
    return build_import_task(
        upload_path,
        original_file_name=file_name,
        province=province,
        exam_type=exam_type,
        year=year,
        task_id=task_id,
        persist=True,
    )


def build_import_task(
    file_path: Path,
    *,
    original_file_name: str | None = None,
    province: str | None = None,
    exam_type: str | None = None,
    year: int | None = None,
    task_id: str | None = None,
    persist: bool = False,
    source_field_mapping: dict[str, str] | None = None,
    forced_detected_type: str | None = None,
    forced_data_granularity: str | None = None,
    selected_sheet: str | None = None,
    header_row: int | None = None,
    sub_header_row: int | None = None,
    data_start_row: int | None = None,
    structure_confirmed: bool = False,
    outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an import preview task from a local CSV/Excel file."""
    task_id = task_id or f"import_{uuid.uuid4().hex}"
    file_name = original_file_name or file_path.name
    all_raw_tables = read_import_file(file_path)
    if not all_raw_tables:
        raise ValueError("未读取到可处理的表格数据")
    sheet_options = [table.sheet_name for table in all_raw_tables]
    clean_selected_sheet = str(selected_sheet or "").strip()
    raw_tables = (
        [table for table in all_raw_tables if table.sheet_name == clean_selected_sheet]
        if clean_selected_sheet
        else all_raw_tables
    )
    if not raw_tables:
        raise ValueError("选择的工作表不存在，请重新选择")

    if not clean_selected_sheet and outputs is None and not forced_detected_type:
        mixed_sheet_candidates = [
            (table, recommend_dataset_outputs(table.rows))
            for table in raw_tables
        ]
        mixed_sheet_candidates = [
            item for item in mixed_sheet_candidates if len(item[1]) > 1
        ]
        if mixed_sheet_candidates:
            preferred_table, _ = max(
                mixed_sheet_candidates,
                key=lambda item: (
                    len(item[1]),
                    "job_table" in {output.get("dataset_type") for output in item[1]},
                    sum(float(output.get("confidence") or 0) for output in item[1]),
                    -all_raw_tables.index(item[0]),
                ),
            )
            raw_tables = [preferred_table]
            clean_selected_sheet = preferred_table.sheet_name

    recommended_outputs = (
        recommend_dataset_outputs(raw_tables[0].rows)
        if len(raw_tables) == 1
        else []
    )
    if outputs is not None or (not forced_detected_type and len(recommended_outputs) > 1):
        return _build_multi_output_import_task(
            file_path=file_path,
            file_name=file_name,
            task_id=task_id,
            raw_table=raw_tables[0],
            sheet_options=sheet_options,
            output_configs=(
                outputs
                if outputs is not None
                else [
                    {"dataset_type": output.get("dataset_type"), "enabled": True}
                    for output in recommended_outputs
                ]
            ),
            province=province,
            exam_type=exam_type,
            year=year,
            header_row=header_row,
            sub_header_row=sub_header_row,
            data_start_row=data_start_row,
            structure_confirmed=structure_confirmed,
            persist=persist,
        )

    detections = [
        (
            raw_table,
            detect_table_type(
                raw_table.rows,
                context="",
            ),
        )
        for raw_table in raw_tables
    ]
    best_detection = max(detections, key=lambda item: item[1].confidence)[1]
    file_detection = detect_table_type([], context=file_name)
    type_candidates = _merge_type_candidates(detections)
    detected_type = forced_detected_type or best_detection.detected_type
    detected_type_label = TYPE_LABELS.get(detected_type, TYPE_LABELS["unknown"])
    confidence = _type_candidate_score(type_candidates, detected_type)
    schema_type = _field_schema_type(detected_type)
    source_field_mapping = _sanitize_source_field_mapping(source_field_mapping, schema_type)

    warnings: list[dict[str, Any]] = []
    inferred_defaults, default_warnings = _infer_import_defaults(
        file_name=file_name,
        raw_tables=raw_tables,
        table_type=detected_type,
        province=province,
        exam_type=exam_type,
        year=year,
    )
    warnings.extend(default_warnings)

    initial_infos = _build_sheet_mapping_infos(
        raw_tables,
        schema_type,
        header_row=header_row,
        sub_header_row=sub_header_row,
    )
    header_signatures = [info["header_signature"] for info in initial_infos if info.get("header_signature")]
    source_headers = _merge_source_headers(initial_infos)
    initial_source_mapping = _merge_source_mapping(initial_infos)
    data_granularity = forced_data_granularity or _infer_data_granularity(
        file_name=file_name,
        raw_tables=raw_tables,
        table_type=schema_type,
        source_mapping=source_field_mapping or initial_source_mapping,
    )

    template = None
    template_mapping: dict[str, str] | None = None
    if (
        source_field_mapping is None
        and not forced_detected_type
        and detected_type not in NON_IMPORTABLE_TABLE_TYPES
    ):
        template = find_matching_import_template(
            data_type=detected_type,
            province=str(inferred_defaults.get("province") or ""),
            exam_type=str(inferred_defaults.get("exam_type") or ""),
            file_name=file_name,
            sheet_names=[table.sheet_name for table in raw_tables],
            header_signatures=header_signatures,
        )
        if template:
            template_mapping = {
                source: target
                for source, target in (template.get("field_mapping") or {}).items()
                if target in set(editable_standard_fields_for(schema_type))
            }

    active_source_mapping = source_field_mapping or template_mapping
    effective_header_row = header_row or _optional_positive_int(template.get("header_row") if template else None)
    effective_sub_header_row = sub_header_row or _optional_positive_int(
        template.get("sub_header_row") if template else None
    )
    effective_data_start_row = data_start_row or _optional_positive_int(
        template.get("data_start_row") if template else None
    )
    effective_sub_header_index = _row_number_to_index(effective_sub_header_row)
    if effective_sub_header_row is None and (structure_confirmed or template is not None):
        effective_sub_header_index = -1
    rules = _validation_rules(
        table_type=schema_type,
        data_granularity=data_granularity,
    )

    if confidence < LOW_CONFIDENCE_THRESHOLD and not forced_detected_type:
        warnings.append(
            {
                "row_index": None,
                "level": "warning",
                "message": "数据类型置信度过低，请人工核对后再确认入库",
                "raw_value": confidence,
                "field": "detected_type",
                "source_column": "",
            }
        )

    clean_payload = _clean_import_tables(
        raw_tables=raw_tables,
        detections=detections,
        detected_type=detected_type,
        file_name=file_name,
        defaults={
            **inferred_defaults,
            "data_granularity": data_granularity,
        },
        source_field_mapping=active_source_mapping,
        header_row_index=_row_number_to_index(effective_header_row),
        sub_header_row_index=effective_sub_header_index,
        data_start_row_index=_row_number_to_index(effective_data_start_row),
        rules=rules,
        warnings=warnings,
    )
    warnings = clean_payload["warnings"]
    import_report = build_import_report(
        sheet_reports=clean_payload["sheet_reports"],
        total_rows=clean_payload["total_rows"],
        valid_rows=len(clean_payload["valid_rows"]),
        warning_rows=clean_payload["warning_rows"],
        duplicate_rows=clean_payload["duplicate_rows"],
        warnings=warnings,
    )

    field_mapping = clean_payload["field_mapping"] or _target_mapping_from_source(active_source_mapping or {})
    source_mapping = clean_payload["field_mapping_by_source"] or active_source_mapping or {}
    display_source_headers = clean_payload.get("source_headers") or list(source_mapping.keys()) or source_headers
    task = {
        "task_id": task_id,
        "file_name": file_name,
        "upload_path": str(file_path),
        "detected_type": detected_type,
        "detected_type_label": detected_type_label,
        "confidence": confidence,
        "type_candidates": type_candidates,
        "type_confirmed": bool(forced_detected_type),
        "data_granularity": data_granularity,
        "province": inferred_defaults.get("province"),
        "exam_type": inferred_defaults.get("exam_type"),
        "year": inferred_defaults.get("year"),
        "total_rows": clean_payload["total_rows"],
        "valid_rows": len(clean_payload["valid_rows"]),
        "warning_rows": clean_payload["warning_rows"],
        "preview_rows": clean_payload["cleaned_rows"][:20],
        "field_mapping": field_mapping,
        "field_mapping_by_source": source_mapping,
        "source_headers": display_source_headers,
        "standard_fields": editable_standard_fields_for(schema_type),
        "field_labels": dict(get_import_type(detected_type).get("field_labels") or {}),
        "required_fields": rules["required_fields"],
        "required_any_fields": rules["required_any_fields"],
        "required_any_groups": rules["required_any_groups"],
        "optional_fields": rules["optional_fields"],
        "available_types": list_public_import_types(),
        "warnings": warnings,
        "warning_count": len(warnings),
        "warning_summary": _build_warning_summary(warnings, clean_payload["duplicate_rows"]),
        "import_report": import_report,
        "sheet_summary": _build_sheet_summary(clean_payload["sheet_reports"]),
        "sheet_options": sheet_options,
        "selected_sheet": clean_selected_sheet,
        "header_row": clean_payload.get("header_row") or effective_header_row,
        "sub_header_row": clean_payload.get("sub_header_row") or effective_sub_header_row,
        "data_start_row": clean_payload.get("data_start_row") or effective_data_start_row,
        "header_signature": clean_payload["header_signature"] or (header_signatures[0] if header_signatures else ""),
        "header_signatures": header_signatures,
        "template_applied": bool(template),
        "template_id": template.get("id") if template else None,
        "template_name": template.get("template_name") if template else "",
        "template_message": f"已复用历史映射模板：{template.get('template_name')}" if template else "",
        "status": "AUTO_DETECTED",
        "cleaned_rows": clean_payload["cleaned_rows"],
        "valid_cleaned_rows": clean_payload["valid_rows"],
    }
    task["importable"] = detected_type not in NON_IMPORTABLE_TABLE_TYPES
    task["type_conflict_reasons"] = _build_type_conflict_reasons(
        detected_type=detected_type,
        best_detection=best_detection,
        file_detection=file_detection,
        type_candidates=type_candidates,
        source_mapping=source_mapping,
        source_headers=display_source_headers,
        type_confirmed=bool(forced_detected_type),
    )
    task["requires_type_confirmation"] = bool(task["type_conflict_reasons"]) or (
        confidence < LOW_CONFIDENCE_THRESHOLD and not forced_detected_type
    )
    task["blocking_reasons"] = _build_blocking_reasons(task)
    task["field_status"] = _build_field_status(task)
    missing_required_mapping = any(
        item.get("satisfied") is False
        for item in task["field_status"]
    )
    if task["requires_type_confirmation"]:
        task["status"] = "NEED_TYPE_CONFIRMATION"
    elif (
        missing_required_mapping
        or int(task.get("valid_rows") or 0) <= 0
        or bool(task["blocking_reasons"])
    ):
        task["status"] = "NEED_FIELD_MAPPING"
    else:
        task["status"] = "PREVIEW_READY"
    if detected_type == "unknown":
        task["detected_type_label"] = TYPE_LABELS["unknown"]
    if persist:
        save_task(task)
    return task


def get_import_preview(task_id: str) -> dict[str, Any]:
    return load_task(task_id)


def remap_import_task(
    task_id: str,
    field_mapping: dict[str, str],
    detected_type: str = "",
    *,
    selected_sheet: str = "",
    header_row: int | None = None,
    sub_header_row: int | None = None,
    data_start_row: int | None = None,
    outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    task = load_task(task_id)
    upload_path = Path(str(task.get("upload_path") or ""))
    if not upload_path.exists():
        raise FileNotFoundError("导入源文件不存在，请重新上传")
    resolved_detected_type = detected_type or str(task.get("detected_type") or "")
    previous_detected_type = str(task.get("detected_type") or "")
    previous_granularity = str(task.get("data_granularity") or "").strip()
    preview = build_import_task(
        upload_path,
        original_file_name=str(task.get("file_name") or upload_path.name),
        province=_task_default(task, "province"),
        exam_type=_task_default(task, "exam_type"),
        year=_task_default_int(task, "year"),
        task_id=task_id,
        persist=False,
        source_field_mapping=field_mapping,
        forced_detected_type=resolved_detected_type,
        forced_data_granularity=(
            previous_granularity
            if resolved_detected_type == "candidate_score_table"
            and previous_detected_type == "candidate_score_table"
            and previous_granularity not in {"", "unknown"}
            else None
        ),
        selected_sheet=selected_sheet,
        header_row=header_row,
        sub_header_row=sub_header_row,
        data_start_row=data_start_row,
        structure_confirmed=True,
        outputs=outputs,
    )
    save_task(preview)
    return preview


def save_template_for_task(
    task_id: str,
    *,
    template_name: str,
    province: str = "",
    data_type: str = "",
    exam_type: str = "",
    source_keyword: str = "",
    sheet_keyword: str = "",
    field_mapping: dict[str, str] | None = None,
    header_row: int | None = None,
    sub_header_row: int | None = None,
    data_start_row: int | None = None,
    outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    task = load_task(task_id)
    if task.get("status") != "PREVIEW_READY" or task.get("blocking_reasons"):
        raise ValueError("请先完成类型确认和字段映射，生成可入库的清洗预览后再保存模板")
    resolved_data_type = data_type or str(task.get("detected_type") or "")
    clean_mapping = _sanitize_source_field_mapping(
        field_mapping or task.get("field_mapping_by_source") or {},
        resolved_data_type,
    ) or {}
    clean_outputs = _sanitize_output_configs(
        outputs if outputs is not None else task.get("outputs") or [],
    )
    saved = save_import_template(
        template_name=template_name,
        data_type=resolved_data_type,
        province=province or _task_default(task, "province"),
        exam_type=exam_type or _task_default(task, "exam_type"),
        source_keyword=source_keyword or _default_source_keyword(str(task.get("file_name") or "")),
        sheet_keyword=sheet_keyword or str(task.get("selected_sheet") or ""),
        header_signature=str(task.get("header_signature") or ""),
        header_row=header_row or _optional_positive_int(task.get("header_row")),
        sub_header_row=sub_header_row or _optional_positive_int(task.get("sub_header_row")),
        data_start_row=data_start_row or _optional_positive_int(task.get("data_start_row")),
        field_mapping=clean_mapping,
        outputs=clean_outputs,
        required_fields=list(task.get("required_fields") or []),
        optional_fields=list(task.get("optional_fields") or []),
    )
    return {
        "status": "SAVED",
        "message": "导入模板已保存，下次相似文件将自动套用。",
        "template": saved,
    }


def list_templates(
    *,
    data_type: str = "",
    province: str = "",
) -> dict[str, Any]:
    templates = list_import_templates(data_type=data_type, province=province)
    return {"total": len(templates), "items": templates}


def confirm_import_task(task_id: str) -> dict[str, Any]:
    return confirm_task(task_id)


def delete_import_task(task_id: str) -> dict[str, Any]:
    result = delete_import_task_data(task_id)
    if not result:
        raise FileNotFoundError("导入任务不存在或已被删除")
    return result


def delete_import_dataset(dataset_id: str) -> dict[str, Any]:
    result = delete_dataset_data(dataset_id)
    if not result:
        raise FileNotFoundError("数据集不存在或已被删除")
    return result


def view_import_dataset_rows(
    dataset_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    keyword: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
) -> dict[str, Any]:
    return get_imported_dataset_rows(
        dataset_id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def public_preview(task: dict[str, Any]) -> dict[str, Any]:
    """Drop internal full-row payloads and local paths from API preview responses."""
    preview = {
        key: value
        for key, value in task.items()
        if key not in {"cleaned_rows", "valid_cleaned_rows", "upload_path"}
    }
    all_warnings = [
        warning for warning in (task.get("warnings") or [])
        if isinstance(warning, dict)
    ]
    preview["warnings"] = all_warnings[:20]
    preview["warning_count"] = len(all_warnings)
    preview["preview_rows"] = [
        sanitize_dataset_row_for_display(
            row,
            str(task.get("detected_type") or ""),
        )
        for row in task.get("preview_rows") or []
        if isinstance(row, dict)
    ]
    public_outputs: list[dict[str, Any]] = []
    for output in task.get("outputs") or []:
        if not isinstance(output, dict):
            continue
        dataset_type = str(output.get("dataset_type") or "")
        public_output = {
            key: value
            for key, value in output.items()
            if key not in {"cleaned_rows", "valid_cleaned_rows"}
        }
        public_output["warnings"] = [
            warning
            for warning in (output.get("warnings") or [])[:20]
            if isinstance(warning, dict)
        ]
        public_output["preview_rows"] = [
            sanitize_dataset_row_for_display(row, dataset_type)
            for row in output.get("preview_rows") or []
            if isinstance(row, dict)
        ]
        public_outputs.append(public_output)
    preview["outputs"] = public_outputs
    return preview


def _build_multi_output_import_task(
    *,
    file_path: Path,
    file_name: str,
    task_id: str,
    raw_table: RawTable,
    sheet_options: list[str],
    output_configs: list[dict[str, Any]],
    province: str | None,
    exam_type: str | None,
    year: int | None,
    header_row: int | None,
    sub_header_row: int | None,
    data_start_row: int | None,
    structure_confirmed: bool,
    persist: bool,
) -> dict[str, Any]:
    """Build independent cleaned outputs from one shared Sheet structure."""
    clean_outputs = _sanitize_output_configs(output_configs)
    if not clean_outputs:
        raise ValueError("当前 Sheet 没有可用的输出数据集，请至少选择一种数据类型")
    primary_type = str(clean_outputs[0]["dataset_type"])
    inferred_defaults, default_warnings = _infer_import_defaults(
        file_name=file_name,
        raw_tables=[raw_table],
        table_type=primary_type,
        province=province,
        exam_type=exam_type,
        year=year,
    )
    primary_infos = _build_sheet_mapping_infos(
        [raw_table],
        primary_type,
        header_row=header_row,
        sub_header_row=sub_header_row,
    )
    header_signatures = [
        info["header_signature"]
        for info in primary_infos
        if info.get("header_signature")
    ]
    has_explicit_mapping = any(output.get("field_mapping") for output in clean_outputs)
    template = None
    if not has_explicit_mapping and not structure_confirmed:
        template = find_matching_import_template(
            data_type=primary_type,
            province=str(inferred_defaults.get("province") or ""),
            exam_type=str(inferred_defaults.get("exam_type") or ""),
            file_name=file_name,
            sheet_names=[raw_table.sheet_name],
            header_signatures=header_signatures,
        )
        template_outputs = _sanitize_output_configs(template.get("outputs") or []) if template else []
        if template_outputs:
            clean_outputs = template_outputs
        else:
            template = None

    effective_header_row = header_row or _optional_positive_int(template.get("header_row") if template else None)
    effective_sub_header_row = sub_header_row or _optional_positive_int(
        template.get("sub_header_row") if template else None
    )
    effective_data_start_row = data_start_row or _optional_positive_int(
        template.get("data_start_row") if template else None
    )
    effective_sub_header_index = _row_number_to_index(effective_sub_header_row)
    if effective_sub_header_row is None and (structure_confirmed or template is not None):
        effective_sub_header_index = -1

    detection = detect_table_type(raw_table.rows, context="")
    built_outputs: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = list(default_warnings)
    duplicate_rows = 0
    for output_config in clean_outputs:
        dataset_type = str(output_config["dataset_type"])
        source_mapping = _sanitize_source_field_mapping(
            output_config.get("field_mapping") or {},
            dataset_type,
        )
        rules = _validation_rules(dataset_type, "unknown")
        if dataset_type == "score_line_table" and "job_code" not in rules["required_fields"]:
            rules["required_fields"] = [*rules["required_fields"], "job_code"]
        output_warnings: list[dict[str, Any]] = []
        clean_payload = _clean_import_tables(
            raw_tables=[raw_table],
            detections=[(raw_table, detection)],
            detected_type=dataset_type,
            file_name=file_name,
            defaults={**inferred_defaults, "data_granularity": "unknown"},
            source_field_mapping=source_mapping,
            header_row_index=_row_number_to_index(effective_header_row),
            sub_header_row_index=effective_sub_header_index,
            data_start_row_index=_row_number_to_index(effective_data_start_row),
            rules=rules,
            warnings=output_warnings,
        )
        mapping = clean_payload["field_mapping"] or _target_mapping_from_source(source_mapping or {})
        mapping_by_source = clean_payload["field_mapping_by_source"] or source_mapping or {}
        output_task = {
            "detected_type": dataset_type,
            "field_mapping": mapping,
            "required_fields": rules["required_fields"],
            "required_any_fields": rules["required_any_fields"],
            "required_any_groups": rules["required_any_groups"],
            "optional_fields": rules["optional_fields"],
            "year": inferred_defaults.get("year"),
            "province": inferred_defaults.get("province"),
            "exam_type": inferred_defaults.get("exam_type"),
        }
        field_status = _build_field_status(output_task)
        missing_fields = [
            str(item.get("field") or "")
            for item in field_status
            if item.get("satisfied") is False
        ]
        blocking_reasons: list[str] = []
        if missing_fields:
            labels = dict(get_import_type(dataset_type).get("field_labels") or {})
            blocking_reasons.append(
                "缺少必要字段：" + "、".join(labels.get(field, field) for field in missing_fields)
            )
        if not clean_payload["valid_rows"]:
            blocking_reasons.append("没有有效记录")
        label = str(get_import_type(dataset_type).get("label") or dataset_type)
        built_output = {
            "dataset_type": dataset_type,
            "dataset_type_label": label,
            "target_table": str(get_import_type(dataset_type).get("target_table") or ""),
            "enabled": True,
            "dedupe_keys": ["province", "year", "exam_type", "job_code"],
            "field_mapping": mapping,
            "field_mapping_by_source": mapping_by_source,
            "source_headers": clean_payload.get("source_headers") or list(mapping_by_source),
            "standard_fields": editable_standard_fields_for(dataset_type),
            "field_labels": dict(get_import_type(dataset_type).get("field_labels") or {}),
            "required_fields": rules["required_fields"],
            "required_any_fields": rules["required_any_fields"],
            "required_any_groups": rules["required_any_groups"],
            "optional_fields": rules["optional_fields"],
            "field_status": field_status,
            "total_rows": clean_payload["total_rows"],
            "valid_rows": len(clean_payload["valid_rows"]),
            "warning_rows": clean_payload["warning_rows"],
            "duplicate_rows": clean_payload["duplicate_rows"],
            "warning_count": len(output_warnings),
            "warnings": output_warnings,
            "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
            "preview_rows": clean_payload["cleaned_rows"][:20],
            "cleaned_rows": clean_payload["cleaned_rows"],
            "valid_cleaned_rows": clean_payload["valid_rows"],
            "header_row": clean_payload.get("header_row") or effective_header_row,
            "sub_header_row": clean_payload.get("sub_header_row") or effective_sub_header_row,
            "data_start_row": clean_payload.get("data_start_row") or effective_data_start_row,
            "header_signature": clean_payload.get("header_signature") or "",
        }
        built_outputs.append(built_output)
        duplicate_rows += int(clean_payload["duplicate_rows"] or 0)
        all_warnings.extend(output_warnings)

    output_label = mixed_output_label(built_outputs)
    requires_output_confirmation = not structure_confirmed and template is None
    blocking_reasons: list[str] = []
    if not inferred_defaults.get("province"):
        blocking_reasons.append("缺少省份，且无法从文件名自动识别")
    if inferred_defaults.get("year") is None:
        blocking_reasons.append("缺少年份")
    if not inferred_defaults.get("exam_type"):
        blocking_reasons.append("缺少考试类型")
    if requires_output_confirmation:
        blocking_reasons.append("检测到该 Sheet 可生成多个数据集，请确认输出列表和各自字段映射")
    for output in built_outputs:
        blocking_reasons.extend(
            f"{output['dataset_type_label']}：{reason}"
            for reason in output.get("blocking_reasons") or []
        )
    first_output = built_outputs[0]
    valid_rows = sum(int(output.get("valid_rows") or 0) for output in built_outputs)
    warning_rows = sum(int(output.get("warning_rows") or 0) for output in built_outputs)
    total_rows = max((int(output.get("total_rows") or 0) for output in built_outputs), default=0)
    import_report = {
        "multi_output": True,
        "sheet_name": raw_table.sheet_name,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "duplicate_rows": duplicate_rows,
        "outputs": [
            {
                "dataset_type": output["dataset_type"],
                "dataset_type_label": output["dataset_type_label"],
                "total_rows": output["total_rows"],
                "valid_rows": output["valid_rows"],
                "warning_rows": output["warning_rows"],
                "duplicate_rows": output["duplicate_rows"],
            }
            for output in built_outputs
        ],
    }
    task = {
        "task_id": task_id,
        "file_name": file_name,
        "upload_path": str(file_path),
        "detected_type": first_output["dataset_type"],
        "detected_type_label": output_label,
        "confidence": round(min(float(output.get("confidence") or 0.99) for output in clean_outputs), 2),
        "type_candidates": detection.candidates,
        "type_confirmed": bool(structure_confirmed or template),
        "multi_output": True,
        "mixed_output_label": output_label,
        "requires_output_confirmation": requires_output_confirmation,
        "outputs": built_outputs,
        "data_granularity": "mixed_sheet",
        "province": inferred_defaults.get("province"),
        "exam_type": inferred_defaults.get("exam_type"),
        "year": inferred_defaults.get("year"),
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "preview_rows": first_output["preview_rows"],
        "field_mapping": first_output["field_mapping"],
        "field_mapping_by_source": first_output["field_mapping_by_source"],
        "source_headers": first_output["source_headers"],
        "standard_fields": first_output["standard_fields"],
        "field_labels": first_output["field_labels"],
        "required_fields": first_output["required_fields"],
        "required_any_fields": first_output["required_any_fields"],
        "required_any_groups": first_output["required_any_groups"],
        "optional_fields": first_output["optional_fields"],
        "available_types": list_public_import_types(),
        "warnings": all_warnings,
        "warning_count": len(all_warnings),
        "warning_summary": _build_warning_summary(all_warnings, duplicate_rows),
        "import_report": import_report,
        "sheet_summary": f"已选择工作表“{raw_table.sheet_name}”，可生成 {len(built_outputs)} 个数据集。",
        "sheet_options": sheet_options,
        "selected_sheet": raw_table.sheet_name,
        "header_row": first_output.get("header_row"),
        "sub_header_row": first_output.get("sub_header_row"),
        "data_start_row": first_output.get("data_start_row"),
        "header_signature": first_output.get("header_signature") or "",
        "header_signatures": header_signatures,
        "template_applied": bool(template),
        "template_id": template.get("id") if template else None,
        "template_name": template.get("template_name") if template else "",
        "template_message": f"已复用多输出模板：{template.get('template_name')}" if template else "",
        "importable": True,
        "requires_type_confirmation": False,
        "type_conflict_reasons": [],
        "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
        "field_status": first_output["field_status"],
        "status": "NEED_FIELD_MAPPING" if blocking_reasons else "PREVIEW_READY",
        "cleaned_rows": first_output["cleaned_rows"],
        "valid_cleaned_rows": first_output["valid_cleaned_rows"],
    }
    if persist:
        save_task(task)
    return task


def _sanitize_output_configs(outputs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    clean_outputs: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    for output in outputs or []:
        if not isinstance(output, dict) or output.get("enabled", True) is False:
            continue
        dataset_type = str(output.get("dataset_type") or "").strip()
        if dataset_type in seen_types or not is_importable_type(dataset_type):
            continue
        raw_mapping = output.get("field_mapping_by_source") or output.get("field_mapping") or {}
        editable_fields = set(editable_standard_fields_for(dataset_type))
        if isinstance(raw_mapping, dict) and raw_mapping and set(raw_mapping).issubset(editable_fields):
            raw_mapping = {
                str(source): str(target)
                for target, source in raw_mapping.items()
                if source
            }
        clean_mapping = _sanitize_source_field_mapping(
            raw_mapping if isinstance(raw_mapping, dict) else {},
            dataset_type,
        ) or {}
        clean_outputs.append(
            {
                "dataset_type": dataset_type,
                "enabled": True,
                "field_mapping": clean_mapping,
                "dedupe_keys": ["province", "year", "exam_type", "job_code"],
            }
        )
        seen_types.add(dataset_type)
    return clean_outputs


def _clean_import_tables(
    *,
    raw_tables: list[RawTable],
    detections: list[tuple[RawTable, Any]],
    detected_type: str,
    file_name: str,
    defaults: dict[str, Any],
    source_field_mapping: dict[str, str] | None,
    header_row_index: int | None,
    sub_header_row_index: int | None,
    data_start_row_index: int | None,
    rules: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    cleaned_rows: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []
    field_mapping: dict[str, str] = {}
    source_mapping: dict[str, str] = {}
    sheet_reports: list[dict[str, Any]] = []
    total_rows = 0
    warning_rows = 0
    duplicate_rows = 0
    header_signature = ""
    resolved_header_row: int | None = None
    resolved_sub_header_row: int | None = None
    resolved_data_start_row: int | None = None
    schema_type = _field_schema_type(detected_type)
    unmapped_headers_seen: set[str] = set()
    resolved_source_headers: list[str] = []

    detection_by_sheet = {id(raw_table): detection for raw_table, detection in detections}
    for raw_table in raw_tables:
        detection = detection_by_sheet.get(id(raw_table))
        mapping = (
            map_fields_from_source_mapping(
                raw_table.rows,
                schema_type,
                source_field_mapping,
                header_row_index=header_row_index,
                sub_header_row_index=sub_header_row_index,
            )
            if source_field_mapping
            else map_fields(
                raw_table.rows,
                schema_type,
                header_row_index=header_row_index,
                sub_header_row_index=sub_header_row_index,
            )
        )
        if source_field_mapping and not mapping.found:
            mapping = map_fields(
                raw_table.rows,
                schema_type,
                header_row_index=header_row_index,
                sub_header_row_index=sub_header_row_index,
            )
        if detection and detection.detected_type != detected_type and not mapping.found:
            sheet_reports.append(
                {
                    "sheet_name": raw_table.sheet_name,
                    "detected_type": detection.detected_type,
                    "confidence": detection.confidence,
                    "status": "skipped",
                    "reason": "sheet 类型与主导入类型不一致",
                }
            )
            continue

        if not mapping.found:
            warnings.append(
                {
                    "row_index": None,
                    "level": "warning",
                    "message": "无法识别表头",
                    "raw_value": raw_table.sheet_name,
                    "field": "header",
                    "source_column": "",
                }
            )
            sheet_reports.append(
                {
                    "sheet_name": raw_table.sheet_name,
                    "detected_type": detection.detected_type if detection else detected_type,
                    "confidence": detection.confidence if detection else 0,
                    "status": "skipped",
                    "reason": "无法识别表头",
                }
            )
            continue

        header_signature = header_signature or header_signature_for_result(raw_table.rows, mapping)
        for header in source_headers_for_result(raw_table.rows, mapping):
            if header and header not in resolved_source_headers:
                resolved_source_headers.append(header)
        resolved_header_row = resolved_header_row or (mapping.header_row_index + 1)
        if mapping.sub_header_row_index >= 0:
            resolved_sub_header_row = resolved_sub_header_row or (mapping.sub_header_row_index + 1)
        effective_data_start_index = (
            data_start_row_index
            if data_start_row_index is not None
            else max(mapping.header_row_index, mapping.sub_header_row_index) + 1
        )
        resolved_data_start_row = resolved_data_start_row or (effective_data_start_index + 1)
        for target_field, source_field in mapping.field_mapping.items():
            field_mapping.setdefault(target_field, source_field)
        for source_field, target_field in field_mapping_by_source(mapping).items():
            source_mapping.setdefault(source_field, target_field)
        for header in mapping.unmapped_headers:
            clean_header = str(header or "").strip()
            if (
                not clean_header
                or clean_header in unmapped_headers_seen
                or is_sensitive_dataset_display_field(clean_header)
            ):
                continue
            unmapped_headers_seen.add(clean_header)

        clean_result = clean_table_rows(
            raw_rows=raw_table.rows,
            header_row_index=mapping.header_row_index,
            column_indexes=mapping.column_indexes,
            unmapped_columns=mapping.unmapped_columns,
            standard_fields=standard_fields_for(schema_type),
            table_type=schema_type,
            source_file=file_name,
            defaults=_sheet_defaults(
                defaults=defaults,
                sheet_name=raw_table.sheet_name,
                table_type=detected_type,
            ),
            required_fields=rules["required_fields"],
            required_any_fields=rules["required_any_fields"],
            required_any_groups=rules["required_any_groups"],
            sub_header_row_index=mapping.sub_header_row_index,
            data_start_row_index=effective_data_start_index,
        )
        cleaned_rows.extend(clean_result.rows)
        valid_rows.extend(clean_result.valid_rows)
        warnings.extend(clean_result.warnings)
        total_rows += clean_result.total_rows
        warning_rows += clean_result.warning_rows
        duplicate_rows += clean_result.duplicate_rows
        sheet_reports.append(
            {
                "sheet_name": raw_table.sheet_name,
                "detected_type": detection.detected_type if detection else detected_type,
                "processed_as": detected_type,
                "confidence": detection.confidence if detection else 0.99,
                "status": "processed",
                "header_row": mapping.header_row_index + 1,
                "sub_header_row": (
                    mapping.sub_header_row_index + 1
                    if mapping.sub_header_row_index >= 0
                    else None
                ),
                "data_start_row": effective_data_start_index + 1,
                "field_mapping": mapping.field_mapping,
                "total_rows": clean_result.total_rows,
                "valid_rows": len(clean_result.valid_rows),
                "warning_rows": clean_result.warning_rows,
            }
        )

    if unmapped_headers_seen:
        unmapped_count = len(unmapped_headers_seen)
        warnings.append(
            {
                "row_index": None,
                "level": "warning",
                "message": f"有 {unmapped_count} 个原表字段未映射，已作为原表字段保留。",
                "raw_value": "",
                "field": "unmapped_fields_preserved",
                "source_column": "",
            }
        )

    return {
        "cleaned_rows": cleaned_rows,
        "valid_rows": valid_rows,
        "warnings": warnings,
        "field_mapping": field_mapping,
        "field_mapping_by_source": source_mapping,
        "sheet_reports": sheet_reports,
        "total_rows": total_rows,
        "warning_rows": warning_rows,
        "duplicate_rows": duplicate_rows,
        "header_signature": header_signature,
        "header_row": resolved_header_row,
        "sub_header_row": resolved_sub_header_row,
        "data_start_row": resolved_data_start_row,
        "source_headers": resolved_source_headers,
    }


def _build_sheet_mapping_infos(
    raw_tables: list[RawTable],
    detected_type: str,
    *,
    header_row: int | None = None,
    sub_header_row: int | None = None,
) -> list[dict[str, Any]]:
    infos: list[dict[str, Any]] = []
    if detected_type == "unknown":
        return infos
    for raw_table in raw_tables:
        mapping = map_fields(
            raw_table.rows,
            detected_type,
            header_row_index=_row_number_to_index(header_row),
            sub_header_row_index=_row_number_to_index(sub_header_row),
        )
        if not mapping.found:
            continue
        infos.append(
            {
                "sheet_name": raw_table.sheet_name,
                "field_mapping": mapping.field_mapping,
                "field_mapping_by_source": field_mapping_by_source(mapping),
                "source_headers": source_headers_for_result(raw_table.rows, mapping),
                "header_signature": header_signature_for_result(raw_table.rows, mapping),
            }
        )
    return infos


def _merge_source_headers(infos: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for info in infos:
        for header in info.get("source_headers") or []:
            if header and header not in result:
                result.append(header)
    return result


def _merge_source_mapping(infos: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for info in infos:
        for source, target in (info.get("field_mapping_by_source") or {}).items():
            result.setdefault(source, target)
    return result


def _target_mapping_from_source(source_mapping: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source, target in source_mapping.items():
        if target:
            result.setdefault(target, source)
    return result


def _sanitize_source_field_mapping(
    source_mapping: dict[str, str] | None,
    table_type: str,
) -> dict[str, str] | None:
    if not source_mapping:
        return None
    allowed_fields = set(editable_standard_fields_for(table_type))
    return {
        str(source): str(target)
        for source, target in source_mapping.items()
        if source and (target in allowed_fields or target == "__preserve__")
    }


def _field_schema_type(table_type: str) -> str:
    return table_type


def _validation_rules(table_type: str, data_granularity: str) -> dict[str, Any]:
    registry_type = get_import_type(table_type)
    base_rules = {
        "required_fields": list(registry_type.get("required_fields") or []),
        "required_any_fields": [],
        "required_any_groups": [
            list(group) for group in registry_type.get("at_least_one_groups") or []
        ],
        "optional_fields": list(registry_type.get("optional_fields") or []),
    }
    if table_type == "review_candidate_list":
        return base_rules
    if table_type == "job_table":
        return {
            "required_fields": ["year", "province", "exam_type", "job_name", "job_code"],
            "required_any_fields": [],
            "required_any_groups": [],
            "optional_fields": base_rules["optional_fields"],
        }
    if table_type == "score_line_table":
        return {
            "required_fields": ["year", "province", "exam_type", "min_score"],
            "required_any_fields": [],
            "required_any_groups": [],
            "optional_fields": [
                "job_code",
                "unit_name",
                "recruit_count",
                "interview_count",
                "major_category",
            ],
        }
    if table_type == "candidate_score_table":
        if data_granularity in {"candidate_level", "candidate_list_level"}:
            return {
                "required_fields": [
                    "year",
                    "province",
                    "exam_type",
                    "candidate_no",
                    "job_code",
                ],
                "required_any_fields": SCORE_FIELDS,
                "required_any_groups": [],
                "optional_fields": ["unit_name", "job_name", "rank", "region", "source_sheet"],
            }
        if data_granularity == "job_level":
            return {
                "required_fields": ["year", "province", "exam_type", "job_code"],
                "required_any_fields": ["total_score", "written_score"],
                "required_any_groups": [],
                "optional_fields": ["unit_name", "job_name", "rank", "region", "source_sheet"],
            }
        return {
            "required_fields": ["year", "province", "exam_type"],
            "required_any_fields": SCORE_FIELDS,
            "required_any_groups": [],
            "optional_fields": ["region", "section_title", "source_sheet", "unit_name", "job_code", "job_name"],
        }
    if table_type == "signup_table":
        return {
            "required_fields": ["year", "province", "exam_type", "job_code"],
            "required_any_fields": [],
            "required_any_groups": [],
            "optional_fields": [
                "job_name",
                "unit_name",
                "recruit_count",
                "signup_count",
                "approved_count",
                "paid_count",
                "competition_ratio",
            ],
        }
    if table_type == "major_catalog":
        return {
            "required_fields": ["year", "province", "major_name"],
            "required_any_fields": [],
            "required_any_groups": [],
            "optional_fields": ["major_code", "major_category", "degree_level"],
        }
    return base_rules


def _infer_data_granularity(
    *,
    file_name: str,
    raw_tables: list[RawTable],
    table_type: str,
    source_mapping: dict[str, str],
) -> str:
    if table_type != "candidate_score_table":
        return "unknown"
    context = _collect_import_context(file_name, raw_tables)
    normalized_context = normalize_header(context)
    mapped_fields = set(source_mapping.values())
    has_score = bool(mapped_fields & set(SCORE_FIELDS))
    if "candidate_no" in mapped_fields and has_score:
        return "candidate_level"
    if {"unit_name", "job_code"}.issubset(mapped_fields) and has_score:
        return "job_level"
    if any(keyword in normalized_context for keyword in ["拟进入体检考察", "人员名单", "准考证号", "体检考察名单"]):
        return "candidate_list_level"
    if any(keyword in normalized_context for keyword in ["上岸分数", "最低分", "分数汇总", "成绩汇总"]):
        return "summary_level"
    if has_score:
        return "region_level"
    return "unknown"


def _merge_type_candidates(
    detections: list[tuple[RawTable, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for _, detection in detections:
        for candidate in detection.candidates or []:
            type_key = str(candidate.get("type_key") or "")
            if not type_key:
                continue
            existing = merged.get(type_key)
            if existing is None or float(candidate.get("score") or 0) > float(existing.get("score") or 0):
                merged[type_key] = {
                    "type_key": type_key,
                    "type_label": candidate.get("type_label") or TYPE_LABELS.get(type_key, type_key),
                    "score": float(candidate.get("score") or 0),
                    "matched_keywords": list(candidate.get("matched_keywords") or []),
                    "matched_features": list(candidate.get("matched_features") or []),
                }
    return sorted(
        merged.values(),
        key=lambda item: float(item.get("score") or 0),
        reverse=True,
    )


def _type_candidate_score(candidates: list[dict[str, Any]], type_key: str) -> float:
    for candidate in candidates:
        if candidate.get("type_key") == type_key:
            return round(float(candidate.get("score") or 0), 2)
    return 0.0


def _build_type_conflict_reasons(
    *,
    detected_type: str,
    best_detection: Any,
    file_detection: Any,
    type_candidates: list[dict[str, Any]],
    source_mapping: dict[str, str],
    source_headers: list[str],
    type_confirmed: bool,
) -> list[str]:
    reasons: list[str] = []
    if not type_confirmed and len(type_candidates) >= 2:
        first_score = float(type_candidates[0].get("score") or 0)
        second_score = float(type_candidates[1].get("score") or 0)
        if second_score >= 0.40 and first_score - second_score < TYPE_SCORE_GAP_THRESHOLD:
            reasons.append("前两个候选类型评分接近，请手动确认数据类型")
    if (
        not type_confirmed
        and file_detection.detected_type != "unknown"
        and float(file_detection.confidence or 0) >= 0.50
        and best_detection.detected_type != "unknown"
        and file_detection.detected_type != best_detection.detected_type
    ):
        reasons.append(
            f"文件名更像{TYPE_LABELS.get(file_detection.detected_type, file_detection.detected_type)}，"
            f"但表头更像{TYPE_LABELS.get(best_detection.detected_type, best_detection.detected_type)}"
        )
    if detected_type == "major_catalog":
        normalized_headers = [
            normalize_header(header)
            for header in [*source_headers, *source_mapping.keys()]
            if normalize_header(header)
        ]
        job_feature_count = sum(
            1
            for keywords in JOB_STRUCTURAL_GROUPS.values()
            if any(
                normalize_header(keyword) in header
                for keyword in keywords
                for header in normalized_headers
            )
        )
        if job_feature_count >= 2:
            reasons.append("该文件更像职位表，不建议按专业目录表入库")
    return list(dict.fromkeys(reasons))


def _build_blocking_reasons(task: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    detected_type = str(task.get("detected_type") or "")
    if detected_type == "unknown":
        reasons.append("无法识别可入库的数据类型")
    elif not is_importable_type(detected_type):
        reasons.append("当前数据类型暂不支持入库")
    if not task.get("province"):
        reasons.append("缺少省份，且无法从文件名自动识别")
    if task.get("year") is None:
        reasons.append("缺少年份")
    if detected_type != "major_catalog" and not task.get("exam_type"):
        reasons.append("缺少考试类型")
    if int(task.get("valid_rows") or 0) <= 0:
        reasons.append("没有有效记录")
    if task.get("requires_type_confirmation"):
        reasons.extend(task.get("type_conflict_reasons") or [])
        reasons.append("系统不确定该文件类型，请手动确认数据类型和字段映射")
    mapping = task.get("field_mapping") or {}
    mapped_fields = {field for field, source in mapping.items() if source}
    if len(mapped_fields) < 2 and detected_type not in {"unknown"}:
        reasons.append("表头字段匹配数量过少，请手动调整字段映射")
    if detected_type == "job_table" and not {"job_code", "job_name"}.issubset(mapped_fields):
        reasons.append("岗位表必须同时映射职位代码和岗位名称")
    if detected_type == "score_line_table" and "min_score" not in mapped_fields:
        reasons.append("进面分数线表必须映射最低进面分字段")
    return list(dict.fromkeys(reasons))


def _build_field_status(task: dict[str, Any]) -> list[dict[str, Any]]:
    table_type = _field_schema_type(str(task.get("detected_type") or ""))
    mapping = task.get("field_mapping") or {}
    required_fields = set(task.get("required_fields") or [])
    required_any_fields = list(task.get("required_any_fields") or [])
    required_any_groups = [
        list(group) for group in task.get("required_any_groups") or []
    ]
    protected_values = {
        "year": task.get("year"),
        "province": task.get("province"),
        "exam_type": task.get("exam_type"),
    }
    fields = list(dict.fromkeys([
        *task.get("required_fields", []),
        *required_any_fields,
        *(field for group in required_any_groups for field in group),
        *task.get("optional_fields", []),
    ]))
    if table_type == "candidate_score_table":
        fields = list(dict.fromkeys([
            "candidate_no",
            "job_code",
            "unit_name",
            "job_name",
            "written_score",
            "interview_score",
            "total_score",
            "min_score",
            "year",
            "province",
            "exam_type",
            *fields,
        ]))

    any_group_satisfied = any(
        bool(mapping.get(field)) for field in required_any_fields
    )
    statuses: list[dict[str, Any]] = []
    for field in fields:
        source = str(mapping.get(field) or "").strip()
        if field in protected_values and protected_values[field] not in {None, ""}:
            source = "导入参数或文件名自动识别"
        mapped = bool(source)
        if field in required_fields:
            requirement = "required"
            satisfied = mapped
        elif field in required_any_fields:
            requirement = "required_any"
            satisfied = any_group_satisfied
        elif any(field in group for group in required_any_groups):
            requirement = "required_any"
            satisfied = all(
                any(
                    bool(mapping.get(group_field))
                    or protected_values.get(group_field) not in {None, ""}
                    for group_field in group
                )
                for group in required_any_groups
                if field in group
            )
        else:
            requirement = "optional"
            satisfied = True
        note = ""
        if field == "min_score" and table_type == "candidate_score_table":
            note = "最低进面分请使用进面分数线表类型导入"
        statuses.append(
            {
                "field": field,
                "source": source,
                "mapped": mapped,
                "satisfied": satisfied,
                "requirement": requirement,
                "note": note,
            }
        )
    return statuses


def _build_warning_summary(warnings: list[dict[str, Any]], duplicate_rows: int) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    if duplicate_rows:
        summary.append(
            {
                "level": "warning",
                "field": "duplicate_row",
                "count": duplicate_rows,
                "message": f"检测到 {duplicate_rows} 条重复记录，确认入库时将自动跳过。",
            }
        )
    visible_warning_count = 0
    for warning in warnings:
        if warning.get("field") == "duplicate_row":
            continue
        if visible_warning_count >= 20:
            break
        summary.append(warning)
        visible_warning_count += 1
    remaining = len([warning for warning in warnings if warning.get("field") != "duplicate_row"]) - visible_warning_count
    if remaining > 0:
        summary.append(
            {
                "level": "warning",
                "field": "warning_overflow",
                "count": remaining,
                "message": f"另有 {remaining} 条 warning 已收起，请在明细中查看。",
            }
        )
    return summary


def _build_sheet_summary(sheet_reports: list[dict[str, Any]]) -> str:
    processed_count = sum(1 for report in sheet_reports if report.get("status") == "processed")
    if processed_count <= 1:
        return ""
    return f"已识别 {processed_count} 个工作表，合并生成预览。"


def _sheet_defaults(
    *,
    defaults: dict[str, Any],
    sheet_name: str,
    table_type: str,
) -> dict[str, Any]:
    sheet_defaults = dict(defaults)
    sheet_defaults["source_sheet"] = sheet_name
    if table_type in {"candidate_score_table", "review_candidate_list"}:
        sheet_defaults["region"] = sheet_defaults.get("region") or sheet_name
    return sheet_defaults


def _validate_upload(file_name: str, content: bytes) -> None:
    suffix = Path(file_name or "").suffix.lower()
    if suffix not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError("仅支持 .xlsx、.xls、.csv 文件")
    if not content:
        raise ValueError("上传文件不能为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("上传文件超过 V1 限制 20MB")


def _infer_import_defaults(
    *,
    file_name: str,
    raw_tables: list[RawTable],
    table_type: str,
    province: str | None,
    exam_type: str | None,
    year: int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    text = _collect_import_context(file_name, raw_tables)
    warnings: list[dict[str, Any]] = []
    inferred_year = _infer_score_line_year(file_name, raw_tables) if table_type == "score_line_table" else _infer_year(text)
    selected_year = year or inferred_year
    if table_type == "score_line_table" and inferred_year is not None:
        selected_year = inferred_year
        if year is not None and year != inferred_year:
            warnings.append(
                {
                    "row_index": None,
                    "level": "warning",
                    "message": f"检测到文件年份为 {inferred_year}，但填写年份为 {year}，已优先使用文件年份 {inferred_year}。",
                    "raw_value": year,
                    "field": "year",
                    "source_column": "",
                }
            )
    return (
        {
            "province": province or _infer_province(text),
            "exam_type": exam_type or _infer_exam_type(text),
            "year": selected_year,
        },
        warnings,
    )


def _collect_import_context(file_name: str, raw_tables: list[RawTable]) -> str:
    parts: list[str] = [file_name]
    for raw_table in raw_tables[:3]:
        parts.append(raw_table.sheet_name)
        for row in raw_table.rows[:20]:
            for value in row[:20]:
                cleaned = clean_value(value)
                if cleaned is not None:
                    parts.append(str(cleaned))
    return " ".join(parts)


def _infer_province(text: str) -> str | None:
    detected = detect_province_in_text(text)
    if detected.get("slug"):
        return str(detected["slug"])
    for keyword, province in PROVINCE_HINTS.items():
        if keyword in text:
            return province
    return None


def _infer_exam_type(text: str) -> str | None:
    if any(keyword in text for keyword in ["公务员", "市考", "省考", "国考"]):
        return "公务员"
    if "事业单位" in text:
        return "事业单位"
    return None


def _infer_score_line_year(file_name: str, raw_tables: list[RawTable]) -> int | None:
    section_year = _infer_year(_collect_section_title_context(raw_tables))
    if section_year is not None:
        return section_year
    return _infer_year(file_name)


def _collect_section_title_context(raw_tables: list[RawTable]) -> str:
    parts: list[str] = []
    for raw_table in raw_tables[:3]:
        for row in raw_table.rows[:80]:
            values = [clean_value(value) for value in row if clean_value(value) is not None]
            if not values or len(values) > 2:
                continue
            title = " ".join(str(value) for value in values)
            if "进面分" in title or "分数线" in title:
                parts.append(title)
    return " ".join(parts)


def _infer_year(text: str) -> int | None:
    full_year = re.search(r"(?<!\d)(20\d{2})(?!\d)", text)
    if full_year:
        return int(full_year.group(1))
    short_year = re.search(r"(?<!\d)(\d{2})年", text)
    if not short_year:
        return None
    year_value = int(short_year.group(1))
    if year_value < 50:
        return 2000 + year_value
    return 1900 + year_value


def _task_default(task: dict[str, Any], field: str) -> str:
    direct_value = task.get(field)
    if direct_value not in {None, ""}:
        return str(direct_value)
    rows = [row for row in (task.get("preview_rows") or []) if isinstance(row, dict)]
    if rows:
        return str(rows[0].get(field) or "")
    return ""


def _task_default_int(task: dict[str, Any], field: str) -> int | None:
    value = _task_default(task, field)
    if value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def _row_number_to_index(value: Any) -> int | None:
    parsed = _optional_positive_int(value)
    return parsed - 1 if parsed is not None else None


def _default_source_keyword(file_name: str) -> str:
    stem = Path(file_name or "").stem
    parts = []
    province = detect_province_in_text(stem)
    province_keyword = str(province.get("province") or province.get("slug") or "").strip()
    if province_keyword:
        parts.append(province_keyword)
    for keyword in ["职位", "岗位", "计划", "资格复审", "资格审查", "成绩", "分数", "报名", "竞争比", "专业目录"]:
        if keyword in stem:
            parts.append(keyword)
    return ",".join(parts) or stem[:40]
