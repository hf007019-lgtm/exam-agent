"""招考数据导入脚本。

读取 raw_private 中的原始 Excel，识别表头、脱敏并聚合成岗位级分数线 CSV。
原始名单可能包含个人信息，本脚本只输出岗位级汇总数据。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERVIEW_OUTPUT_COLUMNS = [
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
OUTPUT_COLUMNS = INTERVIEW_OUTPUT_COLUMNS
FFILL_TARGET_FIELDS = [
    "department",
    "unit",
    "position_code",
    "position_name",
    "score",
]
CORE_FIELDS = [
    "position_code",
    "position_name",
    "score",
    "department",
    "unit",
]
JOB_CORE_FIELDS = [
    "position_code",
    "position_name",
    "department",
    "unit",
    "recruit_count",
]
JOB_SOURCE_FIELDS = [
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
    "remark_extra",
]
JOB_FFILL_TARGET_FIELDS = [
    "department",
    "unit",
]
REQUIRED_OUTPUT_SOURCE_FIELDS = [
    "position_code",
    "score",
]
JOB_REQUIRED_OUTPUT_SOURCE_FIELDS = [
    "position_code",
]
SAFE_OUTPUT_FILENAME = "job_scores_guangxi_2025.csv"
SAFE_OUTPUT_PATH = PROJECT_ROOT / "app" / "data" / "scores" / SAFE_OUTPUT_FILENAME
BLOCKED_INTERMEDIATE_FILENAMES = {
    "2025_interview.csv",
}
DEFAULT_PRIVACY_FIELDS = [
    "姓名",
    "性别",
    "民族",
    "准考证号",
    "准考证号码",
    "考生姓名",
    "身份证号",
    "身份证号码",
    "证件号码",
    "手机号",
    "手机号码",
    "联系电话",
    "电话",
]
PRIVACY_KEYWORDS = [
    "姓名",
    "性别",
    "民族",
    "准考证",
    "身份证",
    "证件号",
    "手机号",
    "手机号码",
    "联系电话",
    "电话",
]
ID_NUMBER_PATTERN = re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{18}|\d{15})(?!\d)")
MOBILE_NUMBER_PATTERN = re.compile(r"(?<!\d)1\d{10}(?!\d)")
LONG_DIGIT_PATTERN = re.compile(r"(?<!\d)\d{10,}(?!\d)")
DEFAULT_FIELD_ALIASES = {
    "position_code": [
        "报考职位代码",
        "职位代码",
        "岗位代码",
        "报考岗位代码",
    ],
    "position_name": [
        "报考职位名称",
        "职位名称",
        "岗位名称",
        "报考岗位名称",
    ],
    "department": [
        "报考机关",
        "招录机关",
        "主管部门",
        "部门",
    ],
    "unit": [
        "用人单位",
        "招录单位",
        "单位",
        "招考单位",
    ],
    "score": [
        "职位最低笔试成绩",
        "职位最低笔试成绩（含照顾分）",
        "最低笔试成绩",
        "最低笔试成绩（含加分）",
        "笔试成绩",
        "笔试成绩（含照顾分）",
        "最低进面分数",
        "最低进面分",
        "成绩",
    ],
    "position_category": [
        "职位类别",
    ],
    "recruit_count": [
        "招录人数",
        "招考人数",
        "计划招录人数",
        "录用人数",
        "人数",
    ],
    "education": [
        "学历",
        "学历要求",
    ],
    "degree": [
        "学位",
        "学位要求",
    ],
    "major_required": [
        "专业（学科）类别",
        "专业(学科)类别",
        "专业类别",
        "专业",
        "专业要求",
    ],
    "identity_required": [
        "职位招考对象",
        "招考对象",
        "招录对象",
    ],
    "age_requirement": [
        "年龄",
        "年龄要求",
    ],
    "political_requirement": [
        "政治面貌",
        "政治面貌要求",
    ],
    "grassroots_requirement": [
        "是否要求基层工作经历",
        "是否要求具有2年以上基层工作经历",
        "是否要求2年以上基层工作经历",
        "基层工作经历",
        "基层经历",
    ],
    "fresh_graduate_required": [
        "是否要求应届毕业生",
        "应届毕业生",
        "是否应届",
    ],
    "service_project_required": [
        "是否要求服务基层项目人员",
        "服务基层项目人员",
    ],
    "police_position": [
        "是否人民警察职位",
        "人民警察职位",
        "是否属于人民警察职位",
        "是否公安机关人民警察职位",
    ],
    "professional_test": [
        "是否进行专业测试",
        "是否进行专业笔试",
        "专业测试",
        "专业笔试",
        "是否专业测试",
    ],
    "job_description": [
        "职位简介",
        "职位描述",
        "岗位简介",
    ],
    "remark": [
        "其他",
        "其他条件",
        "其他要求",
    ],
    "remark_extra": [
        "备注",
    ],
}
GUANGXI_CITY_NAMES = [
    "防城港",
    "南宁",
    "柳州",
    "桂林",
    "梧州",
    "北海",
    "钦州",
    "贵港",
    "玉林",
    "百色",
    "贺州",
    "河池",
    "来宾",
    "崇左",
]


@dataclass
class SheetResult:
    file_path: Path
    sheet_name: str
    header_row_number: int
    key_columns: dict[str, str]
    privacy_columns: list[str]
    raw_preview_rows: list[list[str]]
    original_columns: list[str]
    normalized_columns: list[str]
    unmapped_columns: list[str]
    rows: list[dict[str, Any]]
    warning: str = ""


@dataclass
class ImportResult:
    files: list[Path]
    sheets: list[SheetResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    output_rows: list[dict[str, Any]] = field(default_factory=list)


def main() -> int:
    args = parse_args()
    config_path = resolve_path(args.config)

    try:
        config = load_config(config_path)
        result = run_import(config)
        print_preview(config, result)
        if not args.preview:
            write_output(config, result.output_rows)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="招考数据导入脚本")
    parser.add_argument(
        "--config",
        required=True,
        help="导入配置 JSON 路径，例如 scripts/import_configs/guangxi_interview_2025.json",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="只打印预览，不生成 CSV",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在：{config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    required_keys = [
        "year",
        "target",
        "exam_type",
        "region",
        "doc_type",
        "input_dir",
        "output_path",
    ]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"配置缺少字段：{', '.join(missing_keys)}")

    if config["doc_type"] not in {"interview_scores", "jobs"}:
        raise ValueError(f"暂不支持的 doc_type：{config['doc_type']}")

    validate_output_path_config(config)
    return config


def run_import(config: dict[str, Any]) -> ImportResult:
    input_dir = resolve_path(config["input_dir"])
    files = find_excel_files(input_dir)
    result = ImportResult(files=files)

    for file_path in files:
        sheet_results = process_file(file_path, config)
        if not sheet_results:
            result.warnings.append(f"警告：{file_path} 未识别到可导入的数据，已跳过。")
        result.sheets.extend(sheet_results)

    candidate_rows = [
        row
        for sheet in result.sheets
        for row in sheet.rows
    ]
    result.output_rows = aggregate_rows(config, candidate_rows)
    validate_no_privacy_columns(result.output_rows, config.get("privacy_fields", []))
    return result


def find_excel_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        print(f"警告：输入目录不存在：{input_dir}")
        return []

    patterns = ("*.xls", "*.xlsx")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(input_dir.rglob(pattern))

    return sorted(
        path
        for path in files
        if not path.name.startswith("~$")
    )


def process_file(file_path: Path, config: dict[str, Any]) -> list[SheetResult]:
    workbook = read_workbook(file_path)
    if not workbook:
        return []

    results: list[SheetResult] = []
    for sheet_name, raw_df in workbook.items():
        sheet_result = process_sheet(file_path, sheet_name, raw_df, config)
        if sheet_result.warning:
            print(f"警告：{sheet_result.warning}")
        results.append(sheet_result)

    return results


def read_workbook(file_path: Path) -> dict[str, Any]:
    try:
        import pandas as pd
    except ImportError:
        print("警告：缺少 pandas，读取 Excel 失败。请先安装：pip install pandas")
        return {}

    try:
        return pd.read_excel(
            file_path,
            sheet_name=None,
            header=None,
            dtype=str,
        )
    except ImportError as exc:
        hint = dependency_hint(file_path)
        print(f"警告：读取 {file_path} 失败。{hint} 原始错误：{exc}")
    except ValueError as exc:
        hint = dependency_hint(file_path)
        print(f"警告：读取 {file_path} 失败。{hint} 原始错误：{exc}")
    except Exception as exc:
        print(f"警告：读取 {file_path} 失败，已跳过。原始错误：{exc}")

    return {}


def dependency_hint(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".xls":
        return "如果是 .xls 文件，请安装：pip install xlrd。"
    if suffix == ".xlsx":
        return "如果是 .xlsx 文件，请安装：pip install openpyxl。"
    return "请确认 Excel 读取依赖已安装。"


def is_jobs_doc(config: dict[str, Any]) -> bool:
    return config.get("doc_type") == "jobs"


def output_columns_for_config(config: dict[str, Any]) -> list[str]:
    return JOB_OUTPUT_COLUMNS if is_jobs_doc(config) else INTERVIEW_OUTPUT_COLUMNS


def core_fields_for_config(config: dict[str, Any]) -> list[str]:
    return JOB_CORE_FIELDS if is_jobs_doc(config) else CORE_FIELDS


def required_fields_for_config(config: dict[str, Any]) -> list[str]:
    if is_jobs_doc(config):
        return JOB_REQUIRED_OUTPUT_SOURCE_FIELDS
    return REQUIRED_OUTPUT_SOURCE_FIELDS


def preview_record_label(config: dict[str, Any]) -> str:
    return "标准职位数据" if is_jobs_doc(config) else "岗位级分数线"


def process_sheet(
    file_path: Path,
    sheet_name: str,
    raw_df: Any,
    config: dict[str, Any],
) -> SheetResult:
    privacy_fields = config.get("privacy_fields") or DEFAULT_PRIVACY_FIELDS
    preview_privacy_indexes = detect_privacy_column_indexes(raw_df, privacy_fields, config)
    raw_preview_rows = build_raw_preview(raw_df, preview_privacy_indexes)
    header_info = find_header_row(raw_df, config, privacy_fields)

    empty_result = SheetResult(
        file_path=file_path,
        sheet_name=sheet_name,
        header_row_number=0,
        key_columns={},
        privacy_columns=[],
        raw_preview_rows=raw_preview_rows,
        original_columns=[],
        normalized_columns=[],
        unmapped_columns=[],
        rows=[],
    )
    if not header_info:
        empty_result.warning = f"{file_path} / {sheet_name} 未识别到表头行，已跳过。"
        return empty_result

    (
        header_index,
        key_columns,
        privacy_columns,
        column_indexes,
        original_columns,
        normalized_columns,
        unmapped_columns,
        privacy_column_indexes,
    ) = header_info
    privacy_column_indexes |= preview_privacy_indexes
    raw_preview_rows = build_raw_preview(raw_df, privacy_column_indexes)
    missing_required_fields = [
        field
        for field in required_fields_for_config(config)
        if field not in column_indexes
    ]
    if missing_required_fields:
        empty_result.warning = (
            f"{file_path} / {sheet_name} 缺少关键列："
            f"{', '.join(missing_required_fields)}，已跳过。"
        )
        empty_result.header_row_number = header_index + 1
        empty_result.key_columns = key_columns
        empty_result.privacy_columns = privacy_columns
        empty_result.raw_preview_rows = raw_preview_rows
        empty_result.original_columns = original_columns
        empty_result.normalized_columns = normalized_columns
        empty_result.unmapped_columns = unmapped_columns
        return empty_result

    if is_jobs_doc(config):
        clean_rows = build_job_clean_rows(
            raw_df=raw_df,
            header_index=header_index,
            column_indexes=column_indexes,
            config=config,
        )
    else:
        clean_rows = build_clean_rows(
            raw_df=raw_df,
            header_index=header_index,
            column_indexes=column_indexes,
            config=config,
            city=extract_city_from_filename(file_path),
        )

    return SheetResult(
        file_path=file_path,
        sheet_name=sheet_name,
        header_row_number=header_index + 1,
        key_columns=key_columns,
        privacy_columns=privacy_columns,
        raw_preview_rows=raw_preview_rows,
        original_columns=original_columns,
        normalized_columns=normalized_columns,
        unmapped_columns=unmapped_columns,
        rows=clean_rows,
    )


def find_header_row(
    raw_df: Any,
    config: dict[str, Any],
    privacy_fields: list[str],
) -> tuple[
    int,
    dict[str, str],
    list[str],
    dict[str, int],
    list[str],
    list[str],
    list[str],
    set[int],
] | None:
    alias_lookup = build_field_alias_lookup(config)
    normalized_privacy = build_privacy_lookup(privacy_fields)

    best_match: tuple[
        int,
        int,
        int,
        dict[str, str],
        list[str],
        dict[str, int],
        list[str],
        list[str],
        list[str],
        set[int],
    ] | None = None
    max_rows = min(len(raw_df.index), 30)

    for row_index in range(max_rows):
        row = raw_df.iloc[row_index].tolist()
        key_columns: dict[str, str] = {}
        privacy_columns: list[str] = []
        column_indexes: dict[str, int] = {}
        original_columns: list[str] = []
        normalized_columns: list[str] = []
        unmapped_columns: list[str] = []
        privacy_column_indexes: set[int] = set()

        for column_index, value in enumerate(row):
            original_value = clean_cell(value)
            normalized_value = normalize_header(value)
            matched_normalized_value = normalized_value
            if original_value or normalized_value:
                original_columns.append(original_value)
            if not normalized_value:
                normalized_columns.append(normalized_value)
                continue
            matched_target_field = ""
            matched_original_value = original_value
            header_candidates = build_header_candidates(
                raw_df,
                row_index,
                column_index,
                value,
            )
            privacy_header_candidates = build_privacy_header_candidates(
                raw_df,
                row_index,
                column_index,
                value,
            )
            privacy_candidate = first_privacy_header_candidate(
                privacy_header_candidates,
                normalized_privacy,
            )
            if privacy_candidate:
                normalized_columns.append(privacy_candidate)
                privacy_columns.append(
                    privacy_label(privacy_candidate, normalized_privacy)
                )
                privacy_column_indexes.add(column_index)
                continue
            for candidate_value in header_candidates:
                candidate_normalized = normalize_header(candidate_value)
                if candidate_normalized in alias_lookup:
                    matched_target_field = alias_lookup[candidate_normalized]
                    matched_normalized_value = candidate_normalized
                    matched_original_value = candidate_value
                    break
                if is_score_header(candidate_normalized):
                    matched_target_field = "score"
                    matched_normalized_value = candidate_normalized
                    matched_original_value = candidate_value
                    break
            normalized_columns.append(matched_normalized_value)
            if matched_target_field:
                key_columns[matched_target_field] = (
                    matched_original_value or matched_normalized_value
                )
                column_indexes.setdefault(matched_target_field, column_index)
            if not matched_target_field:
                unmapped_columns.append(original_value or normalized_value)

        core_match_count = len(set(key_columns) & set(core_fields_for_config(config)))
        score = core_match_count * 10 + len(privacy_columns)
        if core_match_count >= 3 and (
            best_match is None
            or core_match_count > best_match[1]
            or score > best_match[2]
        ):
            best_match = (
                row_index,
                core_match_count,
                score,
                key_columns,
                privacy_columns,
                column_indexes,
                original_columns,
                normalized_columns,
                unmapped_columns,
                privacy_column_indexes,
            )

    if not best_match:
        return None

    (
        row_index,
        _,
        _,
        key_columns,
        privacy_columns,
        column_indexes,
        original_columns,
        normalized_columns,
        unmapped_columns,
        privacy_column_indexes,
    ) = best_match

    return (
        row_index,
        key_columns,
        dedupe(privacy_columns),
        column_indexes,
        original_columns,
        normalized_columns,
        dedupe(unmapped_columns),
        privacy_column_indexes,
    )


def build_clean_rows(
    raw_df: Any,
    header_index: int,
    column_indexes: dict[str, int],
    config: dict[str, Any],
    city: str,
) -> list[dict[str, Any]]:
    import pandas as pd

    data_df = raw_df.iloc[header_index + 1 :].copy()
    if data_df.empty:
        return []

    original_has_value = data_df.apply(
        lambda row: any(clean_cell(value) for value in row.tolist()),
        axis=1,
    )
    extracted = pd.DataFrame()
    for target_field in CORE_FIELDS:
        if target_field in column_indexes:
            source_index = column_indexes[target_field]
            extracted[target_field] = data_df.iloc[:, source_index].map(clean_cell)
        else:
            extracted[target_field] = ""

    for target_field in FFILL_TARGET_FIELDS:
        if target_field in extracted:
            extracted[target_field] = extracted[target_field].replace("", pd.NA).ffill()
            extracted[target_field] = extracted[target_field].fillna("")

    extracted = extracted[CORE_FIELDS]
    extracted["score"] = extracted["score"].map(extract_number)
    extracted = extracted[
        original_has_value
        & extracted["position_code"].map(lambda value: bool(str(value).strip()))
        & extracted["score"].notna()
    ]

    rows: list[dict[str, Any]] = []
    for _, row in extracted.iterrows():
        rows.append(
            {
                "year": int(config["year"]),
                "target": config["target"],
                "exam_type": config["exam_type"],
                "region": config["region"],
                "city": city,
                "department": row.get("department", ""),
                "unit": row.get("unit", ""),
                "position_code": row.get("position_code", ""),
                "position_name": row.get("position_name", ""),
                "score": float(row.get("score")),
            }
        )

    return rows


def build_job_clean_rows(
    raw_df: Any,
    header_index: int,
    column_indexes: dict[str, int],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    import pandas as pd

    data_df = raw_df.iloc[header_index + 1 :].copy()
    if data_df.empty:
        return []

    original_has_value = data_df.apply(
        lambda row: any(clean_cell(value) for value in row.tolist()),
        axis=1,
    )
    extracted = pd.DataFrame(index=data_df.index)
    for target_field in JOB_SOURCE_FIELDS:
        if target_field in column_indexes:
            source_index = column_indexes[target_field]
            extracted[target_field] = data_df.iloc[:, source_index].map(clean_cell)
        else:
            extracted[target_field] = ""

    for target_field in JOB_FFILL_TARGET_FIELDS:
        extracted[target_field] = extracted[target_field].replace("", pd.NA).ffill()
        extracted[target_field] = extracted[target_field].fillna("")

    extracted["position_code"] = extracted["position_code"].map(clean_position_code)
    extracted["recruit_count"] = extracted["recruit_count"].map(parse_recruit_count)
    extracted = extracted[
        original_has_value
        & extracted["position_code"].map(lambda value: bool(str(value).strip()))
    ]

    rows: list[dict[str, Any]] = []
    for _, row in extracted.iterrows():
        base_row = {
            "year": int(config["year"]),
            "target": config["target"],
            "exam_type": config["exam_type"],
            "region": config["region"],
            "department": row.get("department", ""),
            "unit": row.get("unit", ""),
            "position_code": row.get("position_code", ""),
            "position_name": row.get("position_name", ""),
            "position_category": row.get("position_category", ""),
            "recruit_count": row.get("recruit_count", ""),
            "education": row.get("education", ""),
            "degree": row.get("degree", ""),
            "major_required": row.get("major_required", ""),
            "identity_required": row.get("identity_required", ""),
            "age_requirement": row.get("age_requirement", ""),
            "political_requirement": row.get("political_requirement", ""),
            "grassroots_requirement": row.get("grassroots_requirement", ""),
            "fresh_graduate_required": row.get("fresh_graduate_required", ""),
            "service_project_required": row.get("service_project_required", ""),
            "police_position": row.get("police_position", ""),
            "professional_test": row.get("professional_test", ""),
            "job_description": row.get("job_description", ""),
            "remark": join_non_empty(
                [
                    row.get("remark", ""),
                    row.get("remark_extra", ""),
                ]
            ),
            "source_type": "官方职位表",
            "data_status": "完整",
        }
        location = infer_job_city_district(base_row)
        base_row["city"] = location.get("city", "")
        base_row["district"] = location.get("district", "")
        rows.append(base_row)

    return rows


def aggregate_rows(config: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if is_jobs_doc(config):
        return aggregate_job_rows(rows)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        position_code = str(row.get("position_code", "")).strip()
        if not position_code:
            continue
        grouped.setdefault(position_code, []).append(row)

    output_rows: list[dict[str, Any]] = []
    for position_code, group_rows in grouped.items():
        scores = [float(row["score"]) for row in group_rows if row.get("score") is not None]
        if not scores:
            continue
        first_row = group_rows[0]
        output_rows.append(
            {
                "year": int(config["year"]),
                "target": config["target"],
                "exam_type": config["exam_type"],
                "region": config["region"],
                "city": first_non_empty(row.get("city", "") for row in group_rows),
                "department": first_non_empty(row.get("department", "") for row in group_rows),
                "unit": first_non_empty(row.get("unit", "") for row in group_rows),
                "position_code": position_code,
                "position_name": first_non_empty(row.get("position_name", "") for row in group_rows),
                "interview_count": len(group_rows),
                "min_interview_score": format_number(min(scores)),
                "max_interview_score": format_number(max(scores)),
                "source_type": "官方名单",
                "data_status": "参考",
            }
        )

    return sorted(
        output_rows,
        key=lambda row: (
            str(row.get("city", "")),
            str(row.get("department", "")),
            str(row.get("position_code", "")),
        ),
    )


def aggregate_job_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        position_code = clean_position_code(row.get("position_code", ""))
        if not position_code:
            continue
        grouped.setdefault(position_code, []).append(row)

    output_rows: list[dict[str, Any]] = []
    for position_code, group_rows in grouped.items():
        output_row: dict[str, Any] = {"position_code": position_code}
        for column in JOB_OUTPUT_COLUMNS:
            if column == "position_code":
                continue
            if column == "year":
                first_year = first_non_empty(row.get(column, "") for row in group_rows)
                output_row[column] = int(first_year) if first_year else ""
                continue
            if column == "recruit_count":
                first_count = first_non_empty(row.get(column, "") for row in group_rows)
                output_row[column] = parse_recruit_count(first_count) if first_count else ""
                continue
            output_row[column] = first_non_empty(row.get(column, "") for row in group_rows)
        output_rows.append(output_row)

    return sorted(
        output_rows,
        key=lambda row: (
            str(row.get("city", "")),
            str(row.get("district", "")),
            str(row.get("department", "")),
            str(row.get("position_code", "")),
        ),
    )


def print_preview(config: dict[str, Any], result: ImportResult) -> None:
    privacy_fields = config.get("privacy_fields", [])
    record_label = preview_record_label(config)
    print("招考数据导入脚本预览")
    print(f"扫描到 {len(result.files)} 个文件")

    for warning in result.warnings:
        print(warning)

    for file_path in result.files:
        file_sheets = [
            sheet
            for sheet in result.sheets
            if sheet.file_path == file_path
        ]
        if not file_sheets:
            print(f"- 文件：{file_path}")
            print("  sheet 名称：未读取")
            print("  表头行：未识别")
            continue
        for sheet in file_sheets:
            sheet_output_rows = aggregate_rows(config, sheet.rows)
            print(f"- 文件：{sheet.file_path}")
            print(f"  sheet 名称：{sheet.sheet_name}")
            print("  前 10 行原始内容简要预览：")
            print(format_preview_rows(sheet.raw_preview_rows))
            print(
                "  识别到的表头行号："
                f"{f'第 {sheet.header_row_number} 行' if sheet.header_row_number else '未识别'}"
            )
            print(f"  原始列名：{format_public_list(sheet.original_columns, privacy_fields)}")
            print(f"  标准化后的列名：{format_public_list(sheet.normalized_columns, privacy_fields)}")
            print(f"  字段映射结果：{format_mapping(sheet.key_columns)}")
            print(f"  未识别字段：{format_public_list(sheet.unmapped_columns, privacy_fields)}")
            print(
                "  将删除的隐私列数量："
                f"{len(sheet.privacy_columns)}"
            )
            print(f"  预计生成 {len(sheet_output_rows)} 条{record_label}")
            print("  前 5 条脱敏预览数据：")
            if sheet_output_rows:
                for row in sheet_output_rows[:5]:
                    print(f"  - {json.dumps(row, ensure_ascii=False)}")
            else:
                print("  - 暂无可预览数据")

    print(f"预计生成 {len(result.output_rows)} 条{record_label}")
    print("前 5 条脱敏后的预览数据：")
    for row in result.output_rows[:5]:
        print(f"- {json.dumps(row, ensure_ascii=False)}")
    if not result.output_rows:
        print("- 暂无可预览数据")


def write_output(config: dict[str, Any], output_rows: list[dict[str, Any]]) -> None:
    output_path = resolve_path(config["output_path"])
    output_columns = output_columns_for_config(config)
    record_label = preview_record_label(config)
    validate_output_path_config(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validate_no_privacy_columns(output_rows, config.get("privacy_fields", []))
    if not output_rows:
        raise ValueError("未生成可导入记录，停止写出，避免覆盖目标 CSV。")

    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"已生成{record_label} CSV：{output_path}")
    print(f"共写入 {len(output_rows)} 条记录")


def validate_no_privacy_columns(
    rows: list[dict[str, Any]],
    privacy_fields: list[str],
) -> None:
    normalized_privacy = build_privacy_lookup(privacy_fields)
    output_names = {
        normalize_header(column)
        for column in [*INTERVIEW_OUTPUT_COLUMNS, *JOB_OUTPUT_COLUMNS]
    }
    row_names = {
        normalize_header(column)
        for row in rows
        for column in row
    }
    leaked_columns = sorted(
        name
        for name in (output_names | row_names)
        if is_privacy_output_column(name, normalized_privacy)
    )
    if leaked_columns:
        raise ValueError(
            "输出字段包含隐私列，已停止导出："
            f"{', '.join(leaked_columns)}"
        )

    leaked_values = find_high_risk_privacy_values(rows)
    if leaked_values:
        raise ValueError(
            "输出内容包含疑似个人敏感号码，已停止导出："
            f"{', '.join(leaked_values[:5])}"
        )


def validate_output_path_config(config: dict[str, Any]) -> None:
    output_path = resolve_path(config["output_path"])
    output_name = output_path.name.lower()
    if (
        output_name in BLOCKED_INTERMEDIATE_FILENAMES
        or output_name.endswith("_interview.csv")
    ):
        raise ValueError(f"禁止生成面试名单中间 CSV：{output_path}")

    is_guangxi_2025_interview = (
        int(config.get("year", 0)) == 2025
        and config.get("region") == "广西"
        and config.get("doc_type") == "interview_scores"
    )
    if is_guangxi_2025_interview:
        if output_path != SAFE_OUTPUT_PATH:
            raise ValueError(f"广西 2025 面试导入只能输出：{SAFE_OUTPUT_PATH}")


def find_high_risk_privacy_values(rows: list[dict[str, Any]]) -> list[str]:
    risky_values: list[str] = []

    for row in rows:
        for column, value in row.items():
            if column == "position_code":
                continue

            text = clean_cell(value)
            if not text:
                continue

            if ID_NUMBER_PATTERN.search(text):
                risky_values.append(f"{column}=疑似身份证号")
                continue
            if MOBILE_NUMBER_PATTERN.search(text):
                risky_values.append(f"{column}=疑似手机号")
                continue
            if LONG_DIGIT_PATTERN.search(text):
                risky_values.append(f"{column}=疑似准考证号")

    return risky_values


def build_field_alias_lookup(config: dict[str, Any]) -> dict[str, str]:
    aliases_by_field: dict[str, set[str]] = {
        target_field: set(aliases)
        for target_field, aliases in DEFAULT_FIELD_ALIASES.items()
    }

    for source_field, target_field in config.get("field_mapping", {}).items():
        aliases_by_field.setdefault(target_field, set()).add(source_field)

    for target_field, aliases in config.get("field_aliases", {}).items():
        aliases_by_field.setdefault(target_field, set()).update(aliases)

    alias_lookup: dict[str, str] = {}
    for target_field, aliases in aliases_by_field.items():
        for alias in aliases:
            normalized_alias = normalize_header(alias)
            if normalized_alias:
                alias_lookup[normalized_alias] = target_field

    return alias_lookup


def build_privacy_lookup(privacy_fields: list[str]) -> dict[str, str]:
    fields = list(DEFAULT_PRIVACY_FIELDS)
    fields.extend(privacy_fields or [])
    return {
        normalize_header(field): field
        for field in fields
        if normalize_header(field)
    }


def is_privacy_output_column(
    normalized_value: str,
    normalized_privacy: dict[str, str],
) -> bool:
    if not normalized_value:
        return False
    if normalized_value in normalized_privacy:
        return True
    return any(
        normalize_header(keyword) in normalized_value
        for keyword in PRIVACY_KEYWORDS
    )


def is_privacy_source_header(
    normalized_value: str,
    normalized_privacy: dict[str, str],
) -> bool:
    return is_privacy_output_column(normalized_value, normalized_privacy)


def is_privacy_header_hint(
    normalized_value: str,
    normalized_privacy: dict[str, str],
) -> bool:
    if not normalized_value:
        return False
    if normalized_value in normalized_privacy:
        return True
    return any(
        normalized_keyword in normalized_value
        for normalized_keyword in (
            normalize_header(keyword)
            for keyword in PRIVACY_KEYWORDS
            if keyword != "民族"
        )
        if normalized_keyword
    )


def first_privacy_header_candidate(
    header_candidates: list[str],
    normalized_privacy: dict[str, str],
) -> str:
    for candidate_value in header_candidates:
        candidate_normalized = normalize_header(candidate_value)
        if is_privacy_source_header(candidate_normalized, normalized_privacy):
            return candidate_normalized
    return ""


def build_privacy_header_candidates(
    raw_df: Any,
    row_index: int,
    column_index: int,
    value: Any,
) -> list[str]:
    current_value = clean_cell(value)
    candidates = [current_value]

    if row_index > 0:
        previous_value = clean_cell(raw_df.iat[row_index - 1, column_index])
        if previous_value and current_value:
            candidates.append(previous_value + current_value)

    return dedupe(candidates)


def privacy_label(
    normalized_value: str,
    normalized_privacy: dict[str, str],
) -> str:
    if normalized_value in normalized_privacy:
        return normalized_privacy[normalized_value]
    for keyword in PRIVACY_KEYWORDS:
        normalized_keyword = normalize_header(keyword)
        if normalized_keyword in normalized_value:
            return keyword
    return normalized_value


def is_score_header(normalized_value: str) -> bool:
    if not normalized_value:
        return False

    precise_matches = [
        "职位最低笔试成绩",
        "最低笔试成绩",
        "最低进面分数",
        "最低进面分",
    ]
    if any(match in normalized_value for match in precise_matches):
        return True

    score_candidate = (
        ("最低" in normalized_value and "成绩" in normalized_value)
        or ("笔试" in normalized_value and "成绩" in normalized_value)
    )
    if not score_candidate:
        return False

    excluded_keywords = [
        "面试成绩",
        "总成绩",
        "综合成绩",
        "体检成绩",
        "考察成绩",
        "备注",
    ]
    return not any(keyword in normalized_value for keyword in excluded_keywords)


def detect_privacy_column_indexes(
    raw_df: Any,
    privacy_fields: list[str],
    config: dict[str, Any],
) -> set[int]:
    normalized_privacy = build_privacy_lookup(privacy_fields)
    alias_lookup = build_field_alias_lookup(config)
    privacy_indexes: set[int] = set()
    max_rows = min(len(raw_df.index), 30)

    for row_index in range(max_rows):
        row_values = raw_df.iloc[row_index].tolist()
        normalized_values = [normalize_header(value) for value in row_values]
        has_business_header = any(
            normalized_value in alias_lookup or is_score_header(normalized_value)
            for normalized_value in normalized_values
        )
        for column_index, normalized_value in enumerate(normalized_values):
            if has_business_header:
                is_privacy = is_privacy_source_header(
                    normalized_value,
                    normalized_privacy,
                )
            else:
                is_privacy = is_privacy_header_hint(
                    normalized_value,
                    normalized_privacy,
                )
            if is_privacy:
                privacy_indexes.add(column_index)

    return privacy_indexes


def build_raw_preview(
    raw_df: Any,
    privacy_column_indexes: set[int] | None = None,
) -> list[list[str]]:
    privacy_column_indexes = privacy_column_indexes or set()
    preview_rows: list[list[str]] = []
    max_rows = min(len(raw_df.index), 10)

    for row_index in range(max_rows):
        row_preview: list[str] = []
        for column_index, value in enumerate(raw_df.iloc[row_index].tolist()):
            if column_index in privacy_column_indexes or is_sensitive_preview_value(value):
                row_preview.append("[已脱敏]")
                continue
            row_preview.append(truncate_text(clean_cell(value), 40))
        preview_rows.append(trim_trailing_empty_cells(row_preview))

    return preview_rows


def build_header_candidates(
    raw_df: Any,
    row_index: int,
    column_index: int,
    value: Any,
) -> list[str]:
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


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def normalize_header(value: Any) -> str:
    text = clean_cell(value)
    text = "".join(
        char
        for char in text
        if not unicodedata.category(char).startswith("C")
    )
    text = re.sub(r"[\s\u3000]+", "", text)
    return text.replace("：", "").replace(":", "").replace("\ufeff", "")


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


def is_sensitive_preview_value(value: Any) -> bool:
    text = clean_cell(value)
    if not text:
        return False
    if ID_NUMBER_PATTERN.search(text) or MOBILE_NUMBER_PATTERN.search(text):
        return True
    return bool(LONG_DIGIT_PATTERN.search(text))


def extract_number(value: Any) -> float | None:
    text = clean_cell(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def clean_position_code(value: Any) -> str:
    text = re.sub(r"\s+", "", clean_cell(value))
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def parse_recruit_count(value: Any) -> int | str:
    number = extract_number(value)
    if number is None:
        return ""
    return int(number)


def infer_job_city_district(job: dict[str, Any]) -> dict[str, str]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from app.tools.region_resolver import resolve_region

    text = " ".join(
        clean_cell(job.get(field, ""))
        for field in [
            "department",
            "unit",
            "position_name",
            "job_description",
            "remark",
        ]
    )
    result = resolve_region(text)
    city = clean_cell(result.get("city", ""))
    district = clean_cell(result.get("district", ""))
    fallback = infer_guangxi_city_district_from_text(text)
    return {
        "city": city or fallback.get("city", ""),
        "district": district or fallback.get("district", ""),
    }


def infer_guangxi_city_district_from_text(text: str) -> dict[str, str]:
    normalized_text = clean_cell(text)
    city = ""
    city_match: re.Match[str] | None = None
    for candidate in sorted(GUANGXI_CITY_NAMES, key=len, reverse=True):
        match = re.search(rf"{re.escape(candidate)}市?", normalized_text)
        if match:
            city = candidate
            city_match = match
            break

    district = ""
    if city_match:
        tail_text = normalized_text[city_match.end() : city_match.end() + 16]
        district_match = re.match(r"([\u4e00-\u9fff]{2,8}(?:区|县|市))", tail_text)
        if district_match:
            district = district_match.group(1)

    return {
        "city": city,
        "district": district,
    }


def join_non_empty(values: list[Any]) -> str:
    return "；".join(dedupe([clean_cell(value) for value in values if clean_cell(value)]))


def extract_city_from_filename(file_path: Path) -> str:
    stem = file_path.stem
    matches = re.findall(r"([\u4e00-\u9fff]{2,12})市", stem)
    if not matches:
        return ""
    return matches[-1].strip()


def format_mapping(mapping: dict[str, str]) -> str:
    if not mapping:
        return "未识别"
    return ", ".join(
        f"{target} <- {source}"
        for target, source in mapping.items()
    )


def format_list(items: list[str]) -> str:
    clean_items = [item for item in items if item]
    if not clean_items:
        return "无"
    return ", ".join(clean_items)


def format_public_list(items: list[str], privacy_fields: list[str]) -> str:
    normalized_privacy = build_privacy_lookup(privacy_fields)
    public_items: list[str] = []
    for item in items:
        if not item:
            continue
        if is_privacy_output_column(normalize_header(item), normalized_privacy):
            public_items.append("[隐私列]")
        else:
            public_items.append(item)
    return format_list(dedupe(public_items))


def format_preview_rows(rows: list[list[str]]) -> str:
    if not rows:
        return "  - 暂无可预览内容"
    lines = []
    for index, row in enumerate(rows, start=1):
        lines.append(f"  - 第 {index} 行：{json.dumps(row, ensure_ascii=False)}")
    return "\n".join(lines)


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def first_non_empty(values: Any) -> str:
    for value in values:
        text = clean_cell(value)
        if text:
            return text
    return ""


def truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length] + "..."


def trim_trailing_empty_cells(row: list[str]) -> list[str]:
    while row and row[-1] == "":
        row.pop()
    return row


def dedupe(items: list[str]) -> list[str]:
    results: list[str] = []
    for item in items:
        if item and item not in results:
            results.append(item)
    return results


if __name__ == "__main__":
    raise SystemExit(main())
