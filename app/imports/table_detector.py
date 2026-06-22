"""Detect structured exam table types from raw spreadsheet rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.imports.cleaners import normalize_header
from app.imports.field_mapper import map_fields
from app.imports.import_type_registry import IMPORT_TYPE_REGISTRY


TYPE_LABELS = {
    type_key: str(config.get("label") or type_key)
    for type_key, config in IMPORT_TYPE_REGISTRY.items()
}

TYPE_KEYWORDS = {
    "review_candidate_list": [
        "进入资格复审",
        "资格复审",
        "资格审查",
        "人员名单",
        "准考证号",
        "报考职位",
        "职位代码",
        "招录单位",
        "资格标志",
        "科目1名称",
        "科目1成绩",
    ],
    "candidate_score_table": [
        "单位代码",
        "单位名称",
        "职位代码",
        "职位序号",
        "职位名称",
        "招录人数",
        "招考人数",
        "招收人数",
        "行测成绩",
        "申论成绩",
        "专业成绩",
        "笔试成绩",
        "笔试分数",
        "笔试总分",
        "面试成绩",
        "面试分数",
        "总分",
        "总成绩",
        "最低分",
        "上岸分数",
        "分数汇总",
        "准考证号",
        "人员名单",
        "拟进入体检考察",
        "排名",
        "职位排名",
        "综合排名",
        "状态",
    ],
    "job_table": [
        "招录机关",
        "招考单位",
        "用人单位",
        "单位名称",
        "职位名称",
        "考录职位",
        "考录人数",
        "岗位名称",
        "职位代码",
        "岗位代码",
        "专业",
        "学历",
        "学位",
        "招考人数",
        "招录人数",
        "政治面貌",
        "基层工作经历",
        "应届生",
        "资格条件",
        "职位简介",
        "机构层级",
    ],
    "score_line_table": [
        "最低进面分",
        "进面分数线",
        "进面分数",
        "进面分",
        "最低分",
        "最高分",
        "岗位名称",
        "职位代码",
        "职位序号",
        "年份",
        "地区",
    ],
    "signup_table": [
        "报名人数",
        "审核通过人数",
        "缴费人数",
        "招录人数",
        "竞争比",
        "报录比",
        "岗位名称",
        "职位代码",
    ],
    "major_catalog": [
        "专业名称",
        "专业代码",
        "专业类别",
        "学科门类",
        "研究生专业",
        "本科专业",
        "专科专业",
    ],
}

FILE_TYPE_HINTS = {
    "job_table": ["职位表", "岗位表", "计划表", "招录计划", "录用计划"],
    "score_line_table": ["进面分", "分数线", "面试名单"],
    "candidate_score_table": ["成绩汇总", "考试成绩", "总成绩"],
    "review_candidate_list": ["资格复审", "资格审查", "复审名单"],
    "signup_table": ["报名人数", "报考人数", "竞争比"],
    "major_catalog": ["专业目录", "专业参考目录", "学科目录"],
}
JOB_STRUCTURAL_GROUPS = {
    "职位代码": ["职位代码", "岗位代码", "职位编码", "职位编号"],
    "岗位名称": ["考录职位", "招考职位", "职位名称", "岗位名称"],
    "招录人数": ["考录人数", "招考人数", "招录人数", "计划人数"],
    "招录单位": ["用人单位", "招录机关", "招考单位", "单位名称"],
    "资格条件": ["资格条件", "职位简介", "机构层级"],
}
MAJOR_CATALOG_STRUCTURAL_GROUPS = {
    "专业名称": ["专业名称"],
    "专业代码": ["专业代码", "门类代码"],
    "专业分类": ["专业类别", "学科门类", "专业大类"],
}

SCORE_LINE_STRONG_KEYWORDS = [
    "进面分数线",
    "最低进面分",
    "最低分",
    "进面分",
]
CANDIDATE_SCORE_STRONG_GROUPS = {
    "written": ["笔试成绩", "笔试分数", "笔试总分"],
    "interview": ["面试成绩", "面试分数"],
    "total": ["总分", "总成绩"],
    "rank": ["排名", "职位排名", "综合排名"],
}
CANDIDATE_SCORE_COMPONENT_KEYWORDS = ["行测成绩", "申论成绩", "专业成绩"]
TYPE_PRIORITY = {
    "review_candidate_list": 6,
    "candidate_score_table": 5,
    "score_line_table": 4,
    "signup_table": 3,
    "job_table": 2,
    "major_catalog": 1,
    "unknown": 0,
}

MULTI_OUTPUT_ORDER = ["job_table", "score_line_table", "signup_table"]
MULTI_OUTPUT_REQUIRED_FIELDS = {
    "job_table": {"job_code", "job_name", "recruit_count"},
    "score_line_table": {"job_code", "min_score"},
    "signup_table": {"job_code"},
}
MULTI_OUTPUT_SIGNAL_FIELDS = {
    "job_table": {"unit_name", "education_requirement", "major_requirement", "job_description"},
    "score_line_table": {"max_score", "min_score", "avg_score", "interview_count"},
    "signup_table": {"signup_count", "approved_count", "paid_count", "competition_ratio"},
}


@dataclass(slots=True)
class DetectionResult:
    detected_type: str = "unknown"
    detected_type_label: str = TYPE_LABELS["unknown"]
    confidence: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)
    matched_features: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)


def recommend_dataset_outputs(rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Recommend independent outputs that share one trustworthy header row.

    This is structural detection only. Callers must still ask the user to
    confirm the Sheet, row boundaries, enabled outputs, and field mappings.
    """
    candidates: list[dict[str, Any]] = []
    for dataset_type in MULTI_OUTPUT_ORDER:
        mapping = map_fields(rows, dataset_type)
        if not mapping.found:
            continue
        mapped_fields = set(mapping.column_indexes)
        required = MULTI_OUTPUT_REQUIRED_FIELDS[dataset_type]
        if not required.issubset(mapped_fields):
            continue
        signal_fields = MULTI_OUTPUT_SIGNAL_FIELDS[dataset_type]
        if not (mapped_fields & signal_fields):
            continue
        if dataset_type == "signup_table" and not (
            mapped_fields & {"signup_count", "approved_count", "paid_count", "competition_ratio"}
        ):
            continue
        candidates.append(
            {
                "dataset_type": dataset_type,
                "dataset_type_label": TYPE_LABELS[dataset_type],
                "target_table": str(IMPORT_TYPE_REGISTRY[dataset_type].get("target_table") or ""),
                "header_row": mapping.header_row_index + 1,
                "sub_header_row": mapping.sub_header_row_index + 1 if mapping.sub_header_row_index >= 0 else None,
                "data_start_row": max(mapping.header_row_index, mapping.sub_header_row_index) + 2,
                "confidence": mapping.confidence,
                "field_mapping": dict(mapping.field_mapping),
            }
        )
    if len(candidates) <= 1:
        return candidates
    header_counts: dict[int, int] = {}
    for candidate in candidates:
        header = int(candidate["header_row"])
        header_counts[header] = header_counts.get(header, 0) + 1
    shared_header = max(header_counts, key=lambda value: (header_counts[value], -value))
    return [candidate for candidate in candidates if candidate["header_row"] == shared_header]


def mixed_output_label(outputs: list[dict[str, Any]]) -> str:
    types = [str(output.get("dataset_type") or "") for output in outputs]
    if types == MULTI_OUTPUT_ORDER:
        return "混合表：岗位 + 报名缴费 + 进面分数"
    labels = [TYPE_LABELS.get(type_key, type_key) for type_key in types if type_key]
    return f"混合表：{' + '.join(labels)}" if len(labels) > 1 else (labels[0] if labels else "未识别")


def detect_table_type(
    rows: list[list[Any]],
    *,
    max_scan_rows: int = 20,
    context: str = "",
) -> DetectionResult:
    """Detect the most likely table type from header and early data rows."""
    table_cells = [
        normalize_header(value)
        for row in rows[:max_scan_rows]
        for value in row[:80]
        if normalize_header(value)
    ]
    normalized_context = normalize_header(context)
    cells = list(table_cells)
    if normalized_context:
        cells.append(normalized_context)
    if not cells:
        return DetectionResult()

    scored_candidates: list[dict[str, Any]] = []
    job_features = _matched_feature_groups(table_cells, JOB_STRUCTURAL_GROUPS)
    major_features = _matched_feature_groups(table_cells, MAJOR_CATALOG_STRUCTURAL_GROUPS)
    for table_type, keywords in TYPE_KEYWORDS.items():
        matches = _matched_keywords(cells, keywords)
        features: list[str] = []
        score = len(matches) * 2
        if table_type == "review_candidate_list" and _matched_keywords(
            cells,
            ["进入资格复审", "资格复审", "资格审查"],
        ):
            score += 10
            features.append("资格复审/资格审查明确标识")
        if table_type == "candidate_score_table":
            score += _candidate_score_bonus(cells)
            if _candidate_score_bonus(cells):
                features.append("成绩、排名或考生级字段组合")
        if table_type == "score_line_table" and _matched_keywords(cells, SCORE_LINE_STRONG_KEYWORDS):
            score += 9
            features.append("最低进面分/分数线明确标识")
            if _matched_keywords(cells, ["职位序号", "职位代码", "岗位代码"]):
                score += 2
        if table_type == "signup_table":
            signup_features = _matched_keywords(
                cells,
                ["报名人数", "审核通过人数", "缴费人数", "竞争比", "报录比"],
            )
            if len(signup_features) >= 2:
                score += 12
                features.append("报名、审核、缴费或竞争比字段组合")
        if table_type == "job_table":
            features.extend(job_features)
            if len(job_features) >= 3:
                score += 14
            elif len(job_features) == 2:
                score += 7
            if _matched_keywords(cells, SCORE_LINE_STRONG_KEYWORDS):
                score -= 12
                features.append("存在明确分数线字段，已降低岗位表评分")
            if len(_matched_keywords(cells, ["报名人数", "审核通过人数", "缴费人数", "竞争比"])) >= 2:
                score -= 10
                features.append("存在报名统计字段，已降低岗位表评分")
        if table_type == "major_catalog":
            features.extend(major_features)
            if len(major_features) >= 2 and len(job_features) < 2:
                score += 12
            if len(job_features) >= 2:
                score -= 18
                features.append("存在职位表结构，已降低专业目录评分")
        context_matches = _matched_keywords(
            [normalized_context] if normalized_context else [],
            FILE_TYPE_HINTS.get(table_type, []),
        )
        if context_matches:
            score += 14 if not table_cells else 4
            features.append(f"文件名/Sheet 提示：{context_matches[0]}")
        normalized_score = max(0, score)
        confidence = round(min(0.99, normalized_score / 24), 2)
        scored_candidates.append(
            {
                "type_key": table_type,
                "type_label": TYPE_LABELS[table_type],
                "score": confidence,
                "raw_score": normalized_score,
                "matched_keywords": matches,
                "matched_features": list(dict.fromkeys(features)),
            }
        )

    scored_candidates.sort(
        key=lambda item: (
            float(item["score"]),
            TYPE_PRIORITY.get(str(item["type_key"]), 0),
        ),
        reverse=True,
    )
    best = scored_candidates[0] if scored_candidates else None
    if not best or float(best["score"]) <= 0:
        return DetectionResult()
    return DetectionResult(
        detected_type=str(best["type_key"]),
        detected_type_label=str(best["type_label"]),
        confidence=float(best["score"]),
        matched_keywords=list(best["matched_keywords"]),
        matched_features=list(best["matched_features"]),
        candidates=scored_candidates,
    )


def _matched_keywords(cells: list[str], keywords: list[str]) -> list[str]:
    matches: list[str] = []
    for keyword in keywords:
        normalized_keyword = normalize_header(keyword)
        if not normalized_keyword:
            continue
        if any(
            normalized_keyword == cell
            or normalized_keyword in cell
            or cell in normalized_keyword
            for cell in cells
        ):
            matches.append(keyword)
    return matches


def _candidate_score_bonus(cells: list[str]) -> int:
    matched_groups = sum(
        1
        for keywords in CANDIDATE_SCORE_STRONG_GROUPS.values()
        if _matched_keywords(cells, keywords)
    )
    bonus = 0
    if matched_groups >= 3:
        bonus += 8
    if matched_groups == len(CANDIDATE_SCORE_STRONG_GROUPS):
        bonus += 4
    component_hits = len(_matched_keywords(cells, CANDIDATE_SCORE_COMPONENT_KEYWORDS))
    if component_hits >= 2:
        bonus += 4
    if component_hits == len(CANDIDATE_SCORE_COMPONENT_KEYWORDS):
        bonus += 3
    return bonus


def _matched_feature_groups(
    cells: list[str],
    groups: dict[str, list[str]],
) -> list[str]:
    return [label for label, keywords in groups.items() if _matched_keywords(cells, keywords)]
