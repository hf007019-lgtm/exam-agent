"""Header detection and source-field to standard-field mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.imports.cleaners import normalize_header


TABLE_STANDARD_FIELDS = {
    "job_table": [
        "year",
        "province",
        "region",
        "exam_type",
        "unit_name",
        "department_name",
        "job_name",
        "job_code",
        "major_requirement",
        "major_requirement_junior_college",
        "major_requirement_bachelor",
        "major_requirement_graduate",
        "degree_requirement",
        "education_requirement",
        "political_requirement",
        "identity_requirement",
        "grassroots_requirement",
        "recruit_count",
        "qualification_requirement",
        "job_description",
        "contact_phone",
        "work_address",
        "remark",
        "source_sheet",
        "source_file",
        "extra_fields_json",
    ],
    "score_line_table": [
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
        "source_sheet",
        "source_file",
        "extra_fields_json",
    ],
    "candidate_score_table": [
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
    "review_candidate_list": [
        "year",
        "province",
        "region",
        "exam_type",
        "job_code",
        "job_name",
        "unit_name",
        "recruit_count",
        "written_score",
        "xingce_score",
        "shenlun_score",
        "professional_score",
        "bonus_score",
        "rank",
        "review_status",
        "total_score",
        "subject1_name",
        "subject1_score",
        "subject2_name",
        "subject2_score",
        "subject3_name",
        "subject3_score",
        "candidate_no",
        "candidate_name",
        "remark",
        "source_file",
        "source_sheet",
        "raw_row_json",
        "extra_fields_json",
    ],
    "signup_table": [
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
        "source_sheet",
        "source_file",
        "extra_fields_json",
    ],
    "major_catalog": [
        "year",
        "province",
        "major_name",
        "major_code",
        "major_category",
        "degree_level",
        "source_sheet",
        "source_file",
        "extra_fields_json",
    ],
}

FIELD_ALIASES = {
    "job_table": {
        "year": ["年份", "年度"],
        "province": ["省份", "省", "地区"],
        "region": ["地区", "地市", "城市", "工作地点", "职位所在地", "考区"],
        "exam_type": ["考试类型", "招考类型"],
        "unit_name": ["招录机关", "招考单位", "用人单位", "单位名称", "招录单位", "招录单位名称", "报考机关"],
        "department_name": ["主管部门", "部门名称", "部门"],
        "job_name": ["职位名称", "岗位名称", "职位", "岗位", "招考职位", "招录职位", "考录职位"],
        "job_code": ["职位代码", "岗位代码", "职位编码", "岗位编码", "职位编号", "岗位编号", "代码"],
        "major_requirement": ["专业", "专业要求", "所学专业", "专业类别", "专业名称", "专业限制"],
        "major_requirement_junior_college": ["专业专科", "专业_专科", "专科专业", "专科"],
        "major_requirement_bachelor": ["专业本科", "专业_本科", "本科专业", "本科"],
        "major_requirement_graduate": ["专业研究生", "专业_研究生", "研究生专业", "研究生"],
        "degree_requirement": ["学位", "学位要求"],
        "education_requirement": ["学历", "学历要求", "最低学历", "文化程度", "学历层次"],
        "political_requirement": ["政治面貌", "政治面貌要求"],
        "identity_requirement": ["应届生", "应届毕业生", "招考对象", "招录对象", "身份要求", "现有身份要求", "职位招考对象"],
        "grassroots_requirement": ["基层工作经历", "基层经历", "基层工作经历要求"],
        "recruit_count": ["招考人数", "招录人数", "考录人数", "招聘人数", "计划人数", "计划招录人数", "录用人数", "人数", "名额"],
        "qualification_requirement": ["资格条件", "报考资格条件", "资格要求"],
        "job_description": ["职位简介", "岗位简介", "职位描述", "岗位描述"],
        "contact_phone": ["咨询电话", "单位咨询电话", "联系电话"],
        "work_address": ["单位地址", "工作地址", "办公地址"],
        "remark": ["备注", "其他", "其他要求", "其他条件"],
    },
    "score_line_table": {
        "year": ["年份", "年度"],
        "province": ["省份", "省"],
        "region": ["地区", "地市", "城市", "考区"],
        "exam_type": ["考试类型", "招考类型"],
        "unit_name": ["招录机关", "招考单位", "用人单位", "单位名称", "招录单位", "招录单位名称", "报考机关"],
        "job_name": ["职位名称", "岗位名称", "职位", "岗位", "报考职位名称"],
        "job_code": ["职位代码", "职位序号", "岗位代码", "报考职位代码", "报考岗位代码", "代码"],
        "recruit_count": ["招考人数", "招录人数", "招聘人数", "计划人数", "计划招录人数"],
        "interview_count": ["进面人数", "进入面试人数", "面试人数", "入围人数"],
        "major_category": ["专业类别", "专业大类", "专业"],
        "min_score": ["最低进面分", "进面分数线", "进面分数", "进面分", "最低分", "最低笔试成绩", "最低进面分数"],
        "max_score": ["最高分", "最高进面分", "最高笔试成绩"],
        "avg_score": ["平均分", "平均成绩", "平均进面分"],
    },
    "candidate_score_table": {
        "year": ["年份", "年度"],
        "province": ["省份", "省"],
        "region": ["地区", "地市", "城市", "考区"],
        "exam_type": ["考试类型", "招考类型"],
        "candidate_no": ["准考证号", "准考证号码", "准考证", "考号", "考生编号", "报名序号"],
        "candidate_name": ["姓名", "考生姓名", "人员姓名"],
        "unit_code": ["单位代码", "招录机关代码", "部门代码", "机构代码"],
        "unit_name": ["单位名称", "招录机关", "招考单位", "用人单位", "招录单位"],
        "job_code": ["职位代码", "职位序号", "岗位代码", "报考职位代码", "报考岗位代码"],
        "job_name": ["职位名称", "岗位名称", "报考职位名称"],
        "recruit_count": ["招录人数", "招考人数", "招收人数", "招聘人数", "计划人数", "计划招录人数"],
        "xingce_score": ["行测成绩", "行测"],
        "shenlun_score": ["申论成绩", "申论"],
        "professional_score": ["专业成绩"],
        "written_score": ["笔试成绩", "笔试分数", "笔试总分", "笔试总成绩"],
        "interview_score": ["面试成绩", "面试分数"],
        "total_score": ["总分", "总成绩", "综合成绩"],
        "rank": ["排名", "职位排名", "综合排名"],
        "status": ["状态"],
        "group_name": ["组别", "分组"],
        "remark": ["备注", "说明"],
    },
    "signup_table": {
        "year": ["年份", "年度"],
        "province": ["省份", "省"],
        "region": ["地区", "地市", "城市", "考区"],
        "exam_type": ["考试类型", "招考类型"],
        "unit_name": ["招录机关", "招考单位", "用人单位", "单位名称", "招录单位", "招录单位名称", "报考机关"],
        "job_name": ["职位名称", "岗位名称", "职位", "岗位", "报考职位名称"],
        "job_code": ["职位代码", "岗位代码", "报考职位代码", "报考岗位代码", "代码"],
        "recruit_count": ["招录人数", "招考人数", "招聘人数", "计划人数", "计划招录人数"],
        "signup_count": ["报名人数", "报考人数", "报名总人数"],
        "approved_count": ["审核通过人数", "审核人数", "过审人数"],
        "paid_count": ["缴费人数", "缴费确认人数", "确认人数"],
        "competition_ratio": ["竞争比", "报录比", "竞争比例"],
    },
    "major_catalog": {
        "year": ["年份", "年度"],
        "province": ["省份", "省"],
        "major_name": ["专业名称", "专业", "研究生专业", "本科专业", "专科专业"],
        "major_code": ["专业代码", "代码"],
        "major_category": ["专业类别", "学科门类", "专业大类", "门类"],
        "degree_level": ["学历层次", "层次", "学历", "专业层次"],
    },
}

FIELD_ALIASES["review_candidate_list"] = {
    **FIELD_ALIASES["candidate_score_table"],
    "unit_name": ["招录单位", "招录机关", "招考单位", "用人单位", "单位名称", "报考机关"],
    "job_code": ["职位代码", "岗位代码", "报考职位代码", "报考岗位代码", "职位序号"],
    "job_name": ["职位名称", "岗位名称", "报考职位名称", "报考岗位名称"],
    "candidate_name": ["姓名", "考生姓名", "人员姓名"],
    "rank": ["排名", "名次", "职位排名", "笔试名次", "综合排名"],
    "subject1_name": ["科目1名称", "科目一名称", "第一科目名称"],
    "subject1_score": ["科目1成绩", "科目一成绩", "第一科目成绩"],
    "subject2_name": ["科目2名称", "科目二名称", "第二科目名称"],
    "subject2_score": ["科目2成绩", "科目二成绩", "第二科目成绩"],
    "subject3_name": ["科目3名称", "科目三名称", "第三科目名称"],
    "subject3_score": ["科目3成绩", "科目三成绩", "第三科目成绩"],
    "bonus_score": ["加分", "加分成绩", "政策加分", "笔试加分"],
    "review_status": ["资格标志", "资格状态", "复审状态", "资格复审状态"],
}

REQUIRED_FIELDS = {
    "job_table": {"job_name", "job_code"},
    "score_line_table": {"job_code", "min_score"},
    "candidate_score_table": {"unit_name", "job_code"},
    "review_candidate_list": {"job_code"},
    "signup_table": {"job_code"},
    "major_catalog": {"major_name"},
}

PROTECTED_DEFAULT_FIELDS = {"year", "province", "exam_type"}
BROAD_ALIASES = {"代码", "职位", "岗位", "单位", "部门", "专业", "学历", "学位", "人数", "地区"}
BROAD_NORMALIZED_HEADERS = {normalize_header(alias) for alias in BROAD_ALIASES}


@dataclass(slots=True)
class FieldMappingResult:
    header_row_index: int = -1
    sub_header_row_index: int = -1
    field_mapping: dict[str, str] = field(default_factory=dict)
    column_indexes: dict[str, int] = field(default_factory=dict)
    unmapped_headers: list[str] = field(default_factory=list)
    unmapped_columns: dict[str, int] = field(default_factory=dict)
    confidence: float = 0.0

    @property
    def found(self) -> bool:
        return self.header_row_index >= 0 and bool(self.column_indexes or self.unmapped_columns)


def standard_fields_for(table_type: str) -> list[str]:
    return list(TABLE_STANDARD_FIELDS.get(table_type, []))


def editable_standard_fields_for(table_type: str) -> list[str]:
    return [
        field
        for field in standard_fields_for(table_type)
        if field not in {
            "source_file",
            "source_sheet",
            "raw_row_json",
            "extra_fields_json",
            "data_granularity",
            *PROTECTED_DEFAULT_FIELDS,
        }
    ]


def map_fields(
    rows: list[list[Any]],
    table_type: str,
    *,
    max_scan_rows: int = 30,
    header_row_index: int | None = None,
    sub_header_row_index: int | None = None,
) -> FieldMappingResult:
    """Find the most likely header row and map source headers to standard fields."""
    if table_type not in FIELD_ALIASES:
        return FieldMappingResult()

    alias_entries = _build_alias_entries(table_type)
    best: FieldMappingResult | None = None
    scan_limit = min(max_scan_rows, len(rows))

    row_indexes = (
        [header_row_index]
        if header_row_index is not None and 0 <= header_row_index < len(rows)
        else list(range(scan_limit))
    )
    for row_index in row_indexes:
        sub_header_candidates = (
            [sub_header_row_index]
            if sub_header_row_index is not None
            else [None, row_index + 1 if row_index + 1 < len(rows) else None]
        )
        for active_sub_header in dict.fromkeys(sub_header_candidates):
            field_mapping: dict[str, str] = {}
            column_indexes: dict[str, int] = {}
            unmapped_headers: list[str] = []
            unmapped_columns: dict[str, int] = {}

            for column_index, value in enumerate(rows[row_index]):
                header_candidates = _build_header_candidates(
                    rows,
                    row_index,
                    column_index,
                    value,
                    sub_header_row_index=active_sub_header,
                )
                if not header_candidates:
                    continue
                target_field = ""
                source_header = ""
                for header_candidate in header_candidates:
                    normalized = normalize_header(header_candidate)
                    if not normalized:
                        continue
                    target_field = _match_header(normalized, alias_entries)
                    if target_field in PROTECTED_DEFAULT_FIELDS:
                        target_field = ""
                    if target_field:
                        source_header = str(header_candidate or "").strip()
                        break
                if target_field and target_field not in column_indexes:
                    column_indexes[target_field] = column_index
                    field_mapping[target_field] = source_header
                else:
                    raw_header = header_candidates[0] if header_candidates else ""
                    if raw_header:
                        unique_header = _unique_source_header(raw_header, column_index, unmapped_columns)
                        unmapped_headers.append(unique_header)
                        unmapped_columns[unique_header] = column_index

            mapped_count = len(column_indexes)
            required_count = len(REQUIRED_FIELDS.get(table_type, set()) & set(column_indexes))
            score = mapped_count * 10 + required_count * 20
            if score <= 0 and header_row_index is None:
                continue

            candidate = FieldMappingResult(
                header_row_index=row_index,
                sub_header_row_index=(
                    active_sub_header
                    if active_sub_header is not None and active_sub_header != row_index
                    else -1
                ),
                field_mapping=field_mapping,
                column_indexes=column_indexes,
                unmapped_headers=unmapped_headers,
                unmapped_columns=unmapped_columns,
                confidence=round(min(0.99, (score / 100) + 0.25), 2),
            )
            if best is None or (
                candidate.confidence,
                len(candidate.column_indexes),
            ) > (
                best.confidence,
                len(best.column_indexes),
            ):
                best = candidate

    return best or FieldMappingResult()


def map_fields_from_source_mapping(
    rows: list[list[Any]],
    table_type: str,
    source_to_target: dict[str, str],
    *,
    header_row_index: int | None = None,
    sub_header_row_index: int | None = None,
    max_scan_rows: int = 30,
) -> FieldMappingResult:
    """Build a mapping result from user-edited source-header -> standard-field choices."""
    if table_type not in FIELD_ALIASES:
        return FieldMappingResult()

    base_mapping = map_fields(
        rows,
        table_type,
        max_scan_rows=max_scan_rows,
        header_row_index=header_row_index,
        sub_header_row_index=sub_header_row_index,
    )
    resolved_header_index = (
        header_row_index
        if header_row_index is not None and header_row_index >= 0
        else base_mapping.header_row_index
    )
    if resolved_header_index < 0 or resolved_header_index >= len(rows):
        return FieldMappingResult()

    standard_fields = set(standard_fields_for(table_type)) - PROTECTED_DEFAULT_FIELDS
    normalized_choices = {
        normalize_header(source): target
        for source, target in (source_to_target or {}).items()
        if normalize_header(source)
        and target in standard_fields
        and target not in {"__ignore__", "ignore", ""}
    }
    field_mapping: dict[str, str] = {}
    column_indexes: dict[str, int] = {}
    unmapped_headers: list[str] = []
    unmapped_columns: dict[str, int] = {}

    for column_index, value in enumerate(rows[resolved_header_index]):
        header_candidates = _build_header_candidates(
            rows,
            resolved_header_index,
            column_index,
            value,
            sub_header_row_index=(
                sub_header_row_index
                if sub_header_row_index is not None
                else base_mapping.sub_header_row_index
            ),
        )
        source_header = _best_source_header(header_candidates, normalized_choices)
        target_field = normalized_choices.get(normalize_header(source_header))
        if target_field and target_field not in column_indexes:
            column_indexes[target_field] = column_index
            field_mapping[target_field] = source_header
        else:
            raw_header = str(source_header or value or "").strip()
            if raw_header:
                unique_header = _unique_source_header(raw_header, column_index, unmapped_columns)
                unmapped_headers.append(unique_header)
                unmapped_columns[unique_header] = column_index

    return FieldMappingResult(
        header_row_index=resolved_header_index,
        sub_header_row_index=(
            sub_header_row_index
            if sub_header_row_index is not None
            else base_mapping.sub_header_row_index
        ),
        field_mapping=field_mapping,
        column_indexes=column_indexes,
        unmapped_headers=unmapped_headers,
        unmapped_columns=unmapped_columns,
        confidence=0.99,
    )


def source_headers_for_result(
    rows: list[list[Any]],
    result: FieldMappingResult,
) -> list[str]:
    if result.header_row_index < 0 or result.header_row_index >= len(rows):
        return []
    headers: list[str] = []
    headers.extend(result.field_mapping.values())
    headers.extend(result.unmapped_columns.keys())
    for column_index, value in enumerate(rows[result.header_row_index]):
        candidates = _build_header_candidates(
            rows,
            result.header_row_index,
            column_index,
            value,
            sub_header_row_index=result.sub_header_row_index,
        )
        headers.extend(candidates[:1])
    return _dedupe(headers)


def field_mapping_by_source(result: FieldMappingResult) -> dict[str, str]:
    return {
        source: target
        for target, source in result.field_mapping.items()
        if source
    }


def header_signature_for_result(rows: list[list[Any]], result: FieldMappingResult) -> str:
    if result.header_row_index < 0 or result.header_row_index >= len(rows):
        return ""
    tokens = []
    for column_index, _ in enumerate(rows[result.header_row_index]):
        token = normalize_header(
            _combined_header_text(
                rows,
                result.header_row_index,
                result.sub_header_row_index,
                column_index,
            )
        )
        if token:
            tokens.append(token)
    return "|".join(tokens)


def _build_alias_entries(table_type: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for target_field, aliases in FIELD_ALIASES[table_type].items():
        for alias in aliases:
            normalized = normalize_header(alias)
            if normalized:
                entries.append((normalized, target_field, alias))
    return entries


def _best_source_header(header_candidates: list[str], normalized_choices: dict[str, str]) -> str:
    for candidate in header_candidates:
        if normalize_header(candidate) in normalized_choices:
            return candidate
    return header_candidates[0] if header_candidates else ""


def _match_header(
    normalized_header: str,
    alias_entries: list[tuple[str, str, str]],
) -> str:
    for alias_normalized, target_field, _ in alias_entries:
        if normalized_header == alias_normalized:
            return target_field

    for alias_normalized, target_field, alias_text in alias_entries:
        if alias_text in BROAD_ALIASES:
            continue
        if normalized_header in BROAD_NORMALIZED_HEADERS:
            continue
        if len(alias_normalized) < 2:
            continue
        if alias_normalized in normalized_header or normalized_header in alias_normalized:
            return target_field
    return ""


def _build_header_candidates(
    rows: list[list[Any]],
    row_index: int,
    column_index: int,
    value: Any,
    *,
    sub_header_row_index: int | None = None,
) -> list[str]:
    current = _combined_header_text(
        rows,
        row_index,
        sub_header_row_index,
        column_index,
    )
    if not current:
        return []
    candidates = [current]
    previous_row_value = _cell_text(rows, row_index - 1, column_index)
    previous_cell_value = _cell_text(rows, row_index, column_index - 1)
    if previous_row_value:
        candidates.append(previous_row_value + current)
    if previous_cell_value:
        candidates.append(previous_cell_value + current)
    return _dedupe(candidates)


def _combined_header_text(
    rows: list[list[Any]],
    header_row_index: int,
    sub_header_row_index: int | None,
    column_index: int,
) -> str:
    main = _header_cell_text(rows, header_row_index, column_index, forward_fill=True)
    if sub_header_row_index is None or sub_header_row_index < 0:
        return main
    sub = _header_cell_text(rows, sub_header_row_index, column_index, forward_fill=False)
    if not sub or normalize_header(sub) == normalize_header(main):
        return main or sub
    return f"{main}_{sub}" if main else sub


def _header_cell_text(
    rows: list[list[Any]],
    row_index: int,
    column_index: int,
    *,
    forward_fill: bool,
) -> str:
    value = _cell_text(rows, row_index, column_index)
    if value or not forward_fill:
        return value
    for previous_index in range(column_index - 1, -1, -1):
        previous = _cell_text(rows, row_index, previous_index)
        if previous:
            return previous
    return ""


def _cell_text(rows: list[list[Any]], row_index: int, column_index: int) -> str:
    if row_index < 0 or column_index < 0 or row_index >= len(rows):
        return ""
    row = rows[row_index]
    if column_index >= len(row):
        return ""
    return str(row[column_index] or "").strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalize_header(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result


def _unique_source_header(
    header: str,
    column_index: int,
    existing: dict[str, int],
) -> str:
    clean_header = str(header or "").strip()
    if clean_header not in existing:
        return clean_header
    return f"{clean_header}（第 {column_index + 1} 列）"
