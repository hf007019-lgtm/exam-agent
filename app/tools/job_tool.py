import csv
import re
from difflib import SequenceMatcher
from pathlib import Path

from app.db.import_repository import list_imported_jobs, list_imported_signup_stats
from app.tools.region_resolver import (
    canonical_province,
    infer_job_region,
    is_unlimited_region_value,
    resolve_region,
)
from app.tools.province_registry import (
    DEFAULT_DATA_YEAR,
    get_province_name,
    jobs_csv_path,
    legacy_jobs_csv_path,
    list_available_job_csvs,
    missing_jobs_message,
    resolve_requested_province,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
JOBS_DATA_DIR = DATA_DIR / "jobs"
MAX_RECOMMENDATIONS = 5
AMBIGUOUS_SINGLE_JOB_MESSAGE = "找到多个相似岗位，请补充职位代码、用人单位或完整岗位名称。"

GUANGXI_CITY_NEIGHBORS = {
    "南宁": ["崇左", "钦州", "防城港", "贵港", "来宾"],
    "柳州": ["来宾", "桂林", "河池"],
    "桂林": ["柳州", "贺州"],
    "梧州": ["贺州", "贵港"],
    "北海": ["钦州", "防城港"],
    "防城港": ["南宁", "钦州"],
    "钦州": ["南宁", "北海", "防城港"],
    "贵港": ["南宁", "来宾", "玉林", "梧州"],
    "玉林": ["贵港", "梧州"],
    "百色": ["南宁", "河池", "崇左"],
    "贺州": ["桂林", "梧州"],
    "河池": ["柳州", "来宾", "百色"],
    "来宾": ["南宁", "柳州", "贵港", "河池"],
    "崇左": ["南宁", "百色"],
}

LOCATION_PREFERENCE_KEYWORDS = [
    "附近",
    "周边",
    "离家近",
    "离家近一点",
    "就近",
    "本地",
    "通勤",
    "家在",
]

COMPUTER_RELATED_MAJORS = {
    "软件工程",
    "计算机科学",
    "计算机科学与技术",
    "网络工程",
    "信息安全",
    "数据科学与大数据技术",
    "人工智能",
    "信息管理与信息系统",
    "电子信息工程",
}

RELATED_MAJOR_KEYWORDS = [
    "计算机",
    "软件",
    "信息技术",
    "信息管理",
    "电子信息",
    "网络",
    "数据",
    "人工智能",
    "网络空间安全",
]

HIGH_SUITABILITY_KEYWORDS = [
    "信息技术",
    "信息化",
    "网络安全",
    "数据管理",
    "大数据",
    "电子政务",
    "系统运维",
    "计算机",
    "软件",
    "数据",
    "信息中心",
    "信息工程",
    "信息处理",
    "信息通信",
    "信息保障",
]

MEDIUM_SUITABILITY_KEYWORDS = [
    "统计",
    "审计信息化",
    "电子数据审计",
    "财政信息化",
    "数字化",
    "数据分析",
    "科技信息管理",
    "信息管理",
]

BUSINESS_LINE_KEYWORDS = [
    "统计",
    "审计",
    "水利",
    "水文",
    "财务",
    "会计",
    "文字综合",
    "文秘",
]

NON_TECH_CONTEXT_KEYWORDS = [
    "基层综合管理",
    "基层公安",
    "执法",
    "人民警察",
    "值班执勤",
    "罪犯管教",
]


def search_jobs(
    target: str,
    exam_type: str,
    region: str,
    education: str,
    major: str,
    identity: str,
    city: str = "",
    question: str = "",
    top_n: int = MAX_RECOMMENDATIONS,
    limit: int | None = None,
) -> list[dict]:
    """先执行硬性条件过滤，再为候选岗位评分并返回 Top N 推荐。"""
    recommendations: list[dict] = []
    requested_province = resolve_requested_province(region=region, question=question)
    effective_region = requested_province.get("province") or region
    source_jobs = _read_jobs(region=region, question=question)
    if not source_jobs:
        return [
            _missing_jobs_result(
                province=requested_province.get("province", ""),
                target=target,
                exam_type=exam_type,
            )
        ]

    location_preference = extract_location_preference(
        question=question,
        city=city,
        region=effective_region,
    )

    for source_job in source_jobs:
        if not _match_target(target, source_job.get("target", "")):
            continue
        if _requires_exam_type_filter(target) and not _match_exam_type(
            exam_type,
            source_job.get("exam_type", ""),
        ):
            continue

        region_score = _score_region(effective_region, source_job.get("region", ""))
        if region_score == 0:
            continue

        education_score = _score_education(
            education,
            source_job.get("education_required", ""),
        )
        if education_score == 0:
            continue

        major_score = _score_major(major, source_job.get("major_required", ""))
        if major_score == 0:
            continue

        identity_score = _score_identity(
            identity,
            source_job.get("identity_required", ""),
        )
        if identity_score == 0:
            continue

        job = dict(source_job)
        qualification_score = _calculate_qualification_score(
            region_score=region_score,
            education_score=education_score,
            major_score=major_score,
            identity_score=identity_score,
        )
        suitability = _analyze_suitability(
            user_major=major,
            job=job,
            major_score=major_score,
        )
        suitability_score = suitability["score"]
        competition_score = _optional_int(job.get("competition_score"))
        match_score = _calculate_match_score(
            qualification_score=qualification_score,
            suitability_score=suitability_score,
            competition_score=competition_score,
        )
        match_score = _apply_conservative_match_cap(
            job=job,
            match_score=match_score,
            major_score=major_score,
        )
        location_preference_score, location_preference_reason = (
            _score_location_preference(
                job=job,
                preference=location_preference,
            )
        )

        job["recruit_count"] = int(job.get("headcount") or 0)
        job["applicants_count"] = _optional_int(job.get("applicants_count"))
        job["interview_count"] = _optional_int(job.get("interview_count"))
        job["min_interview_score"] = _optional_float(
            job.get("min_interview_score")
        )
        job["competition_ratio"] = _optional_text(job.get("competition_ratio"))
        job["competition_score"] = competition_score
        job["competition_level"] = (
            _optional_text(job.get("competition_level")) or "未知"
        )
        job["work_location"] = job.get("work_location") or _format_work_location(job)
        job["qualification_score"] = qualification_score
        job["suitability_score"] = suitability_score
        job["match_score"] = match_score
        job["match_level"] = _match_level(match_score)
        job["_ranking_score"] = match_score + location_preference_score
        job["_location_preference_reason"] = location_preference_reason
        job["match_reason"] = _build_match_reason(
            user_region=effective_region,
            user_education=education,
            user_major=major,
            user_identity=identity,
            job=job,
            major_score=major_score,
            region_score=region_score,
            suitability=suitability,
        )
        job["risk_notes"] = _build_risk_notes(
            user_major=major,
            job=job,
            major_score=major_score,
            region_score=region_score,
            suitability=suitability,
        )
        job["verify_notes"] = _build_verify_notes(job)
        job["short_reason"] = _build_short_reason(
            user_major=major,
            job=job,
            major_score=major_score,
            suitability=suitability,
            location_preference_reason=location_preference_reason,
        )
        job["risk_summary"] = _build_risk_summary(
            job=job,
            suitability=suitability,
        )
        job["ai_analysis"] = _build_ai_analysis(
            user_education=education,
            user_major=major,
            user_identity=identity,
            job=job,
            major_score=major_score,
            suitability=suitability,
            location_preference_reason=location_preference_reason,
        )
        recommendations.append(job)

    recommendations.sort(
        key=lambda item: (
            int(item.get("_ranking_score") or 0),
            int(item.get("match_score") or 0),
            int(item.get("suitability_score") or 0),
            int(item.get("qualification_score") or 0),
            int(item.get("headcount") or 0),
            str(item.get("job_id") or ""),
        ),
        reverse=True,
    )
    result_limit = _coerce_result_limit(limit if limit is not None else top_n)
    results = recommendations[:result_limit]
    for job in results:
        job.pop("_ranking_score", None)
        job.pop("_location_preference_reason", None)
    return results


def find_single_job(
    target: str,
    exam_type: str,
    region: str,
    query: str,
    city: str = "",
) -> dict:
    """按用户输入定位单个已知岗位，不做学历、专业、身份过滤。"""
    requested_province = resolve_requested_province(region=region, question=query)
    effective_region = requested_province.get("province") or region
    source_jobs = _read_jobs(region=region, question=query)
    if not source_jobs:
        return {
            "status": "error",
            "job": None,
            "match_type": "",
            "message": missing_jobs_message(requested_province.get("province", "")),
        }

    scoped_jobs = [
        job
        for job in source_jobs
        if _match_single_query_scope(
            job=job,
            target=target,
            exam_type=exam_type,
            region=effective_region,
            city=city,
        )
    ]
    normalized_query = _normalize_lookup_text(query)
    requested_code = _extract_position_code(query)

    if requested_code:
        code_matches = [
            job
            for job in scoped_jobs
            if _select_position_code(
                job.get("position_code"),
                job.get("职位代码"),
                job.get("岗位代码"),
                job.get("job_id"),
            ) == requested_code
        ]
        if code_matches:
            return _single_job_found(code_matches[0], "code_exact")
        return {
            "status": "not_found",
            "job": None,
            "match_type": "",
            "message": "",
        }

    exact_name_matches = [
        job for job in scoped_jobs if _single_job_position_exact(job, normalized_query)
    ]
    if len(exact_name_matches) == 1:
        return _single_job_found(exact_name_matches[0], "position_exact")

    joint_matches = [
        job for job in (exact_name_matches or scoped_jobs) if _single_job_joint_match(job, normalized_query)
    ]
    if len(joint_matches) == 1:
        return _single_job_found(joint_matches[0], "unit_position_exact")
    if len(joint_matches) > 1 or len(exact_name_matches) > 1:
        return _single_job_ambiguous()

    approximate_matches = _find_approximate_single_jobs(scoped_jobs, normalized_query)
    if len(approximate_matches) == 1:
        return _single_job_found(approximate_matches[0]["job"], "position_fuzzy")
    if len(approximate_matches) > 1:
        return _single_job_ambiguous()

    return {
        "status": "not_found",
        "job": None,
        "match_type": "",
        "message": "",
    }


def extract_location_preference(
    question: str,
    city: str = "",
    region: str = "",
) -> dict:
    """从可选城市和用户问题中提取轻量地域偏好。"""
    question_text = _normalize_text(question)
    question_location = resolve_region(question_text)
    filter_city = _normalize_city(city)
    normalized_region = _normalize_region(region)
    question_city = _normalize_city(question_location.get("city", ""))
    question_province = _normalize_region(question_location.get("province", ""))
    focus_city = question_location.get("city") or filter_city
    focus_district = question_location.get("district", "")
    focus_province = question_province or normalized_region
    source = "question" if question_location.get("level") else ("filter" if filter_city else "")
    display_location = (
        _format_display_location(
            province=question_province,
            city=question_city,
            district=focus_district,
        )
        if source == "question"
        else (focus_city or question_province or "")
    )
    conflict_city = (
        filter_city
        if source == "question" and filter_city and question_city and filter_city != question_city
        else ""
    )

    explicit_nearby_requested = bool(
        any(keyword in question_text for keyword in LOCATION_PREFERENCE_KEYWORDS)
        or (focus_city and re.search(rf"离{re.escape(focus_city)}近", question_text))
    )
    nearby_requested = bool(
        (focus_city or focus_province)
        and (
            source == "question"
            or filter_city
            or explicit_nearby_requested
        )
    )

    return {
        "region": normalized_region,
        "province": focus_province,
        "city": focus_city,
        "district": focus_district,
        "display": display_location,
        "matched_alias": question_location.get("matched_alias", ""),
        "level": question_location.get("level", ""),
        "source": source,
        "conflict_city": conflict_city,
        "nearby_requested": nearby_requested,
        "explicit_nearby_requested": explicit_nearby_requested,
        "nearby_cities": (
            GUANGXI_CITY_NEIGHBORS.get(focus_city, [])
            if nearby_requested
            else []
        ),
    }


def _extract_question_location(question: str) -> dict:
    result = resolve_region(question)
    return {
        "city": result.get("city", ""),
        "district": result.get("district", ""),
        "display": result.get("district") or result.get("city") or result.get("province", ""),
    }


def _format_display_location(province: str = "", city: str = "", district: str = "") -> str:
    if city and district:
        return f"{city}{district}"
    return district or city or province


def _single_job_found(job: dict, match_type: str) -> dict:
    return {
        "status": "found",
        "job": dict(job),
        "match_type": match_type,
        "message": "",
    }


def _single_job_ambiguous() -> dict:
    return {
        "status": "ambiguous",
        "job": None,
        "match_type": "",
        "message": AMBIGUOUS_SINGLE_JOB_MESSAGE,
    }


def _match_single_query_scope(
    job: dict,
    target: str,
    exam_type: str,
    region: str,
    city: str = "",
) -> bool:
    if target and not _match_target(target, job.get("target", "")):
        return False
    if _requires_exam_type_filter(target) and not _match_exam_type(
        exam_type,
        job.get("exam_type", ""),
    ):
        return False
    if region and _score_region(region, job.get("region", "")) == 0:
        return False

    normalized_city = _normalize_city(city)
    if normalized_city and normalized_city != _normalize_city(job.get("city", "")):
        search_text = _normalize_lookup_text(
            " ".join(
                [
                    job.get("city", ""),
                    job.get("work_location", ""),
                    job.get("department", ""),
                    job.get("notes", ""),
                ]
            )
        )
        if _normalize_lookup_text(normalized_city) not in search_text:
            return False

    return True


def _single_job_position_exact(job: dict, normalized_query: str) -> bool:
    position = _normalize_lookup_text(job.get("position", ""))
    return bool(position and (normalized_query == position or position in normalized_query))


def _single_job_joint_match(job: dict, normalized_query: str) -> bool:
    position = _normalize_lookup_text(job.get("position", ""))
    if not position or position not in normalized_query:
        return False

    unit_texts = [
        job.get("department", ""),
        job.get("work_location", ""),
        _extract_note_field(job.get("notes", ""), "招录机关"),
        _extract_note_field(job.get("notes", ""), "用人单位"),
    ]
    return any(
        unit
        and (
            _normalize_lookup_text(unit) in normalized_query
            or normalized_query in _normalize_lookup_text(f"{unit}{job.get('position', '')}")
        )
        for unit in unit_texts
    )


def _find_approximate_single_jobs(jobs: list[dict], normalized_query: str) -> list[dict]:
    if not normalized_query:
        return []

    scored: list[dict] = []
    for job in jobs:
        position = _normalize_lookup_text(job.get("position", ""))
        unit_position = _normalize_lookup_text(f"{job.get('department', '')}{job.get('position', '')}")
        score = max(
            _text_similarity(normalized_query, position),
            _text_similarity(normalized_query, unit_position),
        )
        if score >= 0.72:
            scored.append({"job": job, "score": score})

    scored.sort(key=lambda item: item["score"], reverse=True)
    if not scored:
        return []

    best_score = scored[0]["score"]
    close_matches = [item for item in scored if best_score - item["score"] <= 0.04]
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


def _extract_note_field(notes: str, field_name: str) -> str:
    match = re.search(rf"{re.escape(field_name)}[:：]\s*([^；;，,。]+)", str(notes or ""))
    return match.group(1).strip() if match else ""


def _normalize_lookup_text(text: str) -> str:
    return re.sub(r"[\s,，;；:：。.\-_/（）()【】\[\]“”\"'、]+", "", str(text or "").strip())


def _read_jobs(
    region: str = "",
    question: str = "",
    year: int = DEFAULT_DATA_YEAR,
) -> list[dict]:
    """Read SQLite first and use bundled CSVs only for legacy compatibility."""
    requested_province = resolve_requested_province(region=region, question=question)
    requested_slug = requested_province.get("slug", "")
    db_jobs = _read_jobs_from_database(region=region, question=question)
    if requested_slug:
        if db_jobs:
            return db_jobs
        jobs_path = _first_existing_path(
            jobs_csv_path(requested_slug, year),
            legacy_jobs_csv_path(requested_slug, year),
        )
        if not jobs_path or not _csv_has_data_rows(jobs_path):
            return []
        return _read_jobs_from_csv(
            path=jobs_path,
            defaults=_job_defaults(
                province=requested_province.get("province") or get_province_name(requested_slug),
                year=year,
            ),
        )

    if db_jobs:
        return db_jobs

    # Compatibility only: installations that have not run the seed migration
    # may still rely on the bundled CSVs. CSV is not the formal query path.
    jobs: list[dict] = []
    for slug, path in list_available_job_csvs(year):
        jobs.extend(
            _read_jobs_from_csv(
                path=path,
                defaults=_job_defaults(
                    province=get_province_name(slug),
                    year=year,
                ),
            )
        )
    return _dedupe_job_sources(jobs)


def _read_jobs_from_database(
    region: str = "",
    question: str = "",
) -> list[dict]:
    requested_province = resolve_requested_province(region=region, question=question)
    province = requested_province.get("province") if requested_province.get("slug") else ""
    rows = list_imported_jobs(province=province or "", limit=100000)
    signup_by_code = _imported_signup_by_code(
        list_imported_signup_stats(province=province or "", limit=100000)
    )
    return [
        _normalize_imported_job_row(
            row,
            signup=signup_by_code.get(_normalize_position_code(row.get("job_code"))),
        )
        for row in rows
    ]


def _normalize_imported_job_row(row: dict, signup: dict | None = None) -> dict:
    year = _optional_int(row.get("year")) or DEFAULT_DATA_YEAR
    province = get_province_name(str(row.get("province") or "")) or str(row.get("province") or "")
    signup = signup or {}
    defaults = _job_defaults(province=province, year=year)
    return _normalize_job_row(
        {
            "year": year,
            "target": "公务员",
            "exam_type": _imported_tool_exam_type(row.get("exam_type")),
            "region": province or row.get("region"),
            "city": row.get("region") or "",
            "department": row.get("department_name") or row.get("unit_name") or "",
            "unit": row.get("unit_name") or "",
            "unit_name": row.get("unit_name") or "",
            "position": row.get("job_name") or row.get("job_code") or "",
            "position_name": row.get("job_name") or row.get("job_code") or "",
            "job_id": row.get("job_code") or "",
            "position_code": row.get("job_code") or "",
            "major_required": row.get("major_requirement") or "",
            "degree_requirement": row.get("degree_requirement") or "",
            "education_required": row.get("education_requirement") or "",
            "political_requirement": row.get("political_requirement") or "",
            "identity_required": row.get("identity_requirement") or "",
            "grassroots_requirement": row.get("grassroots_requirement") or "",
            "qualification_requirement": row.get("qualification_requirement") or "",
            "job_description": row.get("job_description") or "",
            "contact_phone": row.get("contact_phone") or "",
            "work_address": row.get("work_address") or "",
            "agency_level": row.get("agency_level") or "",
            "is_public_service": row.get("is_public_service"),
            "is_law_enforcement": row.get("is_law_enforcement"),
            "headcount": row.get("recruit_count"),
            "recruit_count": row.get("recruit_count"),
            "applicants_count": signup.get("signup_count"),
            "approved_count": signup.get("approved_count"),
            "payment_count": signup.get("paid_count"),
            "competition_ratio": signup.get("competition_ratio"),
            "remark": row.get("remark") or "",
            "notes": row.get("remark") or "",
            "source_type": _database_source_label(row.get("source_kind")),
            "data_status": "数据库数据",
            "source_kind": row.get("source_kind") or "imported",
            "storage": "database",
            "job_source_file": "",
            "job_source_year": year,
        },
        defaults,
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


def _imported_signup_by_code(rows: list[dict]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in rows:
        code = _normalize_position_code(row.get("job_code"))
        if code and code not in indexed:
            indexed[code] = row
    return indexed


def _read_jobs_from_csv(path: Path, defaults: dict) -> list[dict]:
    defaults = {
        **defaults,
        "job_source_file": path.relative_to(DATA_DIR.parent).as_posix(),
        "job_source_year": defaults.get("year", ""),
    }
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [_normalize_job_row(row, defaults) for row in csv.DictReader(file)]


def _job_defaults(province: str, year: int = DEFAULT_DATA_YEAR) -> dict:
    return {
        "year": str(year),
        "target": "公务员",
        "exam_type": "省考",
        "region": province,
        "source_type": "官方职位表",
        "data_status": "完整",
    }


def _csv_has_data_rows(path: Path) -> bool:
    if not path.exists():
        return False

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return any(True for _ in reader)


def _first_existing_path(*paths: Path) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def _dedupe_job_sources(jobs: list[dict]) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for job in jobs:
        key = "|".join(
            str(job.get(field) or "")
            for field in ["region", "year", "position_code", "department", "unit", "position"]
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(job)
    return results


def _missing_jobs_result(
    province: str = "",
    target: str = "公务员",
    exam_type: str = "省考",
) -> dict:
    message = missing_jobs_message(province)
    display_region = province or ""
    return {
        "data_error": True,
        "job_id": "",
        "position_code": "",
        "display_position_code": "",
        "full_position_code": "",
        "raw_position_code": "",
        "source_position_code": "",
        "year": DEFAULT_DATA_YEAR,
        "target": target,
        "exam_type": exam_type,
        "region": display_region,
        "city": "",
        "department": "数据未就绪",
        "unit": "数据未就绪",
        "position": f"{display_region or '该省份'}职位表数据未导入",
        "education_required": "",
        "major_required": "",
        "identity_required": "",
        "headcount": 0,
        "recruit_count": 0,
        "source_type": "",
        "data_status": "未导入",
        "work_location": display_region,
        "qualification_score": 0,
        "suitability_score": 0,
        "match_score": 0,
        "match_level": "数据缺失",
        "short_reason": message,
        "match_reason": message,
        "risk_summary": message,
        "risk_notes": [message],
        "verify_notes": [message],
        "ai_analysis": {
            "why_recommended": message,
            "qualification_match": message,
            "major_match": message,
            "direction_fit": message,
            "recruit_risk": message,
            "competition_data": message,
            "verify_before_apply": message,
        },
    }


def _build_notes_from_standard_job(row: dict) -> str:
    note_parts = [
        ("招录机关", row.get("department", "")),
        ("用人单位", row.get("unit", "")),
        ("职位简介", row.get("job_description", "")),
        ("职位类别", row.get("position_category", "")),
        ("学位", row.get("degree", "")),
        ("年龄", row.get("age_requirement", "")),
        ("政治面貌", row.get("political_requirement", "")),
        ("基层工作经历", row.get("grassroots_requirement", "")),
        ("应届毕业生", row.get("fresh_graduate_required", "")),
        ("服务基层项目人员", row.get("service_project_required", "")),
        ("人民警察职位", row.get("police_position", "")),
        ("专业测试", row.get("professional_test", "")),
        ("备注", row.get("remark", "")),
    ]
    return "；".join(
        f"{label}：{_normalize_text(value)}"
        for label, value in note_parts
        if _normalize_text(value)
    )


def _identity_from_job_flags(row: dict) -> str:
    fresh_required = _normalize_text(row.get("fresh_graduate_required", ""))
    service_required = _normalize_text(row.get("service_project_required", ""))
    identities = []
    if _looks_required(fresh_required):
        identities.append("应届生")
    if _looks_required(service_required):
        identities.append("服务基层项目人员")
    return "、".join(identities)


def _looks_required(value: str) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    if text in {"否", "不要求", "不限", "无", "否。"}:
        return False
    return "否" not in text


def _normalize_job_row(row: dict, defaults: dict) -> dict:
    """把不同来源职位表统一成 exam_agent 当前需要的岗位字段。"""
    normalized = {**defaults, **row}
    raw_region = _normalize_text(row.get("region") or defaults.get("region", ""))
    region, city = _split_region_city(raw_region)
    default_region = _normalize_region(defaults.get("region", ""))
    raw_job_id = _normalize_text(normalized.get("job_id") or normalized.get("position_code"))
    normalized["position"] = _normalize_text(
        normalized.get("position") or normalized.get("position_name", "")
    )
    normalized["education_required"] = _normalize_text(
        normalized.get("education_required") or normalized.get("education", "")
    )
    normalized["major_required"] = _normalize_text(normalized.get("major_required", ""))
    normalized["identity_required"] = _normalize_text(
        normalized.get("identity_required") or _identity_from_job_flags(normalized)
    )
    normalized["notes"] = _normalize_text(
        normalized.get("notes") or _build_notes_from_standard_job(normalized)
    )

    raw_position_code = _select_position_code(
        normalized.get("raw_position_code"),
        normalized.get("position_code"),
        normalized.get("职位代码"),
        normalized.get("岗位代码"),
        raw_job_id,
    )
    display_position_code = _select_complete_position_code(
        normalized.get("display_position_code"),
        normalized.get("full_position_code"),
        normalized.get("source_position_code"),
        raw_position_code,
    )
    normalized["job_id"] = raw_job_id or display_position_code
    normalized["raw_position_code"] = raw_position_code
    normalized["source_position_code"] = display_position_code
    normalized["position_code"] = display_position_code
    normalized["display_position_code"] = display_position_code
    normalized["full_position_code"] = display_position_code
    normalized["target"] = _normalize_target(normalized.get("target", ""))
    normalized["exam_type"] = _normalize_exam_type(normalized.get("exam_type", ""))
    normalized["region"] = default_region or region
    normalized["city"] = _normalize_city(normalized.get("city") or city)
    normalized["year"] = _optional_int(normalized.get("year")) or 0
    normalized["headcount"] = (
        _optional_int(normalized.get("headcount"))
        or _optional_int(normalized.get("recruit_count"))
        or 0
    )
    normalized["source_type"] = _normalize_text(normalized.get("source_type", ""))
    normalized["data_status"] = _normalize_text(normalized.get("data_status", ""))
    normalized["job_source_file"] = _normalize_text(normalized.get("job_source_file", ""))
    normalized["job_source_year"] = _optional_int(normalized.get("job_source_year")) or normalized["year"]
    normalized["unit"] = _normalize_text(normalized.get("unit", ""))
    normalized["work_location"] = _normalize_text(
        normalized.get("work_location") or raw_region or _format_work_location(normalized)
    )
    inferred_region = infer_job_region(normalized)
    if inferred_region.get("province") and not normalized["region"]:
        normalized["region"] = _normalize_region(inferred_region["province"])
    if inferred_region.get("city") and not normalized["city"]:
        normalized["city"] = _normalize_city(inferred_region["city"])
    normalized["district"] = _normalize_text(
        normalized.get("district") or inferred_region.get("district", "")
    )

    if not normalized["exam_type"] and _normalize_target(normalized.get("target")) == "公务员":
        normalized["exam_type"] = "省考"
    if not normalized["job_id"]:
        normalized["job_id"] = display_position_code

    return normalized


def _score_location_preference(job: dict, preference: dict) -> tuple[int, str]:
    """给自然语言里的城市和就近偏好提供轻量排序加成。"""
    focus_city = preference.get("city", "")
    focus_province = preference.get("province") or preference.get("region", "")
    if not focus_city and not focus_province:
        return 0, ""
    focus_district = preference.get("district", "")
    display_location = preference.get("display") or focus_district or focus_city
    mentioned_location = preference.get("matched_alias") or focus_district or display_location
    explicit_location = preference.get("source") == "question"
    if not focus_city and not explicit_location:
        return 0, ""

    direct_text = " ".join(
        [
            _normalize_text(job.get("region", "")),
            _normalize_text(job.get("city", "")),
            _normalize_text(job.get("district", "")),
            _normalize_text(job.get("work_location", "")),
            _normalize_text(job.get("department", "")),
            _normalize_text(job.get("unit", "")),
        ]
    )
    notes_text = _normalize_text(job.get("notes", ""))
    lookup_text = _normalize_lookup_text(f"{direct_text} {notes_text}")
    nearby_cities = preference.get("nearby_cities", [])
    job_province = _normalize_region(job.get("region", ""))
    same_province = bool(focus_province and job_province == _normalize_region(focus_province))

    if focus_district and _normalize_lookup_text(focus_district) in lookup_text:
        return (
            90,
            f"你提到{mentioned_location}附近，这个岗位就在{focus_district}，地区匹配度高",
        )
    if focus_city and (focus_city in direct_text or focus_city in notes_text):
        reason = (
            f"当前{focus_district}岗位不足，这个岗位在{focus_city}市范围内，属于同市补充推荐"
            if focus_district
            else f"结合你希望靠近{display_location}，这个岗位在{focus_city}范围内，地区匹配度更高"
        )
        return (
            70,
            reason,
        )

    nearby_match = next(
        (candidate for candidate in nearby_cities if candidate in direct_text),
        "",
    )
    if nearby_match:
        return (
            30,
            f"该岗位在{nearby_match}，属于{display_location}周边补充推荐",
        )

    nearby_note_match = next(
        (candidate for candidate in nearby_cities if candidate in notes_text),
        "",
    )
    if nearby_note_match:
        return (
            25,
            f"岗位工作地点范围包含{display_location}周边的{nearby_note_match}",
        )

    if same_province:
        if explicit_location and not focus_city:
            return (
                10,
                f"这个岗位属于{focus_province}范围内，地区条件与用户输入一致",
            )
        target_text = (
            f"{focus_district}及{focus_city}市"
            if focus_district and focus_city
            else (focus_city or focus_province)
        )
        return (
            10,
            f"当前{target_text}岗位不足，这个岗位属于{focus_province}范围内补充推荐，主要因为专业方向匹配",
        )

    if explicit_location:
        return (
            0,
            f"该岗位不在{focus_city or focus_province}，属于补充推荐，主要是因为专业方向匹配",
        )

    return 0, ""


def _calculate_match_score(
    qualification_score: int,
    suitability_score: int,
    competition_score: int | None,
) -> int:
    """有真实竞争分时预留竞争权重，否则沿用当前资格与适配评分。"""
    if competition_score is not None:
        return round(
            qualification_score * 0.35
            + suitability_score * 0.25
            + competition_score * 0.40
        )

    return round(
        qualification_score * 0.65
        + suitability_score * 0.35
    )


def _apply_conservative_match_cap(job: dict, match_score: int, major_score: int) -> int:
    """在缺少竞争数据时保守展示基础匹配度，避免把可报误写成稳妥。"""
    capped_score = int(match_score or 0)
    has_min_score = not _is_missing_competition_value(job.get("min_interview_score"))
    has_ratio = not _is_missing_competition_value(job.get("competition_ratio"))
    has_applicants = not _is_missing_competition_value(job.get("applicants_count"))
    has_payment = not _is_missing_competition_value(job.get("payment_count"))
    recruit_count = int(job.get("recruit_count") or job.get("headcount") or 0)

    if not has_min_score and not has_ratio:
        capped_score = min(capped_score, 75)
    if not any([has_min_score, has_ratio, has_applicants, has_payment]):
        capped_score = min(capped_score, 75)
    if recruit_count == 1 and not has_ratio:
        capped_score = min(capped_score, 70)
    if major_score == 30:
        capped_score = min(capped_score, 82)
    elif major_score == 20:
        capped_score = min(capped_score, 70)

    return max(0, capped_score)


def _is_missing_competition_value(value: object) -> bool:
    return value is None or str(value).strip() in {"", "暂无", "未知", "null", "None"}


def _match_target(user_target: str, job_target: str) -> bool:
    """判断招考类型是否匹配。"""
    user_target = _normalize_target(user_target)
    job_target = _normalize_target(job_target)
    return bool(user_target and job_target) and (
        user_target in job_target or job_target in user_target
    )


def _requires_exam_type_filter(target: str) -> bool:
    return _normalize_target(target) == "公务员"


def _match_exam_type(user_exam_type: str, job_exam_type: str) -> bool:
    """公务员岗位必须按国考/省考隔离；都看看表示同地区内不限定考试类型。"""
    user_exam_type = _normalize_exam_type(user_exam_type)
    job_exam_type = _normalize_exam_type(job_exam_type)

    if user_exam_type in {"", "都看看"}:
        return True
    return bool(job_exam_type) and user_exam_type == job_exam_type


def _score_region(user_region: str, job_region: str) -> int:
    """地区必须在省份字段上匹配，避免跨省或跨考试类型混用数据。"""
    if is_unlimited_region_value(user_region):
        return 10
    user_region = _normalize_region(user_region)
    job_region = _normalize_region(job_region)

    if not user_region or not job_region:
        return 0
    if user_region == job_region:
        return 10
    return 0


def _score_education(user_education: str, required_education: str) -> int:
    """学历满足岗位要求得 15 分，不满足时作为硬性条件淘汰。"""
    if _is_unlimited_filter(user_education):
        return 15
    required_education = _normalize_text(required_education)
    if "不限" in required_education:
        return 15

    user_level = _education_level(user_education)
    required_level = _education_level(required_education)
    return 15 if user_level and user_level >= required_level else 0


def _education_level(text: str) -> int:
    """把学历文本转换为可比较等级。"""
    text = _normalize_text(text)
    if "博士" in text:
        return 50
    if "硕士" in text or "研究生" in text:
        return 40
    if "本科" in text:
        return 30
    if "专科" in text or "大专" in text:
        return 20
    if "不限" in text:
        return 10
    return 0


def _score_major(user_major: str, required_major: str) -> int:
    """专业完全一致 40 分、相关大类 30 分、专业不限 20 分。"""
    user_major = _normalize_text(user_major)
    required_major = _normalize_text(required_major)

    if not user_major or not required_major:
        return 0
    if "不限" in required_major or required_major == "专业不限":
        return 20
    if user_major == required_major or user_major in required_major:
        return 40
    if required_major in user_major and len(required_major) >= 4:
        return 40
    if _is_related_major(user_major, required_major):
        return 30
    return 0


def _score_identity(user_identity: str, required_identity: str) -> int:
    """身份不限或与用户身份一致得 15 分，不一致时淘汰。"""
    if _is_unlimited_filter(user_identity):
        return 15
    user_identity = _normalize_identity(user_identity)
    required_identity = _normalize_identity(required_identity)

    if not required_identity or "不限" in required_identity:
        return 15
    if user_identity == required_identity:
        return 15
    if "应届" in user_identity and "应届" in required_identity:
        return 15
    if "往届" in user_identity and "往届" in required_identity:
        return 15
    return 0


def _calculate_qualification_score(
    region_score: int,
    education_score: int,
    major_score: int,
    identity_score: int,
) -> int:
    """计算资格匹配分，反映硬性条件满足程度。"""
    major_qualification = {
        40: 100,
        30: 85,
        20: 70,
    }.get(major_score, 0)

    return round(
        (100 if region_score else 0) * 0.15
        + (100 if education_score else 0) * 0.20
        + major_qualification * 0.45
        + (100 if identity_score else 0) * 0.20
    )


def _analyze_suitability(
    user_major: str,
    job: dict,
    major_score: int,
) -> dict:
    """分析岗位职责与用户专业方向的适配程度。"""
    role_text = " ".join(
        [
            _normalize_text(job.get("department", "")),
            _normalize_text(job.get("position", "")),
            _normalize_text(job.get("notes", "")),
        ]
    )
    major_text = _normalize_text(job.get("major_required", ""))
    high_matches = _find_keywords(role_text, HIGH_SUITABILITY_KEYWORDS)
    major_high_matches = _find_keywords(major_text, HIGH_SUITABILITY_KEYWORDS)
    medium_matches = _find_keywords(role_text, MEDIUM_SUITABILITY_KEYWORDS)
    business_matches = _find_keywords(role_text, BUSINESS_LINE_KEYWORDS)
    non_tech_context_matches = _find_keywords(role_text, NON_TECH_CONTEXT_KEYWORDS)

    if not _is_information_technology_major(user_major):
        score = {40: 80, 30: 68, 20: 55}.get(major_score, 45)
        return {
            "score": score,
            "high_matches": high_matches,
            "major_high_matches": major_high_matches,
            "medium_matches": medium_matches,
            "business_matches": business_matches,
            "non_tech_context_matches": non_tech_context_matches,
            "pure_business": False,
            "is_it_major": False,
        }

    if high_matches:
        score = 92 + min(8, max(0, len(high_matches) - 1) * 4)
    elif medium_matches:
        score = 66 + min(9, max(0, len(medium_matches) - 1) * 3)
    else:
        score = {40: 50, 30: 45, 20: 38}.get(major_score, 35)

    # 专业要求中的技术关键词只提供小幅加分，避免“能报”替代岗位职责适配判断。
    score += min(4, len(major_high_matches))

    pure_business = bool(business_matches and not high_matches)
    if pure_business:
        score = min(score, 50)
    elif business_matches:
        score -= 20

    if high_matches and non_tech_context_matches:
        score -= min(8, len(non_tech_context_matches) * 4)

    return {
        "score": max(30, min(100, round(score))),
        "high_matches": high_matches,
        "major_high_matches": major_high_matches,
        "medium_matches": medium_matches,
        "business_matches": business_matches,
        "non_tech_context_matches": non_tech_context_matches,
        "pure_business": pure_business,
        "is_it_major": True,
    }


def _match_level(match_score: int) -> str:
    """根据保守后的基础匹配度生成展示等级。"""
    if match_score >= 80:
        return "推荐关注"
    if match_score >= 70:
        return "可报备选"
    if match_score >= 60:
        return "待补充竞争数据"
    return "低匹配"


def _build_match_reason(
    user_region: str,
    user_education: str,
    user_major: str,
    user_identity: str,
    job: dict,
    major_score: int,
    region_score: int,
    suitability: dict,
) -> str:
    """生成区分硬性条件和岗位适配的推荐理由。"""
    has_major_profile = not _is_unlimited_filter(user_major)
    has_education_profile = not _is_unlimited_filter(user_education)
    has_identity_profile = not _is_unlimited_filter(user_identity)

    if major_score == 40 and has_major_profile:
        major_reason = f"岗位专业要求直接包含{user_major}"
    elif major_score == 30 and has_major_profile:
        major_reason = f"{user_major}按相关专业大类满足要求"
    else:
        major_reason = "岗位专业要求为不限专业，专业本身不构成门槛"

    region_reason = (
        f"目标地区与{job.get('region')}一致"
        if region_score == 10
        else f"岗位位于目标省区内的{job.get('region')}"
    )
    identity_required = job.get("identity_required") or "不限"
    if not has_identity_profile:
        identity_reason = "当前身份画像未完善，不能确认是否满足其他身份条件"
    elif "不限" in identity_required:
        identity_reason = f"身份要求不限，当前{user_identity}可以报，但不形成身份限制优势"
    elif "应届" in _normalize_identity(user_identity) and "应届" in _normalize_identity(identity_required):
        identity_reason = "应届身份匹配岗位限制，有一定限制优势"
    else:
        identity_reason = f"身份要求{identity_required}，当前{user_identity}满足"

    education_reason = (
        f"学历要求{job.get('education_required')}，当前{user_education}满足"
        if has_education_profile
        else f"学历要求{job.get('education_required')}，当前学历画像未完善，不能确认是否满足"
    )
    return (
        f"硬性条件：{major_reason}，{education_reason}；{identity_reason}；{region_reason}。"
        f"岗位适配：{_build_suitability_reason(user_major, suitability)}"
    )


def _build_short_reason(
    user_major: str,
    job: dict,
    major_score: int,
    suitability: dict,
    location_preference_reason: str,
) -> str:
    """生成岗位卡片默认展示的一句话推荐理由。"""
    parts: list[str] = []
    if location_preference_reason:
        parts.append(location_preference_reason)

    high_matches = suitability.get("high_matches", [])
    medium_matches = suitability.get("medium_matches", [])
    if high_matches:
        parts.append(
            f"岗位的{'、'.join(high_matches[:2])}方向和{user_major}比较贴近"
        )
    elif medium_matches:
        parts.append(
            f"岗位涉及{'、'.join(medium_matches[:2])}，和{user_major}有一定关联"
        )
    elif major_score == 40:
        parts.append(f"专业要求直接包含{user_major}")
    elif major_score == 30:
        parts.append(f"{user_major}可按相关专业大类初步匹配")
    else:
        parts.append("岗位专业要求为不限专业，专业本身不构成门槛")

    return "，".join(parts[:2]) + "。"


def _build_risk_notes(
    user_major: str,
    job: dict,
    major_score: int,
    region_score: int,
    suitability: dict,
) -> list[str]:
    """生成岗位级风险提醒。"""
    risks: list[str] = []
    notes = _normalize_text(job.get("notes", ""))
    required_major = job.get("major_required", "")

    if major_score == 30:
        risks.append(f"{user_major}按相关专业大类匹配，必须核对官方专业目录和资格审查口径。")
    if suitability.get("is_it_major") and suitability.get("business_matches"):
        risks.append("岗位名称偏业务条线，实际工作可能以统计、审计、水利业务为主，信息技术属性有限。")
        risks.append("虽然专业目录允许报考，但需要结合职位简介确认是否符合个人职业方向。")

    if int(job.get("recruit_count") or job.get("headcount") or 0) == 1:
        risks.append("该岗位仅招录 1 人，结果受报名人数和个体分差影响较大。")
    if job.get("identity_required") not in {"", "不限"}:
        risks.append(f"岗位限制为{job.get('identity_required')}，需确认身份认定材料。")
    if region_score == 5:
        risks.append(f"岗位位于{job.get('region')}，需确认工作地点和异地报考安排。")
    if any(keyword in notes for keyword in ["人民警察", "视力", "体能"]):
        risks.append("该岗位涉及人民警察或体检体能要求，需重点核对录用条件。")
    if "专业笔试" in notes:
        risks.append("该岗位需要专业笔试，备考内容与普通职位不同。")
    if any(keyword in notes for keyword in ["值班", "执勤", "轮岗"]):
        risks.append("岗位备注涉及值班、执勤或轮岗，需评估工作强度。")
    if "基层工作经历" in notes or "基层经历：是" in notes:
        risks.append("岗位可能要求基层工作经历，需核验经历年限和证明材料。")
    if required_major and len(required_major) > 80:
        risks.append("岗位专业要求口径较长，需逐项确认软件工程是否在可报专业范围内。")

    return _dedupe(risks)[:6]


def _build_risk_summary(job: dict, suitability: dict) -> str:
    """生成岗位卡片默认展示的一句话风险提醒。"""
    notes = _normalize_text(job.get("notes", ""))
    recruit_count = int(job.get("recruit_count") or job.get("headcount") or 0)

    if any(keyword in notes for keyword in ["人民警察", "视力", "体能"]):
        police_checks = ["体检和视力要求"]
        if "专业笔试" in notes:
            police_checks.append("专业笔试")
        if any(keyword in notes for keyword in ["值班", "执勤", "轮岗"]):
            police_checks.append("工作强度")
        return f"涉及人民警察录用条件，{'、'.join(police_checks)}都要重点确认。"
    if recruit_count == 1:
        return "只招 1 人，结果更容易受报名人数和进面分波动影响。"
    if _has_incomplete_competition_data(job):
        return "缺少报名人数、竞争比或最低进面分，只能先作为可报备选，待补充竞争数据后再判断。"
    if suitability.get("pure_business") or suitability.get("business_matches"):
        return "岗位可能偏业务条线，报名前要确认实际技术工作占比。"
    if "专业笔试" in notes:
        return "需要专业笔试，备考内容和普通职位不同。"
    if any(keyword in notes for keyword in ["值班", "执勤", "轮岗"]):
        return "岗位涉及值班、执勤或轮岗，需要提前评估工作强度。"

    return "未发现明显额外限制，但最终仍要以最新职位表和资格审查为准。"


def _has_incomplete_competition_data(job: dict) -> bool:
    return any(
        _is_missing_competition_value(job.get(field))
        for field in [
            "applicants_count",
            "payment_count",
            "competition_ratio",
            "min_interview_score",
        ]
    )


def _build_verify_notes(job: dict) -> list[str]:
    """生成报名前必须逐项确认的核验清单。"""
    notes = _normalize_text(job.get("notes", ""))
    items = [
        f"核对职位代码 {job.get('job_id')} 对应的最新职位表和招考公告。",
        f"核对专业要求“{job.get('major_required')}”及官方专业分类目录。",
        f"核对学历要求“{job.get('education_required')}”和学位要求。",
    ]

    if job.get("identity_required") not in {"", "不限"}:
        items.append(f"准备并核验“{job.get('identity_required')}”身份认定材料。")
    if any(keyword in notes for keyword in ["其他要求", "备注", "专业笔试", "人民警察"]):
        items.append("逐字核对岗位备注、其他要求、专业笔试及体检政审条件。")

    return _dedupe(items)[:5]


def _build_ai_analysis(
    user_education: str,
    user_major: str,
    user_identity: str,
    job: dict,
    major_score: int,
    suitability: dict,
    location_preference_reason: str,
) -> dict:
    """生成岗位卡片按需展开的自然语言分析。"""
    recruit_count = int(job.get("recruit_count") or job.get("headcount") or 0)
    has_major_profile = not _is_unlimited_filter(user_major)
    has_education_profile = not _is_unlimited_filter(user_education)
    has_identity_profile = not _is_unlimited_filter(user_identity)
    identity_required = job.get("identity_required") or "不限"
    if not has_identity_profile:
        identity_text = "当前身份画像未完善，不能确认是否满足岗位的全部身份条件。"
    elif "不限" in identity_required or not identity_required:
        identity_text = (
            f"{user_identity}可以报，但岗位身份要求为“不限”，不形成身份限制优势，竞争人群可能更宽。"
        )
    elif "应届" in _normalize_identity(user_identity) and "应届" in _normalize_identity(identity_required):
        identity_text = "应届身份匹配岗位限制，有一定限制优势，但仍要以资格审查材料为准。"
    else:
        identity_text = f"岗位身份要求为“{identity_required}”，当前{user_identity}满足初步筛选。"
    education_text = (
        f"从当前职位表字段看，你的{user_education}学历满足初步筛选。"
        if has_education_profile
        else "当前学历画像未完善，不能确认是否满足岗位学历要求。"
    )
    qualification_match = f"{education_text}{identity_text}最终仍要以资格审查结果为准。"

    if major_score == 40 and has_major_profile:
        major_match = (
            f"岗位专业要求直接包含{user_major}，专业匹配比较明确。"
            "报名前仍建议逐字核对最新版专业目录。"
        )
    elif major_score == 30 and has_major_profile:
        major_match = (
            f"{user_major}目前按相关专业大类进入推荐，能否通过资格审查要看官方专业目录口径。"
        )
    else:
        major_match = (
            "岗位专业要求为不限专业，专业本身不构成门槛。"
            "但当前学历、身份等画像仍未完善，不能直接判断整体完全符合。"
        )

    recruit_risk = (
        f"这个岗位招录 {recruit_count} 人，招录名额相对多一些，但不能仅凭名额判断难度。"
        if recruit_count >= 3
        else (
            "这个岗位只招 1 人，报名人数和笔试分差会明显影响结果，建议不要只押这一个岗位。"
            if recruit_count == 1
            else f"这个岗位招录 {recruit_count} 人，名额不多，竞争波动需要重点关注。"
        )
    )

    has_applicant_count = not _is_missing_competition_value(
        job.get("applicants_count") or job.get("applicant_count")
    )
    has_competition_ratio = not _is_missing_competition_value(
        job.get("competition_ratio")
    )
    if not has_applicant_count and not has_competition_ratio:
        competition_data = "缺报名人数和竞争比，当前不能判断竞争强弱。"
    elif not has_applicant_count:
        competition_data = "已有竞争比，但缺报名人数，判断竞争压力时仍要保留数据缺口。"
    elif not has_competition_ratio:
        competition_data = "已有报名人数，但缺竞争比，当前不能据此下竞争强弱结论。"
    else:
        competition_data = "已有报名人数和竞争比，可按结构化字段谨慎判断竞争压力。"

    verify_before_apply = "；".join(
        note.rstrip("。；")
        for note in job.get("verify_notes", [])[:3]
    )
    if not verify_before_apply:
        verify_before_apply = "核对最新公告、职位表、专业目录和资格审查要求。"
    elif not verify_before_apply.endswith("。"):
        verify_before_apply += "。"

    why_parts = [
        location_preference_reason,
        _build_short_reason(
            user_major=user_major,
            job=job,
            major_score=major_score,
            suitability=suitability,
            location_preference_reason="",
        ).rstrip("。"),
    ]
    why_recommended = "。".join(part for part in why_parts if part) + "。"

    direction_fit = (
        "当前专业画像未完善，岗位方向是否适合仍需结合职位简介和个人偏好判断。"
        if not has_major_profile
        else _build_suitability_reason(user_major, suitability)
    )

    return {
        "why_recommended": why_recommended,
        "qualification_match": qualification_match,
        "major_match": major_match,
        "direction_fit": direction_fit,
        "recruit_risk": recruit_risk,
        "competition_data": competition_data,
        "verify_before_apply": verify_before_apply,
    }


def _is_related_major(user_major: str, required_major: str) -> bool:
    """判断用户专业与岗位专业要求是否属于相关技术方向。"""
    user_major = _normalize_text(user_major)
    required_major = _normalize_text(required_major)

    if user_major in COMPUTER_RELATED_MAJORS or _is_information_technology_major(user_major):
        return any(keyword in required_major for keyword in RELATED_MAJOR_KEYWORDS)
    return False


def _is_information_technology_major(major: str) -> bool:
    """判断专业是否属于信息技术相关方向。"""
    major = _normalize_text(major)
    return any(keyword in major for keyword in RELATED_MAJOR_KEYWORDS)


def _build_suitability_reason(user_major: str, suitability: dict) -> str:
    high_matches = suitability.get("high_matches", [])
    medium_matches = suitability.get("medium_matches", [])
    business_matches = suitability.get("business_matches", [])

    if not suitability.get("is_it_major"):
        return (
            f"岗位专业要求与{user_major}匹配，"
            "岗位职责适配度仍需结合职位简介和个人职业方向进一步确认。"
        )

    if suitability.get("pure_business"):
        business_text = "、".join(business_matches[:2]) or "业务"
        return (
            f"岗位名称和职责偏{business_text}方向，技术属性不强，"
            "因此作为可报岗位推荐，适配度低于信息化、数据管理、网络安全类岗位。"
        )

    if high_matches and business_matches:
        tech_text = "、".join(high_matches[:3])
        business_text = "、".join(business_matches[:2])
        return (
            f"岗位名称或职责包含{tech_text}，与{user_major}方向相关；"
            f"但同时属于{business_text}业务条线，需要确认实际技术工作占比。"
        )

    if high_matches:
        tech_text = "、".join(high_matches[:3])
        return (
            f"岗位名称或职责包含{tech_text}，"
            f"与{user_major}、信息技术和数据方向高度相关。"
        )

    if medium_matches:
        medium_text = "、".join(medium_matches[:3])
        return (
            f"岗位职责涉及{medium_text}，具备一定数字化或数据属性，"
            "但技术方向仍需结合职位简介进一步确认。"
        )

    return (
        "岗位名称和职责未体现明显的软件工程或信息技术方向，"
        "主要因专业目录允许报考而进入推荐。"
    )


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _normalize_identity(text: str) -> str:
    """统一常见身份文本。"""
    text = _normalize_text(text)
    return (
        text.replace("应届毕业生", "应届生")
        .replace("高校应届生", "应届生")
        .replace("往届毕业生", "往届生")
    )


def _normalize_target(text: str) -> str:
    """统一职业方向名称，兼容旧测试数据中的事业编叫法。"""
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
    """统一公务员考试类型。"""
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
    """Normalize province names with the national region table first."""
    text = _normalize_text(text)
    province = canonical_province(text)
    if province:
        return province
    return (
        text.replace("广西壮族自治区", "广西")
        .replace("内蒙古自治区", "内蒙古")
        .replace("新疆维吾尔自治区", "新疆")
        .replace("西藏自治区", "西藏")
        .replace("宁夏回族自治区", "宁夏")
        .replace("省", "")
        .replace("市", "")
        .replace("自治区", "")
        .replace("特别行政区", "")
        .replace("·", "-")
        .replace("/", "-")
        .replace(" ", "")
    )


def _normalize_city(text: str) -> str:
    """统一城市名称，广西城市额外支持周边关系。"""
    value = _normalize_text(text).replace("市", "").replace("地区", "")
    if value in {"", "不限", "全部", "不限制", "全省"}:
        return ""
    resolved_region = resolve_region(value)
    if resolved_region.get("level") == "city" and resolved_region.get("city"):
        return resolved_region["city"]
    known_city = next(
        (city for city in GUANGXI_CITY_NEIGHBORS if city in value),
        "",
    )
    return known_city or value


def _split_region_city(text: str) -> tuple[str, str]:
    """从“广西-南宁”这类旧字段拆出省份和城市。"""
    value = _normalize_text(text)
    if not value:
        return "", ""

    normalized = value.replace("·", "-").replace("/", "-")
    if "-" in normalized:
        region_part, city_part = normalized.split("-", 1)
        return _normalize_region(region_part), _normalize_city(city_part)

    return _normalize_region(normalized), ""


def _format_work_location(job: dict) -> str:
    region = _normalize_region(job.get("region", ""))
    city = _normalize_city(job.get("city", ""))
    if region and city:
        return f"{region}-{city}"
    return region or city


def _normalize_text(text: str) -> str:
    """去掉文本前后空格。"""
    return str(text or "").strip()


def _is_unlimited_filter(value: str) -> bool:
    return _normalize_text(value) in {"", "不限", "全部", "不限制"}


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


def _optional_text(value) -> str | None:
    text = _normalize_text(value)
    return text or None


def _coerce_result_limit(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = MAX_RECOMMENDATIONS
    return max(1, min(parsed, MAX_RECOMMENDATIONS))


def _dedupe(items: list[str]) -> list[str]:
    """按原顺序去重。"""
    results = []
    for item in items:
        if item and item not in results:
            results.append(item)
    return results
