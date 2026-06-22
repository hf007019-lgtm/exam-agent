"""Build user-facing summaries for exam datasets."""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.db.import_repository import (
    list_imported_candidate_scores,
    list_imported_dataset_summaries,
    list_imported_score_lines,
)
from app.tools.province_registry import (
    DEFAULT_DATA_YEAR,
    SCORES_DATA_DIR,
    detect_province_in_text,
    get_province_name,
)


SCORE_FILE_PATTERN = re.compile(
    rf"^job_scores_(?P<slug>[a-z_]+)_{DEFAULT_DATA_YEAR}\.csv$"
)

DATASET_GROUPS = [
    ("jobs", "Job datasets", "职位表数据"),
    ("scores", "Score datasets", "分数表数据"),
    ("reviews", "Review candidate datasets", "资格复审名单"),
    ("other", "Other structured datasets", "其他结构化数据"),
]


def get_data_catalog() -> dict[str, Any]:
    """Return database-only coverage metadata without exposing internal paths."""
    database_datasets = [
        item
        for item in list_imported_dataset_summaries()
        if int(item.get("record_count") or 0) > 0
    ]
    job_datasets = [
        item for item in database_datasets if item.get("data_type") == "job_table"
    ]
    score_datasets = [
        item
        for item in database_datasets
        if item.get("data_type") in {"score_line_table", "candidate_score_table"}
    ]
    review_datasets = [
        item
        for item in database_datasets
        if item.get("data_type") == "review_candidate_list"
    ]
    imported_datasets = [
        item for item in database_datasets if item.get("source_kind") == "imported"
    ]
    dataset_groups = _build_dataset_groups(database_datasets)

    provinces = sorted(
        {
            item["province"]
            for item in [*job_datasets, *score_datasets, *review_datasets]
            if item.get("province")
        }
    )
    return {
        "default_year": DEFAULT_DATA_YEAR,
        "province_count": len(provinces),
        "job_dataset_count": len(job_datasets),
        "job_record_count": sum(item["record_count"] for item in job_datasets),
        "score_dataset_count": len(score_datasets),
        "score_record_count": sum(item["record_count"] for item in score_datasets),
        "review_dataset_count": len(review_datasets),
        "review_record_count": sum(item["record_count"] for item in review_datasets),
        "database_dataset_count": len(database_datasets),
        "database_record_count": sum(item["record_count"] for item in database_datasets),
        "imported_dataset_count": len(imported_datasets),
        "imported_record_count": sum(item["record_count"] for item in imported_datasets),
        "provinces": provinces,
        "job_datasets": job_datasets,
        "score_datasets": score_datasets,
        "review_datasets": review_datasets,
        "imported_datasets": imported_datasets,
        "database_datasets": database_datasets,
        "dataset_groups": dataset_groups,
    }


def search_score_catalog(
    province: str = "",
    keyword: str = "",
    position_code: str = "",
    min_score: float | None = None,
    max_score: float | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Search SQLite scores, with legacy CSV fallback only when SQLite is empty."""
    normalized_province = str(province or "").strip()
    if normalized_province in {"不限", "全部", "全部已导入省份"}:
        normalized_province = ""
    normalized_keyword = _normalize_search_text(keyword)
    normalized_code = _normalize_position_code(position_code)
    safe_limit = max(1, min(int(limit or 100), 200))
    results: list[dict[str, Any]] = []
    total_matches = 0

    database_rows = _iter_imported_score_rows(normalized_province)
    for row in database_rows:
        if not _score_row_matches(
            row,
            keyword=normalized_keyword,
            position_code=normalized_code,
            min_score=min_score,
            max_score=max_score,
        ):
            continue
        total_matches += 1
        if len(results) < safe_limit:
            results.append(row)

    # Compatibility only: old installations may not have run the seed migration.
    if not database_rows:
        for dataset_province, path in _available_score_csvs():
            if normalized_province and normalized_province != "不限":
                if dataset_province != normalized_province:
                    continue

            with path.open("r", encoding="utf-8-sig", newline="") as file:
                for row in csv.DictReader(file):
                    normalized = _normalize_score_row(row, dataset_province)
                    if not _score_row_matches(
                        normalized,
                        keyword=normalized_keyword,
                        position_code=normalized_code,
                        min_score=min_score,
                        max_score=max_score,
                    ):
                        continue
                    total_matches += 1
                    if len(results) < safe_limit:
                        results.append(normalized)

    results.sort(
        key=lambda item: (
            item.get("storage") == "database",
            item.get("year") or 0,
            item.get("min_interview_score") or 0,
            item.get("position_code") or "",
        ),
        reverse=True,
    )
    return {
        "year": DEFAULT_DATA_YEAR,
        "total": total_matches,
        "returned": len(results),
        "items": results[:safe_limit],
    }


@lru_cache(maxsize=1)
def _available_score_csvs() -> tuple[tuple[str, Path], ...]:
    if not SCORES_DATA_DIR.exists():
        return tuple()

    datasets: list[tuple[str, Path]] = []
    for path in sorted(SCORES_DATA_DIR.glob(f"job_scores_*_{DEFAULT_DATA_YEAR}.csv")):
        match = SCORE_FILE_PATTERN.match(path.name)
        if not match:
            continue
        province = get_province_name(match.group("slug"))
        if province and _count_csv_rows(path) > 0:
            datasets.append((province, path))
    return tuple(datasets)


def _build_dataset_groups(datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items_by_group: dict[str, list[dict[str, Any]]] = {
        key: [] for key, _, _ in DATASET_GROUPS
    }
    for dataset in datasets:
        group_key = _dataset_group_key(dataset)
        if group_key in items_by_group:
            items_by_group[group_key].append(dataset)

    groups = []
    for key, kicker, title in DATASET_GROUPS:
        items = sorted(
            items_by_group[key],
            key=lambda item: (
                int(item.get("year") or 0),
                str(item.get("province") or ""),
                str(item.get("title") or item.get("name") or ""),
            ),
            reverse=True,
        )
        groups.append(
            {
                "key": key,
                "kicker": kicker,
                "title": title,
                "items": items,
                "dataset_count": len(items),
                "record_count": sum(int(item.get("record_count") or 0) for item in items),
            }
        )
    return groups


def _dataset_group_key(dataset: dict[str, Any]) -> str:
    catalog_group = str(dataset.get("catalog_group") or "").strip()
    if catalog_group in {"jobs", "scores", "reviews", "other"}:
        return catalog_group
    data_type = str(dataset.get("data_type") or "").strip()
    kind = str(dataset.get("kind") or "").strip()
    if data_type == "job_table" or kind == "jobs":
        return "jobs"
    if data_type in {"score_line_table", "candidate_score_table"}:
        return "scores"
    if kind in {"scores", "candidate_scores"}:
        return "scores"
    if data_type == "review_candidate_list" or kind == "review_candidates":
        return "reviews"
    return "other"


def _iter_imported_score_rows(province: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        _normalize_imported_score_line(row)
        for row in list_imported_score_lines(province=province, limit=100000)
    )
    rows.extend(
        _normalize_imported_candidate_score(row)
        for row in list_imported_candidate_scores(province=province, limit=100000)
    )
    return rows


def _normalize_imported_score_line(row: dict[str, Any]) -> dict[str, Any]:
    province = _friendly_province(row.get("province"))
    year = _optional_int(row.get("year")) or DEFAULT_DATA_YEAR
    region = str(row.get("region") or province).strip()
    position_name = str(
        row.get("job_name")
        or row.get("major_category")
        or row.get("section_title")
        or row.get("unit_name")
        or "未命名岗位"
    ).strip()
    return {
        "year": year,
        "province": province,
        "city": region,
        "region": region,
        "address": str(row.get("address") or row.get("work_address") or region).strip(),
        "department": str(row.get("section_title") or "").strip(),
        "unit": str(row.get("unit_name") or "").strip(),
        "unit_name": str(row.get("unit_name") or "").strip(),
        "section_title": str(row.get("section_title") or "").strip(),
        "position_name": position_name,
        "position_code": _normalize_position_code(row.get("job_code")),
        "min_interview_score": _optional_float(row.get("min_score")),
        "max_interview_score": _optional_float(row.get("max_score")),
        "interview_count": _optional_int(row.get("interview_count")),
        "source_description": _friendly_dataset_title(
            province=province,
            year=year,
            kind="scores",
            imported=True,
        ),
        "data_status": "导入数据库",
        "storage": "database",
        "source_kind": str(row.get("source_kind") or "imported"),
        "source_file": str(row.get("source_file") or "").strip(),
        "source_sheet": str(row.get("source_sheet") or "").strip(),
        "data_type": "score_line_table",
        "score_record_type": "score_line",
        "score_label": "最低进面分",
        "is_min_score_reference": True,
        "target_table": "exam_score_lines",
    }


def _normalize_imported_candidate_score(row: dict[str, Any]) -> dict[str, Any]:
    province = _friendly_province(row.get("province"))
    year = _optional_int(row.get("year")) or DEFAULT_DATA_YEAR
    region = str(row.get("region") or province).strip()
    return {
        "year": year,
        "province": province,
        "city": region,
        "region": region,
        "address": str(row.get("address") or row.get("work_address") or region).strip(),
        "department": str(row.get("unit_name") or "").strip(),
        "unit": str(row.get("unit_name") or "").strip(),
        "unit_name": str(row.get("unit_name") or "").strip(),
        "section_title": str(row.get("section_title") or row.get("group_name") or "").strip(),
        "position_name": str(row.get("job_name") or row.get("group_name") or "成绩汇总记录").strip(),
        "position_code": _normalize_position_code(row.get("job_code")),
        "min_interview_score": None,
        "max_interview_score": None,
        "interview_count": None,
        "candidate_no": str(row.get("candidate_no") or "").strip(),
        "candidate_name": str(row.get("candidate_name") or "").strip(),
        "written_score": _optional_float(row.get("written_score")),
        "interview_score": _optional_float(row.get("interview_score")),
        "total_score": _optional_float(row.get("total_score")),
        "rank": _optional_int(row.get("rank")),
        "source_description": _friendly_dataset_title(
            province=province,
            year=year,
            kind="candidate_scores",
            imported=True,
        ),
        "data_status": "候选人成绩样本，不是岗位最低进面线",
        "storage": "database",
        "source_kind": str(row.get("source_kind") or "imported"),
        "source_file": str(row.get("source_file") or "").strip(),
        "source_sheet": str(row.get("source_sheet") or "").strip(),
        "data_type": "candidate_score_table",
        "score_record_type": "candidate_score",
        "score_label": "候选人成绩",
        "is_min_score_reference": False,
        "target_table": "exam_candidate_scores",
    }


def _normalize_score_row(row: dict[str, Any], fallback_province: str) -> dict[str, Any]:
    province = str(row.get("region") or fallback_province).strip()
    year = _optional_int(row.get("year")) or DEFAULT_DATA_YEAR
    position_name = str(
        row.get("position_name")
        or row.get("position_type")
        or row.get("position")
        or "未命名岗位"
    ).strip()
    return {
        "year": year,
        "province": province,
        "city": str(row.get("city") or "").strip(),
        "region": str(row.get("city") or row.get("region") or "").strip(),
        "address": str(row.get("address") or row.get("work_address") or row.get("city") or "").strip(),
        "department": str(row.get("department") or "").strip(),
        "unit": str(row.get("unit") or "").strip(),
        "unit_name": str(row.get("unit_name") or row.get("unit") or "").strip(),
        "section_title": str(row.get("section_title") or "").strip(),
        "position_name": position_name,
        "position_code": _normalize_position_code(row.get("position_code")),
        "min_interview_score": _optional_float(
            row.get("min_interview_score") or row.get("min_score")
        ),
        "max_interview_score": _optional_float(
            row.get("max_interview_score") or row.get("max_score")
        ),
        "interview_count": _optional_int(row.get("interview_count")),
        "source_description": _friendly_dataset_title(
            province=province,
            year=year,
            kind="scores",
        ),
        "data_status": str(row.get("data_status") or "参考").strip(),
        "storage": "csv",
        "source_kind": "builtin",
        "source_file": "",
        "data_type": "score_line_table",
        "score_record_type": "score_line",
        "score_label": "最低进面分",
        "is_min_score_reference": True,
    }


def _score_row_matches(
    row: dict[str, Any],
    keyword: str,
    position_code: str,
    min_score: float | None,
    max_score: float | None,
) -> bool:
    if position_code and _normalize_position_code(row.get("position_code")) != position_code:
        return False

    if keyword:
        searchable = _normalize_search_text(
            " ".join(
                str(row.get(field) or "")
                for field in [
                    "position_name",
                    "department",
                    "unit",
                    "unit_name",
                    "city",
                    "region",
                    "address",
                    "section_title",
                ]
            )
        )
        if keyword not in searchable:
            return False

    score = row.get("min_interview_score")
    if min_score is not None and (score is None or score < min_score):
        return False
    if max_score is not None and (score is None or score > max_score):
        return False
    return True


def _friendly_dataset_title(
    province: str,
    year: int,
    kind: str,
    imported: bool = False,
) -> str:
    suffixes = {
        "jobs": "公务员考试职位表",
        "scores": "公务员考试进面分数参考",
        "candidate_scores": "公务员考试成绩汇总参考",
    }
    suffix = suffixes.get(kind, "公务员考试招考数据")
    imported_suffix = "（导入数据库）" if imported else ""
    return f"{year} 年{province}{suffix}{imported_suffix}"


def _friendly_province(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return get_province_name(text) or detect_province_in_text(text).get("province") or text


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def _normalize_search_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).lower()


def _normalize_position_code(value: Any) -> str:
    text = str(value or "").strip()
    digit_groups = re.findall(r"\d+", text)
    if not digit_groups:
        return text
    code = max(enumerate(digit_groups), key=lambda item: (len(item[1]), item[0]))[1]
    return code if len(code) >= 6 else ""


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
