"""Value normalization and row-level cleaning for imported exam tables."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


NULL_MARKERS = {
    "",
    "-",
    "--",
    "/",
    "\\",
    "nan",
    "none",
    "null",
    "nat",
    "na",
    "<na>",
    "暂无",
    "无",
    "空",
}
SOFT_NULL_MARKERS = {"缺考", "弃考", "未参加"}

INTEGER_FIELDS = {
    "recruit_count",
    "signup_count",
    "approved_count",
    "paid_count",
    "rank",
    "interview_count",
}
FLOAT_FIELDS = {
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
}
JOB_LIKE_TABLES = {
    "job_table",
    "score_line_table",
    "signup_table",
    "candidate_score_table",
    "review_candidate_list",
}
SCORE_LINE_HEADER_MARKERS = [
    "用人单位",
    "职位序号",
    "职位代码",
    "岗位代码",
    "招考人数",
    "招录人数",
    "专业类别",
    "进面分数线",
    "最低进面分",
    "最低分",
    "进面分",
]
CANDIDATE_SCORE_HEADER_MARKERS = [
    "准考证号",
    "准考证号码",
    "考号",
    "考生编号",
    "报名序号",
    "单位代码",
    "单位名称",
    "代码",
    "职位代码",
    "职位序号",
    "岗位代码",
    "职位名称",
    "招录人数",
    "招考人数",
    "招收人数",
    "行测成绩",
    "成绩",
    "申论成绩",
    "专业成绩",
    "笔试成绩",
    "笔试分数",
    "笔试总分",
    "面试成绩",
    "面试分数",
    "总分",
    "总成绩",
    "排名",
    "职位排名",
    "综合排名",
    "状态",
]


@dataclass(slots=True)
class CleanResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    valid_rows: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    total_rows: int = 0
    warning_rows: int = 0
    duplicate_rows: int = 0


def _combine_job_major_requirements(row: dict[str, Any]) -> None:
    level_fields = [
        ("major_requirement_junior_college", "专科"),
        ("major_requirement_bachelor", "本科"),
        ("major_requirement_graduate", "研究生"),
    ]
    parts = []
    existing = str(row.get("major_requirement") or "").strip()
    if existing:
        parts.append(existing)
    for field_name, label in level_fields:
        value = str(row.pop(field_name, None) or "").strip()
        if value:
            parts.append(f"{label}：{value}")
    if parts:
        row["major_requirement"] = "；".join(dict.fromkeys(parts))


def _apply_review_subject_scores(row: dict[str, Any]) -> None:
    """Derive standard subject scores only when the source subject name is explicit."""
    subject_targets = {
        "xingce_score": ("行测", "行政职业能力测验", "职业能力测验"),
        "shenlun_score": ("申论",),
        "professional_score": ("专业科目", "专业能力", "公安专业", "专业知识"),
    }
    for index in range(1, 4):
        subject_name = str(row.get(f"subject{index}_name") or "").strip()
        subject_score = row.get(f"subject{index}_score")
        if not subject_name or subject_score is None:
            continue
        normalized_name = normalize_header(subject_name)
        for target_field, markers in subject_targets.items():
            if row.get(target_field) is not None:
                continue
            if any(normalize_header(marker) in normalized_name for marker in markers):
                row[target_field] = subject_score
                break


def _build_extra_fields(
    raw_row: list[Any],
    unmapped_columns: dict[str, int],
) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    for source_header, column_index in (unmapped_columns or {}).items():
        raw_value = raw_row[column_index] if column_index < len(raw_row) else None
        value = clean_value(raw_value)
        if value is not None:
            extras[str(source_header)] = value
    return extras


def clean_table_rows(
    *,
    raw_rows: list[list[Any]],
    header_row_index: int,
    column_indexes: dict[str, int],
    unmapped_columns: dict[str, int] | None = None,
    standard_fields: list[str],
    table_type: str,
    source_file: str,
    defaults: dict[str, Any] | None = None,
    required_fields: list[str] | None = None,
    required_any_fields: list[str] | None = None,
    required_any_groups: list[list[str]] | None = None,
    sub_header_row_index: int | None = None,
    data_start_row_index: int | None = None,
) -> CleanResult:
    """Normalize source rows into standard fields and collect warnings."""
    defaults = defaults or {}
    result = CleanResult()
    seen_keys: set[str] = set()
    warning_row_indexes: set[int] = set()
    current_section_title = ""
    illegal_year_warning_added = False
    mismatched_year_warning_added = False
    if header_row_index > 0:
        current_section_title = _section_title_from_row(
            raw_rows[header_row_index - 1],
            table_type=table_type,
        )

    inferred_start = max(header_row_index, sub_header_row_index or -1) + 1
    first_data_row = (
        max(inferred_start, data_start_row_index)
        if data_start_row_index is not None
        else inferred_start
    )
    for raw_index in range(first_data_row, len(raw_rows)):
        raw_row = raw_rows[raw_index]
        if not _row_has_data(raw_row):
            continue

        section_title = _section_title_from_row(raw_row, table_type=table_type)
        if section_title:
            current_section_title = section_title
            continue

        if _is_repeated_header_row(raw_row, table_type=table_type):
            continue

        row_index = raw_index + 1
        result.total_rows += 1
        clean_row: dict[str, Any] = {field: None for field in standard_fields}
        row_had_warning = False

        for field_name, column_index in column_indexes.items():
            if field_name not in clean_row:
                continue
            raw_value = raw_row[column_index] if column_index < len(raw_row) else None
            clean_row[field_name] = clean_value(raw_value)

        if "extra_fields_json" in clean_row:
            clean_row["extra_fields_json"] = json.dumps(
                _build_extra_fields(raw_row, unmapped_columns or {}),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

        if table_type == "job_table":
            _combine_job_major_requirements(clean_row)
        elif table_type == "review_candidate_list":
            _apply_review_subject_scores(clean_row)

        default_year = parse_year(defaults.get("year"))
        raw_year_value = clean_row.get("year")
        if "year" in clean_row:
            clean_row["year"] = None
            parsed_raw_year = parse_int(raw_year_value) if raw_year_value is not None else None
            if raw_year_value is not None and not is_valid_year(parsed_raw_year):
                row_had_warning = True
                if not illegal_year_warning_added:
                    _append_warning(
                        result.warnings,
                        row_index=row_index,
                        message=f"检测到非法年份字段，已使用导入任务年份 {default_year}",
                        raw_value=raw_year_value,
                        field="year",
                    )
                    illegal_year_warning_added = True
            elif (
                raw_year_value is not None
                and default_year is not None
                and parsed_raw_year != default_year
            ):
                row_had_warning = True
                if not mismatched_year_warning_added:
                    _append_warning(
                        result.warnings,
                        row_index=row_index,
                        message=f"检测到表格年份字段与导入任务年份不一致，已使用导入任务年份 {default_year}。",
                        raw_value=raw_year_value,
                        field="year",
                    )
                    mismatched_year_warning_added = True

        _apply_default(clean_row, "year", default_year)
        _apply_default(clean_row, "province", defaults.get("province"))
        _apply_default(clean_row, "region", defaults.get("region"))
        _apply_default(clean_row, "exam_type", defaults.get("exam_type"))
        _apply_default(clean_row, "data_granularity", defaults.get("data_granularity"))
        _apply_default(clean_row, "source_sheet", defaults.get("source_sheet"))
        _apply_default(clean_row, "source_file", source_file)
        _apply_default(clean_row, "section_title", current_section_title)
        if "raw_row_json" in clean_row:
            clean_row["raw_row_json"] = json.dumps(
                [clean_value(value) for value in raw_row],
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

        if "year" in clean_row and clean_row.get("year") is not None:
            parsed_year = parse_year(clean_row.get("year"))
            if parsed_year is not None:
                clean_row["year"] = parsed_year
            else:
                clean_row["year"] = None

        for field_name in INTEGER_FIELDS & set(clean_row):
            raw_value = clean_row.get(field_name)
            if raw_value is None:
                continue
            if table_type in {"candidate_score_table", "review_candidate_list"} and _is_soft_null_marker(raw_value):
                _append_warning(
                    result.warnings,
                    row_index=row_index,
                    message=f"{_field_label(field_name)}为空值或未参加，已保留为空",
                    raw_value=raw_value,
                    field=field_name,
                )
                clean_row[field_name] = None
                continue
            parsed = parse_int(raw_value)
            if parsed is None:
                if table_type != "review_candidate_list":
                    row_had_warning = True
                _append_warning(
                    result.warnings,
                    row_index=row_index,
                    message=f"{_field_label(field_name)}不是有效数字",
                    raw_value=raw_value,
                    field=field_name,
                )
            clean_row[field_name] = parsed

        for field_name in FLOAT_FIELDS & set(clean_row):
            raw_value = clean_row.get(field_name)
            if raw_value is None:
                continue
            if table_type in {"candidate_score_table", "review_candidate_list"} and _is_soft_null_marker(raw_value):
                _append_warning(
                    result.warnings,
                    row_index=row_index,
                    message=f"{_field_label(field_name)}为空值或未参加，已保留为空",
                    raw_value=raw_value,
                    field=field_name,
                )
                clean_row[field_name] = None
                continue
            parsed = parse_float(raw_value)
            if parsed is None:
                if table_type != "review_candidate_list":
                    row_had_warning = True
                _append_warning(
                    result.warnings,
                    row_index=row_index,
                    message=f"{_field_label(field_name)}不是有效数字",
                    raw_value=raw_value,
                    field=field_name,
                )
            clean_row[field_name] = parsed

        if "competition_ratio" in clean_row and clean_row.get("competition_ratio") is not None:
            raw_value = clean_row.get("competition_ratio")
            parsed = parse_competition_ratio(raw_value)
            if parsed is None:
                row_had_warning = True
                _append_warning(
                    result.warnings,
                    row_index=row_index,
                    message="竞争比不是有效数字",
                    raw_value=raw_value,
                    field="competition_ratio",
                )
            clean_row["competition_ratio"] = parsed

        row_had_warning = _validate_required_fields(
            table_type=table_type,
            row=clean_row,
            row_index=row_index,
            warnings=result.warnings,
            required_fields=required_fields,
            required_any_fields=required_any_fields,
            required_any_groups=required_any_groups,
        ) or row_had_warning

        row_key = build_row_key(table_type, clean_row)
        if row_key in seen_keys:
            result.duplicate_rows += 1
            row_had_warning = True
            _append_warning(
                result.warnings,
                row_index=row_index,
                message="重复行，确认入库时将跳过重复记录",
                raw_value=row_key,
                field="duplicate_row",
                source_column="duplicate",
            )
            warning_row_indexes.add(row_index)
            continue
        seen_keys.add(row_key)

        clean_row = {
            field_name: clean_row.get(field_name)
            for field_name in standard_fields
        }
        result.rows.append(clean_row)
        if row_had_warning:
            warning_row_indexes.add(row_index)
        else:
            result.valid_rows.append(clean_row)

    result.warning_rows = len(warning_row_indexes)
    return result


def build_row_key(table_type: str, row: dict[str, Any]) -> str:
    """Build a stable dedupe key for one standardized row."""
    year = clean_value(row.get("year")) or ""
    province = clean_value(row.get("province")) or ""
    exam_type = clean_value(row.get("exam_type")) or ""
    if table_type == "candidate_score_table":
        candidate_no = clean_value(row.get("candidate_no")) or ""
        code = clean_value(row.get("job_code")) or ""
        rank = clean_value(row.get("rank")) or ""
        identity_parts = [str(clean_value(row.get("source_sheet")) or clean_value(row.get("region")) or "")]
        if candidate_no:
            identity_parts.append(str(candidate_no))
        elif clean_value(row.get("candidate_name")):
            identity_parts.append(str(clean_value(row.get("candidate_name"))))
        identity_parts.extend(
            [
                str(clean_value(row.get("unit_code")) or clean_value(row.get("unit_name")) or ""),
                str(code),
                str(rank),
                str(clean_value(row.get("total_score")) or ""),
            ]
        )
        return "|".join(
            [
                table_type,
                str(province),
                str(year),
                *identity_parts,
            ]
        )
    if table_type == "review_candidate_list":
        source_sheet = clean_value(row.get("source_sheet")) or ""
        job_identity = clean_value(row.get("job_code")) or clean_value(row.get("job_name")) or ""
        candidate_no = clean_value(row.get("candidate_no")) or ""
        candidate_name = clean_value(row.get("candidate_name")) or ""
        written_score = clean_value(row.get("written_score")) or ""
        rank = clean_value(row.get("rank")) or ""
        if candidate_no:
            identity = [candidate_no, job_identity, source_sheet]
        elif candidate_name:
            identity = [candidate_name, job_identity, written_score, source_sheet]
        else:
            identity = [job_identity, written_score, rank, source_sheet]
        return "|".join(
            [
                table_type,
                str(province),
                str(year),
                *[str(value) for value in identity],
            ]
        )
    if table_type == "score_line_table":
        code = clean_value(row.get("job_code")) or ""
        if code:
            return "|".join([table_type, str(province), str(year), str(exam_type), str(code)])
        return "|".join(
            [
                table_type,
                str(province),
                str(year),
                str(exam_type),
                str(clean_value(row.get("unit_name")) or ""),
                str(clean_value(row.get("job_name")) or ""),
            ]
        )
    if table_type in JOB_LIKE_TABLES:
        code = clean_value(row.get("job_code")) or ""
        if code:
            return "|".join([table_type, str(province), str(year), str(exam_type), str(code)])
        return "|".join(
            [
                table_type,
                str(province),
                str(year),
                str(exam_type),
                str(clean_value(row.get("unit_name")) or ""),
                str(clean_value(row.get("job_name")) or ""),
            ]
        )
    if table_type == "major_catalog":
        code = clean_value(row.get("major_code")) or ""
        if code:
            return "|".join([table_type, str(province), str(year), str(code)])
        return "|".join(
            [
                table_type,
                str(province),
                str(year),
                str(clean_value(row.get("major_name")) or ""),
                str(clean_value(row.get("degree_level")) or ""),
            ]
        )
    return "|".join(str(row.get(key) or "") for key in sorted(row))


def clean_value(value: Any) -> Any:
    """Normalize whitespace, full-width characters, brackets, and null markers."""
    if value is None:
        return None
    try:
        if value != value:
            return None
    except Exception:
        pass
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\ufeff", "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[\s\u3000]+", " ", text).strip()
    if text.lower() in NULL_MARKERS:
        return None
    return text


def normalize_header(value: Any) -> str:
    """Return a compact header token for matching aliases."""
    text = clean_value(value)
    if text is None:
        return ""
    text = "".join(
        char
        for char in str(text)
        if not unicodedata.category(char).startswith("C")
    )
    text = re.sub(r"[\s\u3000,，。；;：:、/\\\-_()（）【】\[\]“”\"']+", "", text)
    return text.lower()


def parse_int(value: Any) -> int | None:
    number = _extract_number(value)
    if number is None:
        return None
    return int(number)


def parse_year(value: Any) -> int | None:
    parsed = parse_int(value)
    return parsed if is_valid_year(parsed) else None


def is_valid_year(value: Any) -> bool:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return False
    return 1900 <= parsed <= 2100


def parse_float(value: Any) -> float | None:
    number = _extract_number(value)
    if number is None:
        return None
    return float(number)


def parse_competition_ratio(value: Any) -> float | None:
    text = clean_value(value)
    if text is None:
        return None
    normalized = str(text).replace("：", ":").replace("比", ":")
    ratio_match = re.search(r"(-?\d+(?:\.\d+)?)\s*:\s*1(?:\.0+)?", normalized)
    if ratio_match:
        return float(ratio_match.group(1))
    return parse_float(text)


def _extract_number(value: Any) -> float | None:
    text = clean_value(value)
    if text is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(text).replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def _row_has_data(row: list[Any]) -> bool:
    return any(clean_value(value) is not None for value in row)


def _section_title_from_row(row: list[Any], *, table_type: str) -> str:
    if table_type != "score_line_table":
        return ""
    values = [clean_value(value) for value in row if clean_value(value) is not None]
    if not values or len(values) > 2:
        return ""
    title = " ".join(str(value) for value in values)
    normalized = normalize_header(title)
    if "进面分" not in normalized and "分数线" not in normalized:
        return ""
    if any(marker in normalized for marker in ["公务员", "市考", "岗位", "各职位", "各岗位", "上海"]):
        return title
    return ""


def _is_repeated_header_row(row: list[Any], *, table_type: str) -> bool:
    if table_type in {"candidate_score_table", "review_candidate_list"}:
        return _is_marker_header_row(row, CANDIDATE_SCORE_HEADER_MARKERS, min_hits=3)
    if table_type != "score_line_table":
        return False
    if _is_marker_header_row(row, SCORE_LINE_HEADER_MARKERS, min_hits=3):
        return True
    normalized_values = _normalized_row_values(row)
    joined = "".join(normalized_values)
    has_score_header = any(
        normalize_header(marker) in joined
        for marker in ["进面分数线", "最低进面分", "最低分", "进面分"]
    )
    has_job_header = any(
        normalize_header(marker) in joined
        for marker in ["用人单位", "职位序号", "职位代码", "岗位代码"]
    )
    return has_score_header and has_job_header


def _is_marker_header_row(row: list[Any], markers: list[str], *, min_hits: int) -> bool:
    normalized_values = _normalized_row_values(row)
    if not normalized_values:
        return False
    normalized_markers = {normalize_header(marker) for marker in markers}
    return len(normalized_values & normalized_markers) >= min_hits


def _normalized_row_values(row: list[Any]) -> set[str]:
    return {
        normalize_header(value)
        for value in row
        if normalize_header(value)
    }


def _is_soft_null_marker(value: Any) -> bool:
    text = clean_value(value)
    return text in SOFT_NULL_MARKERS


def _apply_default(row: dict[str, Any], field_name: str, value: Any) -> None:
    if field_name not in row or row.get(field_name) is not None:
        return
    cleaned = clean_value(value)
    if cleaned is not None:
        row[field_name] = cleaned


def _validate_required_fields(
    *,
    table_type: str,
    row: dict[str, Any],
    row_index: int,
    warnings: list[dict[str, Any]],
    required_fields: list[str] | None = None,
    required_any_fields: list[str] | None = None,
    required_any_groups: list[list[str]] | None = None,
) -> bool:
    row_had_warning = False
    if (
        required_fields is not None
        or required_any_fields is not None
        or required_any_groups is not None
    ):
        for field_name in required_fields or []:
            if row.get(field_name) is None or row.get(field_name) == "":
                row_had_warning = True
                _append_warning(
                    warnings,
                    row_index=row_index,
                    message=f"缺少{_field_label(field_name)}",
                    field=field_name,
                )
        if required_any_fields and not any(
            row.get(field_name) is not None and row.get(field_name) != ""
            for field_name in required_any_fields
        ):
            row_had_warning = True
            _append_warning(
                warnings,
                row_index=row_index,
                message="缺少必要成绩字段",
                field="required_score",
            )
        for group_index, group_fields in enumerate(required_any_groups or [], start=1):
            if any(
                row.get(field_name) is not None and row.get(field_name) != ""
                for field_name in group_fields
            ):
                continue
            row_had_warning = True
            labels = " / ".join(_field_label(field_name) for field_name in group_fields)
            _append_warning(
                warnings,
                row_index=row_index,
                message=f"至少需要以下字段之一：{labels}",
                field=f"required_group_{group_index}",
            )
        return row_had_warning

    if table_type == "job_table":
        if not row.get("job_name"):
            row_had_warning = True
            _append_warning(
                warnings,
                row_index=row_index,
                message="缺少岗位名称",
                field="job_name",
            )
        if not row.get("job_code"):
            row_had_warning = True
            _append_warning(
                warnings,
                row_index=row_index,
                message="缺少职位代码",
                field="job_code",
            )
    elif table_type == "score_line_table":
        if row.get("min_score") is None:
            row_had_warning = True
            _append_warning(
                warnings,
                row_index=row_index,
                message="缺少最低进面分",
                field="min_score",
            )
    elif table_type == "signup_table":
        if not row.get("job_name"):
            row_had_warning = True
            _append_warning(
                warnings,
                row_index=row_index,
                message="缺少岗位名称",
                field="job_name",
            )
        if not row.get("job_code"):
            row_had_warning = True
            _append_warning(
                warnings,
                row_index=row_index,
                message="缺少职位代码",
                field="job_code",
            )
    elif table_type == "candidate_score_table":
        if not any(row.get(field_name) is not None for field_name in ["total_score", "written_score", "interview_score"]):
            row_had_warning = True
            _append_warning(
                warnings,
                row_index=row_index,
                message="缺少必要成绩字段",
                field="required_score",
            )
    elif table_type == "major_catalog" and not row.get("major_name"):
        row_had_warning = True
        _append_warning(
            warnings,
            row_index=row_index,
            message="缺少专业名称",
            field="major_name",
        )
    return row_had_warning


def _append_warning(
    warnings: list[dict[str, Any]],
    *,
    row_index: int | None,
    message: str,
    raw_value: Any = None,
    field: str = "",
    source_column: str = "",
) -> None:
    warnings.append(
        {
            "row_index": row_index,
            "level": "warning",
            "message": message,
            "raw_value": raw_value,
            "field": field,
            "source_column": source_column,
        }
    )


def _field_label(field_name: str) -> str:
    return {
        "year": "年份",
        "province": "省份",
        "exam_type": "考试类型",
        "recruit_count": "招录人数",
        "signup_count": "报名人数",
        "approved_count": "审核通过人数",
        "paid_count": "缴费人数",
        "rank": "排名",
        "interview_count": "进面人数",
        "min_score": "最低进面分",
        "max_score": "最高分",
        "avg_score": "平均分",
        "xingce_score": "行测成绩",
        "shenlun_score": "申论成绩",
        "professional_score": "专业成绩",
        "written_score": "笔试成绩",
        "interview_score": "面试成绩",
        "total_score": "总成绩",
        "candidate_no": "准考证号",
        "candidate_name": "姓名",
        "unit_name": "单位名称",
        "job_name": "岗位名称",
        "job_code": "职位代码",
        "region": "地区",
        "section_title": "分段标题",
    }.get(field_name, field_name)
