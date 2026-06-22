import csv
import re
from difflib import SequenceMatcher
from pathlib import Path

from app.db.import_repository import (
    list_imported_candidate_scores,
    list_imported_score_lines,
)
from app.tools.province_registry import (
    DEFAULT_DATA_YEAR,
    detect_province_in_text,
    get_province_name,
    legacy_scores_csv_path,
    list_available_job_csvs,
    resolve_requested_province,
    scores_csv_path,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SCORES_DATA_DIR = DATA_DIR / "scores"
HIGH_CONFIDENCE_SCORE_MATCH_TYPES = {
    "exact_position_code",
    "partial_position_code",
    "fuzzy_high_confidence",
}

POSITION_ALIASES = {
    "信息技术岗": ["信息技术岗", "信息化管理岗", "信息中心岗", "系统运维岗"],
    "数据管理岗": ["数据管理岗", "数据治理岗", "数字政务岗"],
    "数字政务岗": ["数字政务岗", "信息化管理岗", "数据管理岗"],
    "基层综合岗": ["基层综合岗", "综合管理岗"],
    "窗口服务岗": ["窗口服务岗"],
    "信息中心岗": ["信息中心岗", "信息技术岗", "系统运维岗"],
    "系统运维岗": ["系统运维岗", "信息技术岗", "信息中心岗"],
    "网络安全岗": ["网络安全岗", "信息技术岗"],
}
AMBIGUOUS_SINGLE_SCORE_MESSAGE = "找到多个相似岗位，请补充职位代码、用人单位或完整岗位名称。"


def search_scores(
    target: str,
    exam_type: str,
    region: str,
    major: str,
    matched_jobs: list[dict] | None = None,
) -> list[dict]:
    """从 CSV 中检索分数线参考。

    分数线必须先按 target、exam_type、region 隔离，再按职位代码或岗位类别匹配。
    """
    scores = _read_scores(region=region)
    matched_jobs = matched_jobs or []
    scoped_scores = [
        score
        for score in scores
        if _match_target(target, score["target"])
        and (
            not _requires_exam_type_filter(target)
            or _match_exam_type(exam_type, score.get("exam_type", ""))
        )
        and _match_region(region, score["region"])
    ]

    if matched_jobs:
        results = []
        seen_keys: set[str] = set()
        for job in matched_jobs:
            match = _best_score_match_for_job(job, scoped_scores)
            if not match:
                continue
            key = match.get("score_id") or "|".join(
                str(match.get(field, ""))
                for field in ["position_code", "department", "unit", "position_name", "year"]
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            results.append(match)

        _log_score_match_results(
            region=_normalize_region(region),
            exam_type=_normalize_exam_type(exam_type),
            position_codes=_build_position_codes(matched_jobs),
            matched_scores=results,
        )
        results.sort(
            key=lambda item: (
                item.get("year") or 0,
                item.get("score_match_confidence") or 0,
                item.get("min_interview_score") or item.get("min_score") or 0,
            ),
            reverse=True,
        )
        return results[:8]

    position_keywords = _build_position_keywords(major, matched_jobs)
    position_codes = _build_position_codes(matched_jobs)
    normalized_region = _normalize_region(region)
    normalized_exam_type = _normalize_exam_type(exam_type)

    exact_position_results = []
    strict_results = []
    fallback_results = []

    for score in scoped_scores:
        fallback_results.append(score)
        match_type = _match_position_code_set(score.get("position_code"), position_codes)
        if match_type:
            exact_position_results.append(
                _score_with_match_metadata(
                    score,
                    match_type=match_type,
                    confidence=1.0 if match_type == "exact_position_code" else 0.92,
                    reason=_score_code_match_reason(match_type, "", score.get("position_code", "")),
                )
            )
            continue
        if _match_position_type(score["position_type"], position_keywords):
            strict_results.append(
                _score_with_match_metadata(
                    score,
                    match_type="similar_reference",
                    confidence=0.65,
                    reason="同类岗位参考，不是该岗位历史进面分",
                )
            )

    _log_score_match_results(
        region=normalized_region,
        exam_type=normalized_exam_type,
        position_codes=position_codes,
        matched_scores=exact_position_results,
    )

    results = exact_position_results or strict_results or fallback_results

    # 先看年份较新的数据；同一年里最低进面分较高的岗位更能提示竞争压力。
    results.sort(
        key=lambda item: (
            item.get("year") or 0,
            item.get("min_interview_score") or item.get("min_score") or 0,
        ),
        reverse=True,
    )
    return results[:8]


def find_single_score_reference(
    target: str,
    exam_type: str,
    region: str,
    query: str,
    city: str = "",
) -> dict:
    """按单岗位查询语义定位一条分数线记录。"""
    scoped_scores = [
        score
        for score in _read_scores(region=region)
        if _is_min_score_reference(score)
        if _match_single_score_scope(
            score=score,
            target=target,
            exam_type=exam_type,
            region=region,
            city=city,
        )
    ]
    normalized_query = _normalize_lookup_text(query)
    requested_code = _extract_position_code(query)

    if requested_code:
        code_matches = [
            score
            for score in scoped_scores
            if _normalize_position_code(score.get("position_code")) == requested_code
        ]
        if code_matches:
            return _single_score_found(code_matches[0], "code_exact")
        return {
            "status": "not_found",
            "score": None,
            "match_type": "",
            "message": "",
        }

    exact_name_matches = [
        score for score in scoped_scores if _single_score_position_exact(score, normalized_query)
    ]
    if len(exact_name_matches) == 1:
        return _single_score_found(exact_name_matches[0], "position_exact")

    joint_matches = [
        score
        for score in (exact_name_matches or scoped_scores)
        if _single_score_joint_match(score, normalized_query)
    ]
    if len(joint_matches) == 1:
        return _single_score_found(joint_matches[0], "unit_position_exact")
    if len(joint_matches) > 1 or len(exact_name_matches) > 1:
        return _single_score_ambiguous()

    approximate_matches = _find_approximate_single_scores(scoped_scores, normalized_query)
    if len(approximate_matches) == 1:
        return _single_score_found(approximate_matches[0]["score"], "position_fuzzy")
    if len(approximate_matches) > 1:
        return _single_score_ambiguous()

    return {
        "status": "not_found",
        "score": None,
        "match_type": "",
        "message": "",
    }


def attach_scores_to_jobs(matched_jobs: list[dict], score_references: list[dict]) -> None:
    """只有职位代码精确命中时，才把最低进面分回填到岗位卡片。"""
    for job in matched_jobs:
        job_position_code = _select_position_code(
            job.get("display_position_code"),
            job.get("full_position_code"),
            job.get("position_code"),
            job.get("raw_position_code"),
            job.get("source_position_code"),
            job.get("job_id"),
        )
        _set_job_position_code_fields(job, job_position_code)
        _set_no_score_match(job)

        score = _best_score_match_for_job(job, score_references)
        if (
            not score
            or not _is_min_score_reference(score)
            or score.get("score_match_type") not in HIGH_CONFIDENCE_SCORE_MATCH_TYPES
        ):
            continue

        score_position_code = _select_position_code(
            score.get("display_position_code"),
            score.get("full_position_code"),
            score.get("position_code"),
            score.get("matched_position_code"),
            score.get("score_id"),
        )
        display_position_code = _select_position_code(job_position_code, score_position_code)
        _set_job_position_code_fields(job, display_position_code)
        job["score_match_position_code"] = score_position_code
        job["matched_position_code"] = score_position_code
        min_score = score.get("min_interview_score") or score.get("min_score")
        if min_score is not None and job.get("min_interview_score") is None:
            job["min_interview_score"] = min_score
        if min_score is not None:
            job["min_score"] = min_score
        max_score = score.get("max_interview_score") or score.get("max_score")
        if max_score is not None and job.get("max_interview_score") is None:
            job["max_interview_score"] = max_score
        if max_score is not None:
            job["max_score"] = max_score
        avg_score = score.get("avg_score")
        if avg_score is not None:
            job["avg_score"] = avg_score
        if score.get("interview_count") is not None:
            job["interview_count"] = score["interview_count"]
        if score.get("recruit_count") is not None:
            job["recruit_count"] = score["recruit_count"]
            job["headcount"] = score["recruit_count"]
        job["score_source_type"] = "score_line"
        if score.get("data_status"):
            job["score_data_status"] = score["data_status"]
        job["score_match_type"] = score.get("score_match_type") or "no_match"
        job["score_source_file"] = score.get("score_source_file") or ""
        job["score_source_year"] = score.get("score_source_year") or score.get("year") or 0
        job["score_match_confidence"] = score.get("score_match_confidence")
        job["score_match_reason"] = score.get("score_match_reason") or ""
        score_position_name = str(score.get("position_name") or "").strip()
        current_position_name = str(
            job.get("position_name") or job.get("position") or ""
        ).strip()
        if (
            job.get("score_match_type") == "exact_position_code"
            and score_position_name
            and (not current_position_name or current_position_name.isdigit())
        ):
            job["position_name"] = score_position_name


def _best_score_match_for_job(job: dict, scores: list[dict]) -> dict | None:
    scoped_scores = [
        score
        for score in scores
        if _is_min_score_reference(score) and _same_scope(job, score)
    ]
    if not scoped_scores:
        return None

    job_code = _select_position_code(
        job.get("display_position_code"),
        job.get("full_position_code"),
        job.get("position_code"),
        job.get("raw_position_code"),
        job.get("source_position_code"),
        job.get("job_id"),
    )
    if job_code:
        exact_matches = [
            score
            for score in scoped_scores
            if _normalize_position_code(score.get("position_code")) == job_code
        ]
        if exact_matches:
            return _score_with_match_metadata(
                exact_matches[0],
                match_type="exact_position_code",
                confidence=1.0,
                reason=_score_code_match_reason(
                    "exact_position_code",
                    job_code,
                    exact_matches[0].get("position_code", ""),
                ),
            )

        partial_matches = [
            score
            for score in scoped_scores
            if _is_partial_position_code_match(
                job_code,
                _normalize_position_code(score.get("position_code")),
            )
        ]
        if len(partial_matches) == 1:
            return _score_with_match_metadata(
                partial_matches[0],
                match_type="partial_position_code",
                confidence=0.92,
                reason=_score_code_match_reason(
                    "partial_position_code",
                    job_code,
                    partial_matches[0].get("position_code", ""),
                ),
            )

    fuzzy_candidates = []
    for score in scoped_scores:
        confidence = _fuzzy_score_match_confidence(job, score)
        if confidence >= 0.88:
            fuzzy_candidates.append((confidence, score))

    if not fuzzy_candidates:
        return None

    fuzzy_candidates.sort(key=lambda item: item[0], reverse=True)
    best_confidence, best_score = fuzzy_candidates[0]
    if len(fuzzy_candidates) > 1 and best_confidence - fuzzy_candidates[1][0] < 0.03:
        return None

    return _score_with_match_metadata(
        best_score,
        match_type="fuzzy_high_confidence",
        confidence=round(best_confidence, 2),
        reason="单位、岗位名称、省份和年份组合高置信度匹配",
    )


def _match_position_code_set(score_code: str, job_codes: set[str]) -> str:
    normalized_score_code = _normalize_position_code(score_code)
    if not normalized_score_code:
        return ""
    if normalized_score_code in job_codes:
        return "exact_position_code"
    if any(_is_partial_position_code_match(job_code, normalized_score_code) for job_code in job_codes):
        return "partial_position_code"
    return ""


def _is_partial_position_code_match(job_code: str, score_code: str) -> bool:
    job_code = _normalize_position_code(job_code)
    score_code = _normalize_position_code(score_code)
    if not job_code or not score_code or job_code == score_code:
        return False
    if min(len(job_code), len(score_code)) < 2:
        return False
    return job_code.endswith(score_code) or score_code.endswith(job_code)


def _score_with_match_metadata(
    score: dict,
    match_type: str,
    confidence: float,
    reason: str,
) -> dict:
    result = dict(score)
    result["score_match_type"] = match_type
    result["score_source_file"] = result.get("score_source_file") or ""
    result["score_source_year"] = result.get("score_source_year") or result.get("year") or 0
    result["score_match_confidence"] = confidence
    result["score_match_reason"] = reason
    matched_position_code = _select_complete_position_code(
        result.get("display_position_code"),
        result.get("full_position_code"),
        result.get("position_code"),
        result.get("score_id"),
    )
    result["matched_position_code"] = matched_position_code
    result["display_position_code"] = matched_position_code
    result["full_position_code"] = matched_position_code
    return result


def _score_code_match_reason(match_type: str, job_code: str, score_code: str) -> str:
    job_code = _normalize_position_code(job_code)
    score_code = _normalize_position_code(score_code)
    if match_type == "exact_position_code":
        return f"职位代码 {job_code or score_code} 精确匹配"
    return f"职位代码 {job_code or '岗位表代码'} 与分数线代码 {score_code or '空'} 局部匹配"


def _set_no_score_match(job: dict) -> None:
    job["score_match_type"] = "no_match"
    job["score_source_file"] = ""
    job["score_source_year"] = 0
    job["score_match_confidence"] = None
    job["score_match_position_code"] = ""
    job["matched_position_code"] = ""
    code = _select_position_code(
        job.get("display_position_code"),
        job.get("full_position_code"),
        job.get("position_code"),
        job.get("raw_position_code"),
        job.get("source_position_code"),
        job.get("job_id"),
    )
    region = job.get("region") or "当前地区"
    job["score_match_reason"] = (
        f"{region}分数线中未找到职位代码 {code} 对应记录"
        if code
        else f"{region}分数线中未找到可与该岗位精确对应的记录"
    )


def _fuzzy_score_match_confidence(job: dict, score: dict) -> float:
    job_code = _normalize_position_code(job.get("position_code") or job.get("job_id"))
    score_code = _normalize_position_code(score.get("position_code"))
    if job_code and score_code and not _is_partial_position_code_match(job_code, score_code):
        return 0.0

    job_year = _optional_int(job.get("year"))
    score_year = _optional_int(score.get("year"))
    if job_year and score_year and job_year != score_year:
        return 0.0

    job_department = _normalize_lookup_text(job.get("department", ""))
    score_department = _normalize_lookup_text(score.get("department", ""))
    job_unit = _normalize_lookup_text(job.get("unit", ""))
    score_unit = _normalize_lookup_text(score.get("unit", ""))
    job_position = _normalize_lookup_text(job.get("position", ""))
    score_position = _normalize_lookup_text(score.get("position_name") or score.get("position_type", ""))
    job_text = _normalize_lookup_text(
        " ".join([job.get("department", ""), job.get("unit", ""), job.get("position", "")])
    )
    score_text = _normalize_lookup_text(
        " ".join([score.get("department", ""), score.get("unit", ""), score.get("position_name", "")])
    )

    department_similarity = _text_similarity(job_department, score_department)
    unit_similarity = _text_similarity(job_unit, score_unit)
    position_similarity = _text_similarity(job_position, score_position)
    combined_similarity = _text_similarity(job_text, score_text)

    confidence = max(
        combined_similarity,
        (department_similarity * 0.35) + (unit_similarity * 0.35) + (position_similarity * 0.3),
    )
    return confidence


def _single_score_found(score: dict, match_type: str) -> dict:
    return {
        "status": "found",
        "score": dict(score),
        "match_type": match_type,
        "message": "",
    }


def _single_score_ambiguous() -> dict:
    return {
        "status": "ambiguous",
        "score": None,
        "match_type": "",
        "message": AMBIGUOUS_SINGLE_SCORE_MESSAGE,
    }


def _match_single_score_scope(
    score: dict,
    target: str,
    exam_type: str,
    region: str,
    city: str = "",
) -> bool:
    if target and not _match_target(target, score.get("target", "")):
        return False
    if _requires_exam_type_filter(target) and not _match_exam_type(
        exam_type,
        score.get("exam_type", ""),
    ):
        return False
    if region and not _match_region(region, score.get("region", "")):
        return False

    normalized_city = _normalize_city(city)
    if normalized_city and normalized_city != _normalize_city(score.get("city", "")):
        search_text = _normalize_lookup_text(
            " ".join(
                [
                    score.get("city", ""),
                    score.get("department", ""),
                    score.get("unit", ""),
                    score.get("notes", ""),
                ]
            )
        )
        if _normalize_lookup_text(normalized_city) not in search_text:
            return False

    return True


def _single_score_position_exact(score: dict, normalized_query: str) -> bool:
    position_name = _normalize_lookup_text(score.get("position_name") or score.get("position_type"))
    return bool(position_name and (normalized_query == position_name or position_name in normalized_query))


def _single_score_joint_match(score: dict, normalized_query: str) -> bool:
    position_name = _normalize_lookup_text(score.get("position_name") or score.get("position_type"))
    if not position_name or position_name not in normalized_query:
        return False

    unit_texts = [score.get("department", ""), score.get("unit", "")]
    return any(
        unit
        and (
            _normalize_lookup_text(unit) in normalized_query
            or normalized_query in _normalize_lookup_text(f"{unit}{score.get('position_name', '')}")
        )
        for unit in unit_texts
    )


def _find_approximate_single_scores(scores: list[dict], normalized_query: str) -> list[dict]:
    if not normalized_query:
        return []

    scored: list[dict] = []
    for score in scores:
        position_name = _normalize_lookup_text(score.get("position_name") or score.get("position_type"))
        unit_position = _normalize_lookup_text(f"{score.get('unit') or score.get('department', '')}{score.get('position_name', '')}")
        similarity = max(
            _text_similarity(normalized_query, position_name),
            _text_similarity(normalized_query, unit_position),
        )
        if similarity >= 0.72:
            scored.append({"score": score, "score_value": similarity})

    scored.sort(key=lambda item: item["score_value"], reverse=True)
    if not scored:
        return []

    best_score = scored[0]["score_value"]
    close_matches = [item for item in scored if best_score - item["score_value"] <= 0.04]
    if len(close_matches) > 1:
        return close_matches
    return scored[:1]


def _text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0
    if left == right:
        return 1
    if right in left or left in right:
        return 0.9
    return SequenceMatcher(None, left, right).ratio()


def _extract_position_code(text: str) -> str:
    value = str(text or "")
    contextual_match = re.search(
        r"(?:职位代码|岗位代码|职位编号|岗位编号|position_code)\D{0,12}(\d{6,20})",
        value,
        flags=re.IGNORECASE,
    )
    if contextual_match:
        return _normalize_position_code(contextual_match.group(1))

    prefixed_match = re.search(r"\b[A-Z]{2,}\d{4}[-_]?(\d{6,20})\b", value, flags=re.IGNORECASE)
    if prefixed_match:
        return _normalize_position_code(prefixed_match.group(1))

    standalone_match = re.search(r"(?<!\d)(\d{6,20})(?!\d)", value)
    return _normalize_position_code(standalone_match.group(1)) if standalone_match else ""


def _normalize_lookup_text(text: str) -> str:
    return re.sub(r"[\s,，;；:：。.\-_/（）()【】\[\]“”\"'、]+", "", str(text or "").strip())


def _read_scores(
    region: str = "",
    year: int = DEFAULT_DATA_YEAR,
) -> list[dict]:
    """Read SQLite first and use bundled CSVs only for legacy compatibility."""
    requested_province = resolve_requested_province(region=region)
    requested_slug = requested_province.get("slug", "")
    db_scores = _read_scores_from_database(region=region)
    if requested_slug:
        if db_scores:
            return db_scores
        score_path = _first_existing_path(
            scores_csv_path(requested_slug, year),
            legacy_scores_csv_path(requested_slug, year),
        )
        if not score_path:
            return []
        return _read_scores_from_csv(
            path=score_path,
            defaults=_score_defaults(
                province=requested_province.get("province") or get_province_name(requested_slug),
                year=year,
            ),
        )

    if db_scores:
        return db_scores

    # Compatibility only: CSV remains available until the seed migration has
    # run, but it is not mixed into the formal database query result.
    scores: list[dict] = []
    for slug, _jobs_path in list_available_job_csvs(year):
        score_path = scores_csv_path(slug, year)
        if not score_path.exists():
            continue
        scores.extend(
            _read_scores_from_csv(
                path=score_path,
                defaults=_score_defaults(
                    province=get_province_name(slug),
                    year=year,
                ),
            )
        )
    return _dedupe_score_sources(scores)


def _read_scores_from_database(region: str = "") -> list[dict]:
    requested_province = resolve_requested_province(region=region)
    province = requested_province.get("province") if requested_province.get("slug") else ""
    rows: list[dict] = []
    rows.extend(
        _normalize_imported_score_line(row)
        for row in list_imported_score_lines(province=province or "", limit=100000)
    )
    rows.extend(
        _normalize_imported_candidate_score(row)
        for row in list_imported_candidate_scores(province=province or "", limit=100000)
    )
    return rows


def _normalize_imported_score_line(row: dict) -> dict:
    year = _optional_int(row.get("year")) or DEFAULT_DATA_YEAR
    province = get_province_name(str(row.get("province") or "")) or str(row.get("province") or "")
    defaults = _score_defaults(province=province, year=year)
    return _normalize_score_row(
        row={
            "score_id": f"db-score-line-{row.get('id')}",
            "year": year,
            "target": "公务员",
            "exam_type": _imported_tool_exam_type(row.get("exam_type")),
            "region": province,
            "city": row.get("region") or "",
            "department": row.get("section_title") or "",
            "unit": row.get("unit_name") or "",
            "position_name": row.get("job_name") or row.get("major_category") or row.get("section_title") or "",
            "position_type": row.get("major_category") or row.get("job_name") or "",
            "position_code": row.get("job_code") or "",
            "recruit_count": row.get("recruit_count"),
            "interview_count": row.get("interview_count"),
            "min_score": row.get("min_score"),
            "max_score": row.get("max_score"),
            "avg_score": row.get("avg_score"),
            "source_type": _database_source_label(row.get("source_kind")),
            "data_status": "历史进面分参考",
            "source_kind": row.get("source_kind") or "imported",
            "storage": "database",
            "score_source_file": "",
            "score_source_year": year,
            "data_type": "score_line_table",
            "score_record_type": "score_line",
            "score_label": "最低进面分",
            "is_min_score_reference": True,
        },
        defaults=defaults,
        fallback_score_id=f"db-score-line-{row.get('id')}",
    )


def _normalize_imported_candidate_score(row: dict) -> dict:
    year = _optional_int(row.get("year")) or DEFAULT_DATA_YEAR
    province = get_province_name(str(row.get("province") or "")) or str(row.get("province") or "")
    defaults = _score_defaults(province=province, year=year)
    return _normalize_score_row(
        row={
            "score_id": f"db-candidate-score-{row.get('id')}",
            "year": year,
            "target": "公务员",
            "exam_type": _imported_tool_exam_type(row.get("exam_type")),
            "region": province,
            "city": row.get("region") or "",
            "department": row.get("unit_name") or "",
            "unit": row.get("unit_name") or "",
            "position_name": row.get("job_name") or row.get("group_name") or "成绩汇总记录",
            "position_type": row.get("group_name") or "候选人成绩",
            "position_code": row.get("job_code") or "",
            "recruit_count": row.get("recruit_count"),
            "min_score": None,
            "avg_score": None,
            "candidate_no": row.get("candidate_no") or "",
            "candidate_name": row.get("candidate_name") or "",
            "written_score": row.get("written_score"),
            "interview_score": row.get("interview_score"),
            "total_score": row.get("total_score"),
            "rank": row.get("rank"),
            "source_type": _database_source_label(row.get("source_kind")),
            "data_status": "候选人成绩样本，不是岗位最低进面线",
            "source_kind": row.get("source_kind") or "imported",
            "storage": "database",
            "score_source_file": "",
            "score_source_year": year,
            "data_type": "candidate_score_table",
            "score_record_type": "candidate_score",
            "score_label": "候选人成绩",
            "is_min_score_reference": False,
        },
        defaults=defaults,
        fallback_score_id=f"db-candidate-score-{row.get('id')}",
    )


def _imported_tool_exam_type(value) -> str:
    text = _normalize_text(value)
    if text in {"公务员", "地方公务员"}:
        return "省考"
    return text or "省考"


def _database_source_label(value) -> str:
    source_kind = _normalize_text(value)
    if source_kind == "builtin_seed":
        return "内置种子数据"
    if source_kind == "migrated":
        return "迁移数据"
    return "导入数据库"


def _read_scores_from_csv(path: Path, defaults: dict) -> list[dict]:
    scores = []
    defaults = {
        **defaults,
        "score_source_file": path.relative_to(DATA_DIR.parent).as_posix(),
        "score_source_year": defaults.get("year", ""),
    }
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader, start=1):
            scores.append(
                _normalize_score_row(
                    row=row,
                    defaults=defaults,
                    fallback_score_id=f"{path.stem}-{index}",
                )
            )
    return scores


def _score_defaults(province: str, year: int = DEFAULT_DATA_YEAR) -> dict:
    return {
        "year": str(year),
        "target": "公务员",
        "exam_type": "省考",
        "region": province,
        "source_type": "官方名单",
        "data_status": "参考",
    }


def _normalize_score_row(
    row: dict,
    defaults: dict,
    fallback_score_id: str,
) -> dict:
    """统一广西岗位分数线 CSV 字段。"""
    normalized = {**defaults, **row}
    raw_region = _normalize_text(row.get("region") or defaults.get("region", ""))
    region, city = _split_region_city(raw_region)
    min_interview_score = _optional_float(
        normalized.get("min_interview_score") or normalized.get("min_score")
    )
    max_interview_score = _optional_float(
        normalized.get("max_interview_score") or normalized.get("max_score")
    )

    normalized["score_id"] = _normalize_text(
        normalized.get("score_id") or fallback_score_id
    )
    normalized["year"] = _optional_int(normalized.get("year")) or 0
    normalized["target"] = _normalize_target(normalized.get("target", ""))
    normalized["exam_type"] = _normalize_exam_type(normalized.get("exam_type", ""))
    normalized["region"] = _normalize_region(defaults.get("region") or region)
    normalized["city"] = _normalize_city(normalized.get("city") or city)
    normalized["position_code"] = _normalize_position_code(
        normalized.get("position_code") or normalized.get("job_id")
    )
    normalized["raw_position_code"] = normalized["position_code"]
    display_position_code = _select_complete_position_code(normalized["position_code"])
    normalized["display_position_code"] = display_position_code
    normalized["full_position_code"] = display_position_code
    normalized["matched_position_code"] = display_position_code
    normalized["department"] = _normalize_text(normalized.get("department", ""))
    normalized["unit"] = _normalize_text(normalized.get("unit", ""))
    normalized["position_name"] = _normalize_text(
        normalized.get("position_name") or normalized.get("position", "")
    )
    normalized["position_type"] = _normalize_text(
        normalized.get("position_type") or normalized.get("position_name")
    )
    normalized["recruit_count"] = _optional_int(
        normalized.get("recruit_count") or normalized.get("headcount")
    )
    normalized["interview_count"] = _optional_int(normalized.get("interview_count"))
    normalized["min_interview_score"] = min_interview_score
    normalized["min_score"] = (
        _optional_float(normalized.get("min_score")) or min_interview_score
    )
    normalized["avg_score"] = _optional_float(normalized.get("avg_score"))
    normalized["max_interview_score"] = max_interview_score
    normalized["max_score"] = (
        _optional_float(normalized.get("max_score")) or max_interview_score
    )
    normalized["source_type"] = _normalize_text(normalized.get("source_type", ""))
    normalized["data_status"] = _normalize_text(normalized.get("data_status", ""))
    normalized["notes"] = _normalize_text(normalized.get("notes", ""))
    normalized["score_source_file"] = _normalize_text(normalized.get("score_source_file", ""))
    normalized["score_source_year"] = _optional_int(normalized.get("score_source_year")) or normalized["year"]
    normalized["candidate_no"] = _normalize_text(normalized.get("candidate_no", ""))
    normalized["candidate_name"] = _normalize_text(normalized.get("candidate_name", ""))
    normalized["written_score"] = _optional_float(normalized.get("written_score"))
    normalized["interview_score"] = _optional_float(normalized.get("interview_score"))
    normalized["total_score"] = _optional_float(normalized.get("total_score"))
    normalized["rank"] = _optional_int(normalized.get("rank"))

    return normalized


def _is_min_score_reference(score: dict) -> bool:
    if score.get("is_min_score_reference") is False:
        return False
    return str(score.get("data_type") or "") != "candidate_score_table"


def _match_target(user_target: str, score_target: str) -> bool:
    """判断目标方向是否匹配。"""
    user_target = _normalize_target(user_target)
    score_target = _normalize_target(score_target)
    return bool(user_target and score_target) and (
        user_target in score_target or score_target in user_target
    )


def _requires_exam_type_filter(target: str) -> bool:
    return _normalize_target(target) == "公务员"


def _match_exam_type(user_exam_type: str, score_exam_type: str) -> bool:
    """公务员分数线必须按国考/省考隔离；都看看表示同地区内不限定考试类型。"""
    user_exam_type = _normalize_exam_type(user_exam_type)
    score_exam_type = _normalize_exam_type(score_exam_type)

    if user_exam_type in {"", "都看看"}:
        return True
    return bool(score_exam_type) and user_exam_type == score_exam_type


def _match_region(user_region: str, score_region: str) -> bool:
    """判断地区是否匹配。"""
    user_region = _normalize_region(user_region)
    score_region = _normalize_region(score_region)
    if user_region in {"", "不限", "全部", "不限制", "全国", "全省"}:
        return bool(score_region)
    return bool(user_region and score_region) and user_region == score_region


def _build_position_keywords(major: str, matched_jobs: list[dict]) -> list[str]:
    """根据专业和已匹配岗位生成岗位类别关键词。"""
    keywords: list[str] = []

    for job in matched_jobs:
        position = _normalize_text(job.get("position", ""))
        if position:
            keywords.append(position)

    if _is_information_technology_major(major):
        keywords.extend(
            [
                "信息技术岗",
                "数据管理岗",
                "数字政务岗",
                "信息中心岗",
                "系统运维岗",
                "网络安全岗",
                "信息化管理岗",
            ]
        )

    return _dedupe(keywords)


def _build_position_codes(matched_jobs: list[dict]) -> set[str]:
    return {
        _normalize_position_code(job.get("position_code") or job.get("job_id"))
        for job in matched_jobs
        if _normalize_position_code(job.get("position_code") or job.get("job_id"))
    }


def _log_score_match_results(
    region: str,
    exam_type: str,
    position_codes: set[str],
    matched_scores: list[dict],
) -> None:
    if not position_codes:
        print("匹配失败：推荐岗位缺少 position_code，无法精确关联分数线")
        return

    matched_by_code = {
        score.get("position_code"): score
        for score in matched_scores
        if score.get("position_code")
    }
    for position_code in sorted(position_codes):
        print(
            "正在匹配分数线："
            f"region={region} exam_type={exam_type} position_code={position_code}"
        )
        score = matched_by_code.get(position_code)
        if not score:
            print(f"匹配失败：position_code={position_code}")
            continue
        print(
            "匹配成功："
            f"min_interview_score={score.get('min_interview_score')} "
            f"interview_count={score.get('interview_count')}"
        )


def _match_position_type(position_type: str, keywords: list[str]) -> bool:
    """判断岗位类别是否命中关键词或同类岗位别名。"""
    position_type = _normalize_text(position_type)
    if not keywords:
        return True

    for keyword in keywords:
        if position_type == keyword:
            return True
        if position_type in POSITION_ALIASES.get(keyword, []):
            return True
        if keyword in POSITION_ALIASES.get(position_type, []):
            return True

    return False


def _is_information_technology_major(major: str) -> bool:
    """判断专业是否偏信息技术方向。"""
    major = _normalize_text(major)
    keywords = ["软件", "计算机", "网络", "信息", "数据", "人工智能"]
    return any(keyword in major for keyword in keywords)


def _same_scope(job: dict, score: dict) -> bool:
    if not _match_target(job.get("target", ""), score.get("target", "")):
        return False
    if _requires_exam_type_filter(job.get("target", "")) and (
        _normalize_exam_type(job.get("exam_type", ""))
        != _normalize_exam_type(score.get("exam_type", ""))
    ):
        return False
    return _match_region(job.get("region", ""), score.get("region", ""))


def _dedupe(items: list[str]) -> list[str]:
    """按原顺序去重。"""
    results = []
    for item in items:
        if item not in results:
            results.append(item)
    return results


def _normalize_text(text: str) -> str:
    """去掉文本前后空格。"""
    return str(text or "").strip()


def _normalize_position_code(value) -> str:
    """统一职位代码格式，兼容 GX2025-45010027 这类职位表编号。"""
    text = re.sub(r"[\s_#/:：,，;；()（）\[\]【】]+", "", _normalize_text(value))
    if not text:
        return ""
    digit_groups = re.findall(r"\d+", text)
    if digit_groups:
        return max(enumerate(digit_groups), key=lambda item: (len(item[1]), item[0]))[1]
    return text


def _select_position_code(*values) -> str:
    candidates = [_normalize_position_code(value) for value in values]
    return max((code for code in candidates if code), key=len, default="")


def _select_complete_position_code(*values) -> str:
    candidates = [_normalize_position_code(value) for value in values]
    return max(
        (code for code in candidates if re.fullmatch(r"\d{6,20}", code)),
        key=len,
        default="",
    )


def _set_job_position_code_fields(job: dict, position_code: str) -> None:
    code = _normalize_position_code(position_code)
    if not code:
        return
    if not job.get("raw_position_code"):
        job["raw_position_code"] = _normalize_position_code(
            job.get("position_code") or job.get("job_id")
        )
    if not re.fullmatch(r"\d{6,20}", code):
        return
    job["position_code"] = code
    job["display_position_code"] = code
    job["full_position_code"] = code


def _normalize_target(text: str) -> str:
    text = _normalize_text(text)
    aliases = {
        "事业编": "事业单位",
        "事业单位": "事业单位",
        "公务员": "公务员",
        "考研": "考研",
        "国企": "国企",
    }
    return aliases.get(text, text)


def _normalize_exam_type(text: str) -> str:
    text = _normalize_text(text)
    aliases = {
        "省考": "省考",
        "省公务员": "省考",
        "地方公务员": "省考",
        "国考": "国考",
        "国家公务员": "国考",
        "都看看": "都看看",
        "不限": "都看看",
    }
    return aliases.get(text, text)


def _normalize_region(text: str) -> str:
    text = _normalize_text(text)
    province = detect_province_in_text(text).get("province")
    if province:
        return province
    return (
        text.replace("广西壮族自治区", "广西")
        .replace("河北省", "河北")
        .replace("广东省", "广东")
        .replace("省", "")
        .replace("壮族自治区", "")
        .replace("自治区", "")
        .replace("·", "-")
        .replace("/", "-")
        .replace(" ", "")
    )


def _normalize_city(text: str) -> str:
    value = _normalize_text(text).replace("市", "").replace("地区", "")
    if value in {"", "不限", "全部", "不限制", "全省"}:
        return ""
    return value


def _split_region_city(text: str) -> tuple[str, str]:
    value = _normalize_text(text)
    if not value:
        return "", ""

    normalized = value.replace("·", "-").replace("/", "-")
    if "-" in normalized:
        region_part, city_part = normalized.split("-", 1)
        return _normalize_region(region_part), _normalize_city(city_part)

    return _normalize_region(normalized), ""


def _optional_int(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_float(value) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_existing_path(*paths: Path) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def _dedupe_score_sources(scores: list[dict]) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for score in scores:
        key = "|".join(
            str(score.get(field) or "")
            for field in [
                "region",
                "year",
                "position_code",
                "department",
                "unit",
                "position_name",
                "min_interview_score",
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(score)
    return results
