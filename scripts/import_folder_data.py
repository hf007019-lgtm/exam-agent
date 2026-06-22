"""Import folder-style provincial exam data into normalized CSV files.

Expected source folders:
raw_private/{province_slug}/{year}/jobs/
raw_private/{province_slug}/{year}/scores/

This script reads only Excel files under raw_private, writes normalized CSV files
under app/data, and writes a markdown import report under docs.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from province_registry import get_province_name, list_province_slugs, normalize_province_slug


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "raw_private"
DATA_DIR = PROJECT_ROOT / "app" / "data"
JOBS_DATA_DIR = DATA_DIR / "jobs"
SCORES_DATA_DIR = DATA_DIR / "scores"
DOCS_DIR = PROJECT_ROOT / "docs"

SUPPORTED_EXCEL_SUFFIXES = {".xls", ".xlsx"}
WPS_SUFFIXES = {".et", ".wps"}

JOB_OUTPUT_COLUMNS = [
    "year",
    "target",
    "exam_type",
    "region",
    "city",
    "district",
    "department",
    "unit",
    "position_code",
    "position_name",
    "position_category",
    "recruit_count",
    "education",
    "degree",
    "major_required",
    "identity_required",
    "age_requirement",
    "political_requirement",
    "grassroots_requirement",
    "fresh_graduate_required",
    "service_project_required",
    "police_position",
    "professional_test",
    "job_description",
    "remark",
    "source_type",
    "data_status",
]

SCORE_OUTPUT_COLUMNS = [
    "year",
    "target",
    "exam_type",
    "region",
    "city",
    "department",
    "unit",
    "position_code",
    "position_name",
    "interview_count",
    "min_interview_score",
    "max_interview_score",
    "source_type",
    "data_status",
]

JOB_ALIAS_BY_FIELD = {
    "position_code": ["职位代码", "岗位代码", "职位编码", "岗位编码", "职位编号", "岗位编号", "代码", "报考职位代码", "报考岗位代码"],
    "position_name": ["职位名称", "岗位名称", "职位", "招考职位", "招录职位", "岗位", "报考职位名称", "报考岗位名称"],
    "department": ["招录机关", "招考单位", "主管部门", "招录单位", "单位名称", "部门名称", "报考机关", "部门"],
    "unit": ["用人单位", "招录单位", "具体单位", "单位名称", "单位"],
    "recruit_count": ["招录人数", "招考人数", "计划人数", "计划招录人数", "计划招考人数", "录用人数", "拟录用人数", "招录名额", "招考名额", "录用名额", "招聘人数", "招聘名额", "招收人数", "人数", "名额"],
    "major_required": ["专业", "专业要求", "专业类别", "专业名称", "专业限制", "专业条件", "专业（学科）类别", "专业(学科)类别", "专业（学科）要求", "专业(学科)要求", "所需专业", "招考专业", "报考专业", "要求专业", "研究生专业", "本科专业", "专科专业", "学科门类", "专业大类"],
    "education": ["学历", "学历要求", "最低学历", "文化程度", "文化程度要求", "学历层次", "学历类别", "学历学位", "学历（学位）", "学历(学位)", "学历、学位", "学历要求（学位要求）", "学历要求(学位要求)", "报考学历"],
    "degree": ["学位", "学位要求"],
    "job_description": ["职位简介", "岗位简介", "职位描述", "岗位描述"],
    "remark": ["备注", "其他", "其他要求", "其他条件"],
    "position_category": ["职位类别", "岗位类别"],
    "identity_required": ["招考对象", "招录对象", "职位招考对象", "身份要求"],
    "age_requirement": ["年龄", "年龄要求"],
    "political_requirement": ["政治面貌", "政治面貌要求"],
    "grassroots_requirement": ["基层工作经历", "基层经历", "基层工作经历要求"],
    "fresh_graduate_required": ["应届毕业生", "是否要求应届毕业生", "是否应届"],
    "service_project_required": ["服务基层项目人员", "是否要求服务基层项目人员"],
    "police_position": ["人民警察职位", "是否人民警察职位", "是否公安机关人民警察职位"],
    "professional_test": ["专业测试", "专业笔试", "是否进行专业测试", "是否进行专业笔试"],
}

SCORE_ALIAS_BY_FIELD = {
    "position_code": ["职位代码", "岗位代码", "职位编码", "报考职位代码", "报考岗位代码"],
    "position_name": ["职位名称", "岗位名称", "报考职位名称", "报考岗位名称"],
    "department": ["招录机关", "单位", "招考单位", "主管部门", "报考机关"],
    "unit": ["用人单位", "招录单位", "单位名称"],
    "min_interview_score": ["最低进面分", "最低分", "最低笔试成绩", "最低进面分数", "职位最低笔试成绩"],
    "max_interview_score": ["最高进面分", "最高分", "最高笔试成绩", "最高进面分数"],
    "interview_count": ["面试人数", "入围人数", "进面人数", "面试入围人数"],
    "score": ["笔试成绩", "成绩", "笔试分数", "分数"],
}

JOB_HEADER_KEYWORDS = [
    "职位代码",
    "岗位代码",
    "职位名称",
    "岗位名称",
    "招录人数",
    "招考人数",
    "招录机关",
    "用人单位",
    "专业",
    "学历",
]

SCORE_HEADER_KEYWORDS = [
    "职位代码",
    "岗位代码",
    "最低进面分",
    "最低分",
    "面试入围",
    "准考证",
    "笔试成绩",
    "进面分",
]

COMPETITION_KEYWORDS = ["报名人数", "竞争比", "报考人数", "确认人数"]
SUSPECTED_SCORE_FILENAME_KEYWORDS = ["最低进面分", "进面分", "分数线", "面试入围", "入面", "笔试成绩"]
STRONG_POSITION_CODE_ALIASES = [
    "职位代码",
    "岗位代码",
    "职位编码",
    "岗位编码",
    "职位编号",
    "岗位编号",
    "招考职位代码",
    "招录职位代码",
]
POSITION_CODE_GENERIC_ALIASES = ["代码"]
POSITION_CODE_NEGATIVE_KEYWORDS = [
    "单位",
    "部门",
    "机关",
    "机构",
    "地区",
    "行政区",
    "区划",
    "类别",
    "类型",
    "考试类别",
    "职位类别",
    "专业",
    "学科",
    "科目",
    "学历",
    "学位",
    "政治面貌",
    "民族",
    "名称",
]
POSITION_CODE_NAMESPACE_KEYWORDS = ["单位", "部门", "机关", "机构"]
FIELD_MAPPING_REPORT_FIELDS = [
    "recruit_count",
    "education",
    "major_required",
    "degree",
    "age_requirement",
    "identity_required",
]
RECRUIT_COUNT_ALIASES = [
    "招录人数",
    "招考人数",
    "计划人数",
    "计划招录人数",
    "计划招考人数",
    "录用人数",
    "拟录用人数",
    "招录名额",
    "招考名额",
    "录用名额",
    "招聘人数",
    "招聘名额",
    "招收人数",
    "人数",
    "名额",
]
RECRUIT_COUNT_NEGATIVE_KEYWORDS = [
    "报名人数",
    "报考人数",
    "审核通过人数",
    "缴费人数",
    "确认人数",
    "竞争比",
    "职位代码",
    "岗位代码",
    "单位代码",
    "部门代码",
    "专业代码",
    "年龄",
    "年龄要求",
    "最低服务年限",
]
EDUCATION_ALIASES = [
    "学历",
    "学历要求",
    "最低学历",
    "文化程度",
    "文化程度要求",
    "学历层次",
    "学历类别",
    "学历学位",
    "学历（学位）",
    "学历(学位)",
    "学历、学位",
    "学历要求（学位要求）",
    "学历要求(学位要求)",
    "报考学历",
]
MAJOR_REQUIRED_ALIASES = [
    "专业",
    "专业要求",
    "专业类别",
    "专业名称",
    "专业限制",
    "专业条件",
    "专业（学科）类别",
    "专业(学科)类别",
    "专业（学科）要求",
    "专业(学科)要求",
    "所需专业",
    "招考专业",
    "报考专业",
    "要求专业",
    "研究生专业",
    "本科专业",
    "专科专业",
    "学科门类",
    "专业大类",
    "不限专业",
    "专业不限",
]
MAJOR_LEVEL_LABELS = {
    "研究生": "研究生",
    "本科": "本科",
    "专科": "专科",
}
BROAD_EXACT_ONLY_ALIASES = {
    "代码",
    "职位",
    "岗位",
    "人数",
    "单位",
    "部门",
    "专业",
    "学历",
    "学位",
}

PRIVACY_KEYWORDS = [
    "姓名",
    "性别",
    "准考证",
    "身份证",
    "手机号",
    "联系电话",
    "证件号码",
    "证件号",
    "出生日期",
]

ID_NUMBER_PATTERN = re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{18}|\d{15})(?!\d)")
MOBILE_NUMBER_PATTERN = re.compile(r"(?<!\d)1\d{10}(?!\d)")
LONG_DIGIT_PATTERN = re.compile(r"(?<!\d)\d{10,}(?!\d)")


@dataclass
class SheetReport:
    sheet_name: str
    detected_type: str
    imported_rows: int = 0
    skipped: bool = False
    reason: str = ""
    skipped_reason: str = ""
    raw_rows: int = 0
    normalized_rows: int = 0
    non_empty_position_code_rows: int = 0
    empty_position_code_rows: int = 0
    output_rows: int = 0
    selected_position_code_column: str = ""
    position_code_candidate_columns: list["PositionCodeCandidate"] = field(default_factory=list)
    field_mapping_details: list["FieldMappingDetail"] = field(default_factory=list)
    recruit_count_non_empty_rows: int = 0
    education_non_empty_rows: int = 0
    major_required_non_empty_rows: int = 0
    privacy_fields: list[str] = field(default_factory=list)


@dataclass
class FileReport:
    path: Path
    folder_type: str
    detected_type: str = ""
    status: str = ""
    reason: str = ""
    sheets: list[SheetReport] = field(default_factory=list)


@dataclass
class RowBuildStats:
    raw_rows: int = 0
    normalized_rows: int = 0
    non_empty_position_code_rows: int = 0
    empty_position_code_rows: int = 0
    recruit_count_non_empty_rows: int = 0
    education_non_empty_rows: int = 0
    major_required_non_empty_rows: int = 0


@dataclass
class FieldMappingCandidate:
    column_index: int | None
    column_name: str
    sample_values: list[str]
    empty_count: int
    non_empty_count: int
    score: int
    reject_reason: str = ""
    selected: bool = False
    component_indexes: tuple[int, ...] = ()


@dataclass
class FieldMappingDetail:
    field: str
    selected_column: str = ""
    candidate_columns: list[FieldMappingCandidate] = field(default_factory=list)


@dataclass
class PositionCodeCandidate:
    column_index: int | None
    column_name: str
    non_empty_count: int
    unique_count: int
    unique_ratio: float
    sample_values: list[str]
    score: int
    reject_reason: str = ""
    selected: bool = False
    component_indexes: tuple[int, ...] = ()


@dataclass
class PositionCodeSelection:
    selected_column_name: str = ""
    column_index: int | None = None
    component_indexes: tuple[int, ...] = ()
    candidates: list[PositionCodeCandidate] = field(default_factory=list)


@dataclass
class ProvinceImportReport:
    province_slug: str
    province_name: str
    year: int
    files: list[FileReport] = field(default_factory=list)
    output_paths: dict[str, Path] = field(default_factory=dict)
    output_counts: dict[str, int] = field(default_factory=dict)
    output_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    output_skipped_reasons: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def main() -> int:
    args = parse_args()
    province_slugs = resolve_target_provinces(args)
    selected_types = ["jobs", "scores"] if args.type == "all" else [args.type]

    exit_code = 0
    for province_slug in province_slugs:
        try:
            report = import_province(
                province_slug=province_slug,
                year=args.year,
                selected_types=selected_types,
            )
            write_import_report(report)
            print_summary(report)
        except Exception as exc:
            exit_code = 1
            print(f"错误：{province_slug} 导入失败：{exc}", file=sys.stderr)

    return exit_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 raw_private 目录一键导入省考数据")
    parser.add_argument("--province", help="省份拼音目录，例如 guangdong")
    parser.add_argument("--all", action="store_true", help="导入注册表中的全部省份")
    parser.add_argument("--year", required=True, type=int, help="年份，例如 2025")
    parser.add_argument(
        "--type",
        choices=["jobs", "scores", "all"],
        default="all",
        help="导入类型，默认 all",
    )
    args = parser.parse_args()

    if args.all and args.province:
        parser.error("--all 和 --province 只能二选一")
    if not args.all and not args.province:
        parser.error("请指定 --province 或 --all")
    return args


def resolve_target_provinces(args: argparse.Namespace) -> list[str]:
    if args.all:
        return list_province_slugs()
    return [normalize_province_slug(args.province)]


def import_province(
    province_slug: str,
    year: int,
    selected_types: list[str],
) -> ProvinceImportReport:
    province_name = get_province_name(province_slug)
    report = ProvinceImportReport(
        province_slug=province_slug,
        province_name=province_name,
        year=year,
    )
    rows_by_type: dict[str, list[dict[str, Any]]] = {"jobs": [], "scores": []}

    for folder_type in selected_types:
        input_dir = RAW_ROOT / province_slug / str(year) / folder_type
        files = find_source_files(input_dir)
        if not input_dir.exists():
            report.failures.append(f"{input_dir} 不存在，已跳过。")
            continue
        if not files:
            report.failures.append(f"{input_dir} 未扫描到可处理文件。")
            continue

        for file_path in files:
            file_report = process_source_file(
                file_path=file_path,
                folder_type=folder_type,
                province_name=province_name,
                year=year,
            )
            report.files.append(file_report)
            if file_report.status == "imported":
                for sheet in file_report.sheets:
                    if sheet.skipped:
                        continue
                    sheet_rows = getattr(sheet, "_rows", [])
                    rows_by_type[folder_type].extend(sheet_rows)

    if "jobs" in selected_types:
        job_rows = aggregate_jobs(rows_by_type["jobs"])
        job_stats = build_output_stats(report, "jobs", len(job_rows))
        job_skip_reason = detect_output_skip_reason(report, "jobs", job_stats)
        write_csv_if_rows(
            rows=job_rows,
            output_path=JOBS_DATA_DIR / f"jobs_{province_slug}_{year}.csv",
            columns=JOB_OUTPUT_COLUMNS,
            report=report,
            kind="jobs",
            stats=job_stats,
            skip_reason=job_skip_reason,
        )

    if "scores" in selected_types:
        score_rows = aggregate_scores(rows_by_type["scores"])
        score_stats = build_output_stats(report, "scores", len(score_rows))
        write_csv_if_rows(
            rows=score_rows,
            output_path=SCORES_DATA_DIR / f"job_scores_{province_slug}_{year}.csv",
            columns=SCORE_OUTPUT_COLUMNS,
            report=report,
            kind="scores",
            stats=score_stats,
        )

    return report


def find_source_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    files = [
        path
        for path in input_dir.rglob("*")
        if path.is_file() and not path.name.startswith("~$")
    ]
    return sorted(
        path
        for path in files
        if path.suffix.lower() in SUPPORTED_EXCEL_SUFFIXES | WPS_SUFFIXES
    )


def process_source_file(
    file_path: Path,
    folder_type: str,
    province_name: str,
    year: int,
) -> FileReport:
    file_report = FileReport(path=file_path, folder_type=folder_type)
    suffix = file_path.suffix.lower()
    file_text = normalize_text(file_path.name)

    if any(keyword in file_text for keyword in COMPETITION_KEYWORDS):
        file_report.detected_type = "competition"
        file_report.status = "skipped"
        file_report.reason = "competition 文件，本轮跳过。"
        return file_report

    if folder_type == "jobs" and any(keyword in file_text for keyword in SUSPECTED_SCORE_FILENAME_KEYWORDS):
        file_report.detected_type = "suspected_scores"
        file_report.status = "skipped"
        file_report.reason = "该文件疑似 scores，但当前放在 jobs 目录，请移动到 scores 后重新导入。"
        return file_report

    if suffix in WPS_SUFFIXES:
        file_report.detected_type = "unsupported_wps"
        file_report.status = "skipped"
        file_report.reason = "该文件需要先用 WPS 另存为 .xlsx 后再导入。"
        return file_report

    if suffix not in SUPPORTED_EXCEL_SUFFIXES:
        file_report.detected_type = "unsupported"
        file_report.status = "skipped"
        file_report.reason = f"暂不支持的文件类型：{suffix}"
        return file_report

    try:
        workbook = read_workbook(file_path)
    except RuntimeError as exc:
        file_report.status = "failed"
        file_report.reason = str(exc)
        return file_report

    if not workbook:
        file_report.status = "failed"
        file_report.reason = "Excel 读取失败或没有可读取 sheet。"
        return file_report

    imported_any = False
    detected_types: list[str] = []
    for sheet_name, raw_df in workbook.items():
        sheet_report, rows = process_sheet(
            raw_df=raw_df,
            sheet_name=str(sheet_name),
            expected_type=folder_type,
            province_name=province_name,
            year=year,
        )
        setattr(sheet_report, "_rows", rows)
        file_report.sheets.append(sheet_report)
        if sheet_report.detected_type:
            detected_types.append(sheet_report.detected_type)
        if rows:
            imported_any = True

    file_report.detected_type = summarize_detected_type(detected_types) or folder_type
    file_report.status = "imported" if imported_any else "skipped"
    if not imported_any and not file_report.reason:
        file_report.reason = "未识别到可导入数据。"
    return file_report


def read_workbook(file_path: Path) -> dict[str, Any]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("缺少 pandas，无法读取 Excel。请先安装 pandas/openpyxl/xlrd。") from exc

    try:
        return pd.read_excel(file_path, sheet_name=None, header=None, dtype=str)
    except Exception as exc:
        print(f"警告：读取 {file_path} 失败，已跳过。原始错误：{exc}", file=sys.stderr)
        return {}


def process_sheet(
    raw_df: Any,
    sheet_name: str,
    expected_type: str,
    province_name: str,
    year: int,
) -> tuple[SheetReport, list[dict[str, Any]]]:
    if raw_df is None or raw_df.empty:
        return SheetReport(sheet_name=sheet_name, detected_type="", skipped=True, reason="空 sheet。", skipped_reason="空 sheet。"), []

    header_info = find_header_row(raw_df, expected_type)
    if not header_info:
        return SheetReport(
            sheet_name=sheet_name,
            detected_type="",
            skipped=True,
            reason="前 20 行内未识别到表头，可能是说明页或合并说明行。",
            skipped_reason="字段映射失败",
        ), []

    header_index, detected_type, column_indexes, privacy_fields = header_info
    if detected_type == "competition":
        return SheetReport(
            sheet_name=sheet_name,
            detected_type="competition",
            skipped=True,
            reason="competition 文件，本轮跳过。",
            skipped_reason="competition 文件，本轮跳过。",
            privacy_fields=privacy_fields,
        ), []

    if detected_type != expected_type:
        return SheetReport(
            sheet_name=sheet_name,
            detected_type=detected_type,
            skipped=True,
            reason=f"sheet 识别为 {detected_type}，与目录类型 {expected_type} 不一致。",
            skipped_reason=f"sheet 识别为 {detected_type}，与目录类型 {expected_type} 不一致。",
            privacy_fields=privacy_fields,
        ), []

    if expected_type == "jobs":
        position_code_selection = select_position_code_candidate(raw_df, header_index)
        field_mapping_details = build_job_field_mapping_details(raw_df, header_index)
        rows, stats = build_job_rows(
            raw_df,
            header_index,
            column_indexes,
            province_name,
            year,
            position_code_selection,
            field_mapping_details,
        )
    else:
        position_code_selection = PositionCodeSelection()
        field_mapping_details = []
        rows, stats = build_score_rows(raw_df, header_index, column_indexes, province_name, year, privacy_fields)

    sheet_skipped = expected_type == "jobs" and not position_code_selection.selected_column_name
    sheet_reason = "未能确认职位代码字段。" if sheet_skipped else ""
    sheet_skipped_reason = "字段映射失败" if sheet_skipped else ""

    return SheetReport(
        sheet_name=sheet_name,
        detected_type=detected_type,
        imported_rows=len(rows),
        skipped=sheet_skipped,
        reason=sheet_reason,
        skipped_reason=sheet_skipped_reason,
        raw_rows=stats.raw_rows,
        normalized_rows=stats.normalized_rows,
        non_empty_position_code_rows=stats.non_empty_position_code_rows,
        empty_position_code_rows=stats.empty_position_code_rows,
        selected_position_code_column=position_code_selection.selected_column_name,
        position_code_candidate_columns=position_code_selection.candidates,
        field_mapping_details=field_mapping_details,
        recruit_count_non_empty_rows=stats.recruit_count_non_empty_rows,
        education_non_empty_rows=stats.education_non_empty_rows,
        major_required_non_empty_rows=stats.major_required_non_empty_rows,
        privacy_fields=privacy_fields,
    ), rows


def find_header_row(
    raw_df: Any,
    expected_type: str,
) -> tuple[int, str, dict[str, int], list[str]] | None:
    max_rows = min(len(raw_df.index), 20)
    best_match: tuple[int, int, str, dict[str, int], list[str]] | None = None

    for row_index in range(max_rows):
        values = raw_df.iloc[row_index].tolist()
        row_text = normalize_text(" ".join(clean_cell(value) for value in values))
        if not row_text:
            continue

        privacy_fields = detect_privacy_fields(values)
        if any(keyword in row_text for keyword in COMPETITION_KEYWORDS):
            return row_index, "competition", {}, privacy_fields

        job_indexes = build_column_indexes(raw_df, row_index, JOB_ALIAS_BY_FIELD)
        score_indexes = build_column_indexes(raw_df, row_index, SCORE_ALIAS_BY_FIELD)
        job_keyword_count = sum(1 for keyword in JOB_HEADER_KEYWORDS if keyword in row_text)
        score_keyword_count = sum(1 for keyword in SCORE_HEADER_KEYWORDS if keyword in row_text)

        if expected_type == "jobs":
            detected_type = "jobs" if len(job_indexes) + job_keyword_count >= 3 else ""
            score = len(job_indexes) * 10 + job_keyword_count
            column_indexes = job_indexes
        else:
            detected_type = "scores" if len(score_indexes) + score_keyword_count >= 2 else ""
            score = len(score_indexes) * 10 + score_keyword_count + len(privacy_fields)
            column_indexes = score_indexes

        if not detected_type:
            continue

        if best_match is None or score > best_match[1]:
            best_match = (row_index, score, detected_type, column_indexes, privacy_fields)

    if not best_match:
        return None

    row_index, _, detected_type, column_indexes, privacy_fields = best_match
    if expected_type == "scores" and "position_code" not in column_indexes:
        return None
    return row_index, detected_type, column_indexes, privacy_fields


def build_column_indexes(
    raw_df: Any,
    row_index: int,
    aliases_by_field: dict[str, list[str]],
) -> dict[str, int]:
    alias_lookup = build_alias_lookup(aliases_by_field)
    column_indexes: dict[str, int] = {}

    for column_index, value in enumerate(raw_df.iloc[row_index].tolist()):
        candidates = build_header_candidates(raw_df, row_index, column_index, value)
        for candidate in candidates:
            normalized_candidate = normalize_text(candidate)
            fields = match_aliases(normalized_candidate, alias_lookup)
            if fields:
                for field in fields:
                    if field not in column_indexes:
                        column_indexes[field] = column_index
                break

    return column_indexes


def build_alias_lookup(aliases_by_field: dict[str, list[str]]) -> dict[str, list[str]]:
    alias_lookup: dict[str, list[str]] = {}
    for field, aliases in aliases_by_field.items():
        for alias in aliases:
            normalized_alias = normalize_text(alias)
            if not normalized_alias:
                continue
            alias_lookup.setdefault(normalized_alias, [])
            if field not in alias_lookup[normalized_alias]:
                alias_lookup[normalized_alias].append(field)
    return alias_lookup


def match_aliases(normalized_candidate: str, alias_lookup: dict[str, list[str]]) -> list[str]:
    if normalized_candidate in alias_lookup:
        return alias_lookup[normalized_candidate]
    matched_fields: list[str] = []
    for alias, fields in alias_lookup.items():
        if alias in BROAD_EXACT_ONLY_ALIASES:
            continue
        if alias and alias in normalized_candidate:
            matched_fields.extend(fields)
    return dedupe(matched_fields)


def build_header_candidates(raw_df: Any, row_index: int, column_index: int, value: Any) -> list[str]:
    current_value = clean_cell(value)
    candidates = [current_value]
    if row_index > 0:
        previous_value = clean_cell(raw_df.iat[row_index - 1, column_index])
        if previous_value and current_value:
            candidates.append(previous_value + current_value)
    if row_index + 1 < len(raw_df.index):
        next_value = clean_cell(raw_df.iat[row_index + 1, column_index])
        if current_value and next_value:
            candidates.append(current_value + next_value)
    return dedupe(candidates)


def select_position_code_candidate(raw_df: Any, header_index: int) -> PositionCodeSelection:
    data_row_indexes = [
        row_index
        for row_index in range(header_index + 1, len(raw_df.index))
        if row_has_data(raw_df, row_index)
    ]
    raw_rows = len(data_row_indexes)
    candidates: list[PositionCodeCandidate] = []

    for column_index, value in enumerate(raw_df.iloc[header_index].tolist()):
        candidate = build_position_code_candidate(raw_df, header_index, column_index, value, data_row_indexes, raw_rows)
        if candidate:
            candidates.append(candidate)

    candidates.extend(build_composite_position_code_candidates(raw_df, data_row_indexes, candidates, raw_rows))
    selectable_candidates = [candidate for candidate in candidates if not candidate.reject_reason]
    selected = max(selectable_candidates, key=lambda candidate: candidate.score, default=None)
    if selected:
        selected.selected = True
        selected_column_name = selected.column_name
        column_index = selected.column_index
        component_indexes = selected.component_indexes
    else:
        selected_column_name = ""
        column_index = None
        component_indexes = ()

    return PositionCodeSelection(
        selected_column_name=selected_column_name,
        column_index=column_index,
        component_indexes=component_indexes,
        candidates=sorted(candidates, key=lambda candidate: candidate.score, reverse=True),
    )


def build_position_code_candidate(
    raw_df: Any,
    header_index: int,
    column_index: int,
    value: Any,
    data_row_indexes: list[int],
    raw_rows: int,
) -> PositionCodeCandidate | None:
    column_name = choose_position_code_candidate_name(raw_df, header_index, column_index, value)
    normalized_name = normalize_text(column_name)
    if not normalized_name or not is_possible_position_code_header(normalized_name):
        return None

    values = [clean_position_code(raw_df.iat[row_index, column_index]) for row_index in data_row_indexes]
    non_empty_values = [value for value in values if value]
    unique_values = dedupe(non_empty_values)
    non_empty_count = len(non_empty_values)
    unique_count = len(unique_values)
    unique_ratio = unique_count / non_empty_count if non_empty_count else 0
    score = score_position_code_header(normalized_name)
    score += min(40, int(unique_ratio * 40))
    if raw_rows and non_empty_count >= raw_rows * 0.9:
        score += 20
    if average_length(non_empty_values) <= 2 and unique_ratio < 0.5:
        score -= 15

    reject_reason = build_position_code_reject_reason(normalized_name, non_empty_count, unique_ratio, raw_rows)
    if reject_reason:
        score -= 100

    return PositionCodeCandidate(
        column_index=column_index,
        column_name=column_name,
        non_empty_count=non_empty_count,
        unique_count=unique_count,
        unique_ratio=unique_ratio,
        sample_values=unique_values[:5],
        score=score,
        reject_reason=reject_reason,
    )


def choose_position_code_candidate_name(raw_df: Any, header_index: int, column_index: int, value: Any) -> str:
    candidates = build_header_candidates(raw_df, header_index, column_index, value)
    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if is_possible_position_code_header(normalized_candidate):
            return clean_cell(candidate)
    return clean_cell(value)


def is_possible_position_code_header(normalized_name: str) -> bool:
    strong_aliases = [normalize_text(alias) for alias in STRONG_POSITION_CODE_ALIASES]
    generic_aliases = [normalize_text(alias) for alias in POSITION_CODE_GENERIC_ALIASES]
    if normalized_name in strong_aliases or normalized_name in generic_aliases:
        return True
    if any(alias and alias in normalized_name for alias in strong_aliases):
        return True
    return any(token in normalized_name for token in ["代码", "编码", "编号"])


def score_position_code_header(normalized_name: str) -> int:
    strong_aliases = [normalize_text(alias) for alias in STRONG_POSITION_CODE_ALIASES]
    generic_aliases = [normalize_text(alias) for alias in POSITION_CODE_GENERIC_ALIASES]
    if normalized_name in strong_aliases:
        return 120
    if any(alias and alias in normalized_name for alias in strong_aliases):
        return 80
    if normalized_name in generic_aliases:
        return 30
    return 10


def build_position_code_reject_reason(
    normalized_name: str,
    non_empty_count: int,
    unique_ratio: float,
    raw_rows: int,
) -> str:
    negative_hits = [
        keyword
        for keyword in POSITION_CODE_NEGATIVE_KEYWORDS
        if normalize_text(keyword) in normalized_name
    ]
    if negative_hits:
        return f"表头包含排除词：{', '.join(dedupe(negative_hits))}"
    if non_empty_count == 0:
        return "该列没有非空值"
    if raw_rows > 500 and unique_ratio < 0.3:
        return "唯一比例低于 0.3，不适合作为独立职位代码"
    return ""


def build_composite_position_code_candidates(
    raw_df: Any,
    data_row_indexes: list[int],
    candidates: list[PositionCodeCandidate],
    raw_rows: int,
) -> list[PositionCodeCandidate]:
    local_code_candidates = [
        candidate
        for candidate in candidates
        if candidate.column_index is not None and is_local_position_code_component(candidate.column_name)
        and candidate.unique_ratio < 0.3
    ]
    namespace_candidates = [
        candidate
        for candidate in candidates
        if candidate.column_index is not None and is_namespace_code_component(candidate.column_name)
    ]

    composite_candidates: list[PositionCodeCandidate] = []
    for namespace_candidate in namespace_candidates:
        for local_candidate in local_code_candidates:
            if namespace_candidate.column_index == local_candidate.column_index:
                continue
            values = []
            for row_index in data_row_indexes:
                namespace_value = clean_position_code(raw_df.iat[row_index, namespace_candidate.column_index])
                local_value = clean_position_code(raw_df.iat[row_index, local_candidate.column_index])
                if namespace_value and local_value:
                    values.append(f"{namespace_value}-{local_value}")
            unique_values = dedupe(values)
            non_empty_count = len(values)
            unique_count = len(unique_values)
            unique_ratio = unique_count / non_empty_count if non_empty_count else 0
            reject_reason = ""
            if non_empty_count == 0:
                reject_reason = "组合列没有非空值"
            elif raw_rows > 500 and unique_ratio < 0.3:
                reject_reason = "组合后唯一比例仍低于 0.3"

            score = 160 + min(60, int(unique_ratio * 60))
            if raw_rows and non_empty_count >= raw_rows * 0.9:
                score += 20
            if reject_reason:
                score -= 100

            composite_candidates.append(
                PositionCodeCandidate(
                    column_index=None,
                    column_name=f"{namespace_candidate.column_name} + {local_candidate.column_name}",
                    non_empty_count=non_empty_count,
                    unique_count=unique_count,
                    unique_ratio=unique_ratio,
                    sample_values=unique_values[:5],
                    score=score,
                    reject_reason=reject_reason,
                    component_indexes=(namespace_candidate.column_index, local_candidate.column_index),
                )
            )
    return composite_candidates


def is_local_position_code_component(column_name: str) -> bool:
    normalized_name = normalize_text(column_name)
    strong_aliases = [normalize_text(alias) for alias in STRONG_POSITION_CODE_ALIASES]
    if not any(alias and alias in normalized_name for alias in strong_aliases):
        return False
    return not any(
        normalize_text(keyword) in normalized_name
        for keyword in POSITION_CODE_NEGATIVE_KEYWORDS
    )


def is_namespace_code_component(column_name: str) -> bool:
    normalized_name = normalize_text(column_name)
    if not any(token in normalized_name for token in ["代码", "编码", "编号"]):
        return False
    if any(normalize_text(keyword) in normalized_name for keyword in ["名称", "专业", "学科", "科目"]):
        return False
    return any(normalize_text(keyword) in normalized_name for keyword in POSITION_CODE_NAMESPACE_KEYWORDS)


def build_job_field_mapping_details(raw_df: Any, header_index: int) -> list[FieldMappingDetail]:
    data_row_indexes = [
        row_index
        for row_index in range(header_index + 1, len(raw_df.index))
        if row_has_data(raw_df, row_index)
    ]
    details = [
        build_field_mapping_detail(raw_df, header_index, data_row_indexes, field)
        for field in FIELD_MAPPING_REPORT_FIELDS
    ]
    return details


def build_field_mapping_detail(
    raw_df: Any,
    header_index: int,
    data_row_indexes: list[int],
    field_name: str,
) -> FieldMappingDetail:
    candidates: list[FieldMappingCandidate] = []
    for column_index, value in enumerate(raw_df.iloc[header_index].tolist()):
        candidate = build_field_mapping_candidate(
            raw_df,
            header_index,
            column_index,
            value,
            data_row_indexes,
            field_name,
        )
        if candidate:
            candidates.append(candidate)

    if field_name == "major_required":
        composite_candidate = build_major_composite_candidate(raw_df, data_row_indexes, candidates)
        if composite_candidate:
            candidates.append(composite_candidate)

    selectable_candidates = [candidate for candidate in candidates if not candidate.reject_reason]
    selected = max(selectable_candidates, key=lambda candidate: candidate.score, default=None)
    if selected:
        selected.selected = True
        selected_column = selected.column_name
    else:
        selected_column = ""
    return FieldMappingDetail(
        field=field_name,
        selected_column=selected_column,
        candidate_columns=sorted(candidates, key=lambda candidate: candidate.score, reverse=True),
    )


def build_field_mapping_candidate(
    raw_df: Any,
    header_index: int,
    column_index: int,
    value: Any,
    data_row_indexes: list[int],
    field_name: str,
) -> FieldMappingCandidate | None:
    column_name = choose_field_candidate_name(raw_df, header_index, column_index, value, field_name)
    normalized_name = normalize_text(column_name)
    if not normalized_name:
        return None
    if not is_possible_field_header(normalized_name, field_name):
        return None

    values = [clean_cell(raw_df.iat[row_index, column_index]) for row_index in data_row_indexes]
    non_empty_values = [value for value in values if value]
    empty_count = len(values) - len(non_empty_values)
    non_empty_count = len(non_empty_values)
    score = score_field_header(normalized_name, field_name)
    reject_reason = build_field_reject_reason(normalized_name, non_empty_values, field_name, len(data_row_indexes))

    if field_name == "recruit_count":
        numeric_ratio = numeric_value_ratio(non_empty_values)
        small_integer_ratio = small_integer_value_ratio(non_empty_values)
        score += int(numeric_ratio * 60) + int(small_integer_ratio * 30)
    else:
        score += 30 if non_empty_count else 0
    if data_row_indexes and non_empty_count >= len(data_row_indexes) * 0.8:
        score += 20
    if reject_reason:
        score -= 100

    return FieldMappingCandidate(
        column_index=column_index,
        column_name=column_name,
        sample_values=dedupe(non_empty_values)[:5],
        empty_count=empty_count,
        non_empty_count=non_empty_count,
        score=score,
        reject_reason=reject_reason,
    )


def choose_field_candidate_name(raw_df: Any, header_index: int, column_index: int, value: Any, field_name: str) -> str:
    candidates = build_header_candidates(raw_df, header_index, column_index, value)
    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if is_possible_field_header(normalized_candidate, field_name):
            return clean_cell(candidate)
    return clean_cell(value)


def is_possible_field_header(normalized_name: str, field_name: str) -> bool:
    aliases = [normalize_text(alias) for alias in field_aliases(field_name)]
    if normalized_name in aliases:
        return True
    if field_name == "education" and normalized_name in {normalize_text("学位"), normalize_text("学位要求")}:
        return False
    return any(alias and alias in normalized_name for alias in aliases if alias not in BROAD_EXACT_ONLY_ALIASES)


def field_aliases(field_name: str) -> list[str]:
    if field_name == "recruit_count":
        return RECRUIT_COUNT_ALIASES
    if field_name == "education":
        return EDUCATION_ALIASES
    if field_name == "major_required":
        return MAJOR_REQUIRED_ALIASES
    return JOB_ALIAS_BY_FIELD.get(field_name, [])


def score_field_header(normalized_name: str, field_name: str) -> int:
    aliases = [normalize_text(alias) for alias in field_aliases(field_name)]
    if normalized_name in aliases:
        return 100
    if any(alias and alias in normalized_name for alias in aliases if alias not in BROAD_EXACT_ONLY_ALIASES):
        return 70
    return 20


def build_field_reject_reason(
    normalized_name: str,
    non_empty_values: list[str],
    field_name: str,
    raw_rows: int,
) -> str:
    if field_name == "recruit_count":
        negative_hits = [
            keyword
            for keyword in RECRUIT_COUNT_NEGATIVE_KEYWORDS
            if normalize_text(keyword) in normalized_name
        ]
        if negative_hits:
            return f"表头包含排除词：{', '.join(dedupe(negative_hits))}"
        if not non_empty_values:
            return "该列没有非空值"
        if raw_rows > 0 and len(non_empty_values) < raw_rows * 0.3:
            return "非空值过少"
        if numeric_value_ratio(non_empty_values) < 0.7:
            return "数字值比例过低"
    elif field_name == "education":
        if normalized_name in {normalize_text("学位"), normalize_text("学位要求")}:
            return "学位字段不能单独作为学历字段"
        if not non_empty_values:
            return "该列没有非空值"
    elif field_name == "major_required":
        if not non_empty_values:
            return "该列没有非空值"
    elif not non_empty_values:
        return "该列没有非空值"
    return ""


def build_major_composite_candidate(
    raw_df: Any,
    data_row_indexes: list[int],
    candidates: list[FieldMappingCandidate],
) -> FieldMappingCandidate | None:
    level_candidates = [
        candidate
        for candidate in candidates
        if candidate.column_index is not None and major_level_label(candidate.column_name)
    ]
    if len(level_candidates) < 2:
        return None

    values = []
    for row_index in data_row_indexes:
        values.append(build_major_required_value(raw_df, row_index, level_candidates))
    non_empty_values = [value for value in values if value]
    if not non_empty_values:
        return None
    empty_count = len(values) - len(non_empty_values)
    score = 160
    if data_row_indexes and len(non_empty_values) >= len(data_row_indexes) * 0.8:
        score += 20
    return FieldMappingCandidate(
        column_index=None,
        column_name=" + ".join(candidate.column_name for candidate in level_candidates),
        sample_values=dedupe(non_empty_values)[:5],
        empty_count=empty_count,
        non_empty_count=len(non_empty_values),
        score=score,
        component_indexes=tuple(candidate.column_index for candidate in level_candidates if candidate.column_index is not None),
    )


def build_major_required_value(raw_df: Any, row_index: int, candidates: list[FieldMappingCandidate]) -> str:
    parts = []
    for candidate in candidates:
        if candidate.column_index is None:
            continue
        value = clean_cell(raw_df.iat[row_index, candidate.column_index])
        if not value:
            continue
        label = major_level_label(candidate.column_name)
        if label:
            parts.append(f"{label}：{value}")
        else:
            parts.append(value)
    return "；".join(parts)


def major_level_label(column_name: str) -> str:
    normalized_name = normalize_text(column_name)
    for keyword, label in MAJOR_LEVEL_LABELS.items():
        if normalize_text(keyword) in normalized_name:
            return label
    return ""


def build_job_rows(
    raw_df: Any,
    header_index: int,
    column_indexes: dict[str, int],
    province_name: str,
    year: int,
    position_code_selection: PositionCodeSelection,
    field_mapping_details: list[FieldMappingDetail],
) -> tuple[list[dict[str, Any]], RowBuildStats]:
    rows: list[dict[str, Any]] = []
    stats = RowBuildStats()
    field_mapping_by_name = {detail.field: detail for detail in field_mapping_details}
    for row_index in range(header_index + 1, len(raw_df.index)):
        if not row_has_data(raw_df, row_index):
            continue
        stats.raw_rows += 1
        source = extract_source_row(raw_df, row_index, column_indexes)
        position_code = extract_selected_position_code(raw_df, row_index, position_code_selection)
        if not position_code:
            stats.empty_position_code_rows += 1
            continue
        stats.non_empty_position_code_rows += 1

        row = {column: "" for column in JOB_OUTPUT_COLUMNS}
        row.update(
            {
                "year": year,
                "target": "公务员",
                "exam_type": "省考",
                "region": province_name,
                "position_code": position_code,
                "source_type": "官方职位表",
                "data_status": "完整",
            }
        )
        for field in JOB_ALIAS_BY_FIELD:
            if field in row and field != "position_code":
                row[field] = clean_cell(source.get(field, ""))
        apply_job_field_mappings(raw_df, row_index, row, field_mapping_by_name)
        row["recruit_count"] = parse_int(row.get("recruit_count", ""))
        if clean_cell(row.get("recruit_count", "")):
            stats.recruit_count_non_empty_rows += 1
        if clean_cell(row.get("education", "")):
            stats.education_non_empty_rows += 1
        if clean_cell(row.get("major_required", "")):
            stats.major_required_non_empty_rows += 1
        region = infer_city_district(row)
        row["city"] = region.get("city", "")
        row["district"] = region.get("district", "")
        rows.append(row)
    stats.normalized_rows = len(rows)
    return rows, stats


def apply_job_field_mappings(
    raw_df: Any,
    row_index: int,
    row: dict[str, Any],
    field_mapping_by_name: dict[str, FieldMappingDetail],
) -> None:
    for field_name in FIELD_MAPPING_REPORT_FIELDS:
        detail = field_mapping_by_name.get(field_name)
        if not detail:
            continue
        value = extract_mapped_field_value(raw_df, row_index, detail)
        if value:
            row[field_name] = value


def extract_mapped_field_value(raw_df: Any, row_index: int, detail: FieldMappingDetail) -> str:
    selected_candidate = next((candidate for candidate in detail.candidate_columns if candidate.selected), None)
    if not selected_candidate:
        return ""
    if detail.field == "major_required" and selected_candidate.component_indexes:
        level_candidates = [
            candidate
            for candidate in detail.candidate_columns
            if candidate.column_index in selected_candidate.component_indexes
        ]
        return build_major_required_value(raw_df, row_index, level_candidates)
    if selected_candidate.column_index is None:
        return ""
    value = clean_cell(raw_df.iat[row_index, selected_candidate.column_index])
    if detail.field == "major_required" and is_unlimited_major_value(value):
        return "不限"
    return value


def is_unlimited_major_value(value: str) -> bool:
    normalized_value = normalize_text(value)
    return normalized_value in {normalize_text("不限"), normalize_text("不限专业"), normalize_text("专业不限")}


def extract_selected_position_code(
    raw_df: Any,
    row_index: int,
    position_code_selection: PositionCodeSelection,
) -> str:
    if position_code_selection.component_indexes:
        values = [
            clean_position_code(raw_df.iat[row_index, column_index])
            for column_index in position_code_selection.component_indexes
        ]
        if all(values):
            return "-".join(values)
        return ""
    if position_code_selection.column_index is None:
        return ""
    return clean_position_code(raw_df.iat[row_index, position_code_selection.column_index])


def build_score_rows(
    raw_df: Any,
    header_index: int,
    column_indexes: dict[str, int],
    province_name: str,
    year: int,
    privacy_fields: list[str],
) -> tuple[list[dict[str, Any]], RowBuildStats]:
    rows: list[dict[str, Any]] = []
    stats = RowBuildStats()
    has_privacy = bool(privacy_fields)
    for row_index in range(header_index + 1, len(raw_df.index)):
        if not row_has_data(raw_df, row_index):
            continue
        stats.raw_rows += 1
        source = extract_source_row(raw_df, row_index, column_indexes)
        position_code = clean_position_code(source.get("position_code", ""))
        if not position_code:
            stats.empty_position_code_rows += 1
            continue
        stats.non_empty_position_code_rows += 1

        row = {column: "" for column in SCORE_OUTPUT_COLUMNS}
        row.update(
            {
                "year": year,
                "target": "公务员",
                "exam_type": "省考",
                "region": province_name,
                "position_code": position_code,
                "source_type": "进面分数线或面试入围名单",
                "data_status": "部分统计" if has_privacy else "完整",
            }
        )
        for field in SCORE_ALIAS_BY_FIELD:
            if field in row and field != "position_code":
                row[field] = clean_cell(source.get(field, ""))
        if source.get("score"):
            row["_score"] = clean_cell(source.get("score", ""))
        region = infer_city_district(row)
        row["city"] = region.get("city", "")
        rows.append(row)
    stats.normalized_rows = len(rows)
    return rows, stats


def row_has_data(raw_df: Any, row_index: int) -> bool:
    return any(clean_cell(value) for value in raw_df.iloc[row_index].tolist())


def extract_source_row(raw_df: Any, row_index: int, column_indexes: dict[str, int]) -> dict[str, str]:
    return {
        field: clean_cell(raw_df.iat[row_index, column_index])
        for field, column_index in column_indexes.items()
    }


def aggregate_jobs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        position_code = clean_position_code(row.get("position_code", ""))
        if not position_code:
            continue
        grouped.setdefault(position_code, []).append(row)

    output_rows: list[dict[str, Any]] = []
    for position_code, group_rows in grouped.items():
        output_row = {column: "" for column in JOB_OUTPUT_COLUMNS}
        output_row["position_code"] = position_code
        for column in JOB_OUTPUT_COLUMNS:
            if column == "position_code":
                continue
            output_row[column] = first_non_empty(row.get(column, "") for row in group_rows)
        output_rows.append(output_row)

    return sorted(output_rows, key=lambda row: str(row.get("position_code", "")))


def aggregate_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("position_code", "")), []).append(row)

    output_rows: list[dict[str, Any]] = []
    for position_code, group_rows in grouped.items():
        score_values = []
        for row in group_rows:
            for value in [
                row.get("_score", ""),
                row.get("min_interview_score", ""),
                row.get("max_interview_score", ""),
            ]:
                number = extract_number(value)
                if number is not None:
                    score_values.append(number)

        explicit_count = first_non_empty(row.get("interview_count", "") for row in group_rows)
        output_row = {column: "" for column in SCORE_OUTPUT_COLUMNS}
        output_row["position_code"] = position_code
        for column in SCORE_OUTPUT_COLUMNS:
            if column in {"position_code", "interview_count", "min_interview_score", "max_interview_score"}:
                continue
            output_row[column] = first_non_empty(row.get(column, "") for row in group_rows)
        output_row["interview_count"] = parse_int(explicit_count) or len(group_rows)
        if score_values:
            output_row["min_interview_score"] = format_number(min(score_values))
            output_row["max_interview_score"] = format_number(max(score_values))
        output_row["data_status"] = infer_score_data_status(output_row, group_rows)
        output_rows.append(output_row)

    validate_no_privacy_output(output_rows)
    return sorted(output_rows, key=lambda row: str(row.get("position_code", "")))


def infer_score_data_status(output_row: dict[str, Any], group_rows: list[dict[str, Any]]) -> str:
    if any(row.get("data_status") == "部分统计" for row in group_rows):
        return "部分统计"
    if not output_row.get("min_interview_score") or not output_row.get("max_interview_score"):
        return "部分统计"
    return "完整"


def write_csv_if_rows(
    rows: list[dict[str, Any]],
    output_path: Path,
    columns: list[str],
    report: ProvinceImportReport,
    kind: str,
    stats: dict[str, int] | None = None,
    skip_reason: str = "",
) -> None:
    report.output_counts[kind] = len(rows)
    if stats is not None:
        report.output_stats[kind] = stats
    if skip_reason:
        report.output_skipped_reasons[kind] = skip_reason
        if skip_reason == "输出行数异常":
            report.failures.append(
                f"{kind} 未写出 CSV，原因：输出行数异常。导入结果异常：输出行数明显低于原始行数，"
                "可能是表头识别或职位代码字段映射失败，已避免覆盖现有文件。"
            )
        else:
            report.failures.append(f"{kind} 未写出 CSV，原因：{skip_reason}，避免覆盖现有文件。")
        return
    if not rows:
        reason = infer_empty_output_reason(kind, stats or {})
        report.output_skipped_reasons[kind] = reason
        report.failures.append(f"{kind} 未写出 CSV，原因：{reason}，避免覆盖现有文件。")
        return

    add_jobs_field_coverage_warnings(report, kind, stats or {})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    report.output_paths[kind] = output_path


def add_jobs_field_coverage_warnings(report: ProvinceImportReport, kind: str, stats: dict[str, int]) -> None:
    if kind != "jobs" or stats.get("raw_rows", 0) <= 500:
        return
    warning_rules = [
        ("recruit_count_non_empty_rows", "招录人数字段未识别，请检查原表表头。"),
        ("education_non_empty_rows", "学历字段未识别，请检查原表表头。"),
        ("major_required_non_empty_rows", "专业字段未识别，请检查原表表头。"),
    ]
    for stat_key, message in warning_rules:
        if stats.get(stat_key, 0) == 0 and message not in report.failures:
            report.failures.append(message)


def build_output_stats(report: ProvinceImportReport, kind: str, output_rows: int) -> dict[str, int]:
    stats = {
        "raw_rows": 0,
        "normalized_rows": 0,
        "non_empty_position_code_rows": 0,
        "empty_position_code_rows": 0,
        "recruit_count_non_empty_rows": 0,
        "education_non_empty_rows": 0,
        "major_required_non_empty_rows": 0,
        "output_rows": output_rows,
    }
    for file_report in report.files:
        if file_report.folder_type != kind:
            continue
        for sheet in file_report.sheets:
            stats["raw_rows"] += sheet.raw_rows
            stats["normalized_rows"] += sheet.normalized_rows
            stats["non_empty_position_code_rows"] += sheet.non_empty_position_code_rows
            stats["empty_position_code_rows"] += sheet.empty_position_code_rows
            stats["recruit_count_non_empty_rows"] += sheet.recruit_count_non_empty_rows
            stats["education_non_empty_rows"] += sheet.education_non_empty_rows
            stats["major_required_non_empty_rows"] += sheet.major_required_non_empty_rows
    return stats


def detect_output_skip_reason(report: ProvinceImportReport, kind: str, stats: dict[str, int]) -> str:
    if kind != "jobs":
        return ""
    has_suspected_score_file = any(
        file_report.folder_type == "jobs" and file_report.detected_type == "suspected_scores"
        for file_report in report.files
    )
    if has_suspected_score_file and stats.get("output_rows", 0) == 0:
        return "文件类型疑似放错目录"
    if stats.get("output_rows", 0) == 0 and any(
        file_report.folder_type == "jobs"
        and any(sheet.skipped_reason == "字段映射失败" for sheet in file_report.sheets)
        for file_report in report.files
    ):
        return "字段映射失败"
    if stats.get("raw_rows", 0) > 0 and stats.get("non_empty_position_code_rows", 0) == 0:
        return "字段映射失败"
    if stats.get("raw_rows", 0) > 500 and stats.get("output_rows", 0) < stats["raw_rows"] * 0.3:
        return "输出行数异常"
    return ""


def infer_empty_output_reason(kind: str, stats: dict[str, int]) -> str:
    if kind == "jobs" and stats.get("raw_rows", 0) > 0:
        return "字段映射失败"
    return "未生成可导入记录"


def write_import_report(report: ProvinceImportReport) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = DOCS_DIR / f"import_report_{report.province_slug}_{report.year}.md"
    lines = [
        f"# {report.province_name} {report.year} 原始数据导入报告",
        "",
        "## 扫描文件",
    ]

    if not report.files:
        lines.append("- 未扫描到文件。")
    for file_report in report.files:
        lines.append(f"- `{relative_path(file_report.path)}`")
        lines.append(f"  - 目录类型：{file_report.folder_type}")
        lines.append(f"  - 识别类型：{file_report.detected_type or '未识别'}")
        lines.append(f"  - 状态：{file_report.status or '未知'}")
        if file_report.reason:
            lines.append(f"  - 原因：{file_report.reason}")
        for sheet in file_report.sheets:
            lines.append(
                f"  - sheet `{sheet.sheet_name}`："
                f"{'跳过' if sheet.skipped else '导入'}，"
                f"识别为 {sheet.detected_type or '未识别'}，"
                f"导入 {sheet.imported_rows} 行"
            )
            lines.append(f"    - raw_rows: {sheet.raw_rows}")
            lines.append(f"    - normalized_rows: {sheet.normalized_rows}")
            lines.append(f"    - non_empty_position_code_rows: {sheet.non_empty_position_code_rows}")
            lines.append(f"    - empty_position_code_rows: {sheet.empty_position_code_rows}")
            lines.append(f"    - recruit_count_non_empty_rows: {sheet.recruit_count_non_empty_rows}")
            lines.append(f"    - education_non_empty_rows: {sheet.education_non_empty_rows}")
            lines.append(f"    - major_required_non_empty_rows: {sheet.major_required_non_empty_rows}")
            if sheet.selected_position_code_column:
                lines.append(f"    - selected_position_code_column: {sheet.selected_position_code_column}")
            if sheet.position_code_candidate_columns:
                lines.append("    - position_code_candidate_columns:")
                for candidate in sheet.position_code_candidate_columns:
                    sample_values = ", ".join(candidate.sample_values) if candidate.sample_values else ""
                    lines.append(
                        "      - "
                        f"列名: {candidate.column_name}; "
                        f"非空数量: {candidate.non_empty_count}; "
                        f"唯一值数量: {candidate.unique_count}; "
                        f"唯一比例: {candidate.unique_ratio:.4f}; "
                        f"样例值: {sample_values}; "
                        f"得分: {candidate.score}; "
                        f"是否被选中: {'是' if candidate.selected else '否'}; "
                        f"未选中原因: {candidate.reject_reason or '得分低于最终选中列'}"
                    )
            if sheet.field_mapping_details:
                lines.append("    - field_mapping_details:")
                for detail in sheet.field_mapping_details:
                    lines.append(f"      - field: {detail.field}")
                    lines.append(f"        selected_column: {detail.selected_column or '未识别'}")
                    lines.append("        candidate_columns:")
                    if not detail.candidate_columns:
                        lines.append("          - 无候选列")
                    for candidate in detail.candidate_columns:
                        sample_values = ", ".join(candidate.sample_values) if candidate.sample_values else ""
                        lines.append(
                            "          - "
                            f"列名: {candidate.column_name}; "
                            f"样例值: {sample_values}; "
                            f"empty_count: {candidate.empty_count}; "
                            f"non_empty_count: {candidate.non_empty_count}; "
                            f"得分: {candidate.score}; "
                            f"是否被选中: {'是' if candidate.selected else '否'}; "
                            f"reject_reason: {candidate.reject_reason or '得分低于最终选中列'}"
                        )
            if sheet.skipped_reason:
                lines.append(f"    - skipped_reason: {sheet.skipped_reason}")
            if sheet.privacy_fields:
                lines.append(f"    - 隐私字段风险：{', '.join(sheet.privacy_fields)}")
            if sheet.reason:
                lines.append(f"    - 跳过原因：{sheet.reason}")

    lines.extend(["", "## 输出 CSV"])
    if not report.output_stats and not report.output_paths:
        lines.append("- 本次未写出 CSV。")
    for kind in sorted(set(report.output_stats) | set(report.output_paths) | set(report.output_counts)):
        output_path = report.output_paths.get(kind)
        stats = report.output_stats.get(kind, {})
        if output_path:
            lines.append(
                f"- {kind}: `{relative_path(output_path)}`，"
                f"成功导入 {report.output_counts.get(kind, 0)} 条"
            )
        else:
            reason = report.output_skipped_reasons.get(kind, "未生成可导入记录")
            lines.append(f"- {kind}: 未写出 CSV，原因：{reason}")
        if stats:
            lines.append(f"  - raw_rows: {stats.get('raw_rows', 0)}")
            lines.append(f"  - normalized_rows: {stats.get('normalized_rows', 0)}")
            lines.append(f"  - non_empty_position_code_rows: {stats.get('non_empty_position_code_rows', 0)}")
            lines.append(f"  - empty_position_code_rows: {stats.get('empty_position_code_rows', 0)}")
            lines.append(f"  - recruit_count_non_empty_rows: {stats.get('recruit_count_non_empty_rows', 0)}")
            lines.append(f"  - education_non_empty_rows: {stats.get('education_non_empty_rows', 0)}")
            lines.append(f"  - major_required_non_empty_rows: {stats.get('major_required_non_empty_rows', 0)}")
            lines.append(f"  - output_rows: {stats.get('output_rows', 0)}")
            if kind in report.output_skipped_reasons:
                lines.append(f"  - skipped_reason: {report.output_skipped_reasons[kind]}")

    lines.extend(["", "## 失败或需要人工处理"])
    if not report.failures:
        lines.append("- 无。")
    else:
        for failure in report.failures:
            lines.append(f"- {failure}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(report: ProvinceImportReport) -> None:
    print(f"{report.province_name} {report.year} 导入完成")
    for kind, count in sorted(report.output_counts.items()):
        output_path = report.output_paths.get(kind)
        if output_path:
            print(f"- {kind}: {count} 条 -> {output_path}")
        else:
            print(f"- {kind}: {count} 条，未写出 CSV")
    print(f"- 报告：{DOCS_DIR / f'import_report_{report.province_slug}_{report.year}.md'}")


def detect_privacy_fields(values: list[Any]) -> list[str]:
    fields: list[str] = []
    row_text = normalize_text(" ".join(clean_cell(value) for value in values))
    for keyword in PRIVACY_KEYWORDS:
        if keyword in row_text:
            fields.append(keyword)
    return dedupe(fields)


def infer_city_district(row: dict[str, Any]) -> dict[str, str]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from app.tools.region_resolver import resolve_region
    except Exception:
        return {"city": "", "district": ""}

    text = " ".join(
        clean_cell(row.get(field, ""))
        for field in ["department", "unit", "position_name", "job_description", "remark"]
    )
    resolved = resolve_region(text)
    return {
        "city": clean_cell(resolved.get("city", "")),
        "district": clean_cell(resolved.get("district", "")),
    }


def validate_no_privacy_output(rows: list[dict[str, Any]]) -> None:
    columns = {normalize_text(column) for row in rows for column in row}
    leaked_columns = [
        keyword
        for keyword in PRIVACY_KEYWORDS
        if any(keyword in column for column in columns)
    ]
    if leaked_columns:
        raise ValueError(f"输出字段包含隐私字段：{', '.join(leaked_columns)}")

    for row in rows:
        for column, value in row.items():
            if column == "position_code":
                continue
            text = clean_cell(value)
            if (
                ID_NUMBER_PATTERN.search(text)
                or MOBILE_NUMBER_PATTERN.search(text)
                or LONG_DIGIT_PATTERN.search(text)
            ):
                raise ValueError("输出内容包含疑似个人敏感号码，已停止导出。")


def summarize_detected_type(types: list[str]) -> str:
    clean_types = [item for item in types if item]
    if not clean_types:
        return ""
    if "competition" in clean_types:
        return "competition"
    if len(set(clean_types)) == 1:
        return clean_types[0]
    return "mixed"


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat", "na", "<na>"}:
        return ""
    return text


def normalize_text(value: Any) -> str:
    text = clean_cell(value)
    text = "".join(
        char
        for char in text
        if not unicodedata.category(char).startswith("C")
    )
    return re.sub(r"[\s\u3000,，。；;：:\-_/（）()【】\[\]“”\"'、]+", "", text)


def clean_position_code(value: Any) -> str:
    text = re.sub(r"\s+", "", clean_cell(value))
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def extract_number(value: Any) -> float | None:
    text = clean_cell(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def parse_int(value: Any) -> int | str:
    number = extract_number(value)
    if number is None:
        return ""
    return int(number)


def numeric_value_ratio(values: list[str]) -> float:
    if not values:
        return 0
    numeric_count = sum(1 for value in values if extract_number(value) is not None)
    return numeric_count / len(values)


def small_integer_value_ratio(values: list[str]) -> float:
    if not values:
        return 0
    small_integer_count = 0
    for value in values:
        number = extract_number(value)
        if number is not None and float(number).is_integer() and 0 < number <= 50:
            small_integer_count += 1
    return small_integer_count / len(values)


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def average_length(values: list[str]) -> float:
    if not values:
        return 0
    return sum(len(value) for value in values) / len(values)


def first_non_empty(values: Any) -> str:
    for value in values:
        text = clean_cell(value)
        if text:
            return text
    return ""


def dedupe(items: list[str]) -> list[str]:
    results: list[str] = []
    for item in items:
        if item and item not in results:
            results.append(item)
    return results


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
