import re

from app.schemas.agent_schema import AgentAnalyzeRequest


def analyze_risks(
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict],
    score_references: list[dict],
    policy_error: str = "",
) -> list[str]:
    """Return only risks that are directly triggered by structured job facts."""
    del payload, score_references, policy_error
    risks: list[str] = []

    if any(_applicant_count(job) is None for job in matched_jobs):
        risks.append("暂无报名人数，不能判断报名热度。")
    if any(not str(job.get("competition_ratio") or "").strip() for job in matched_jobs):
        risks.append("暂无竞争比，不能判断竞争强弱。")
    if any(_has_identity_restriction(job) for job in matched_jobs):
        risks.append("该岗位存在身份要求，需核对自己是否符合。")
    if any(_recruit_count(job) == 1 for job in matched_jobs):
        risks.append("该岗位只招 1 人，结果波动和低容错风险更高。")
    if any(_is_police_job(job) for job in matched_jobs):
        risks.append(
            "公安岗通常还要关注体检、体测、视力、政审等要求，"
            "具体以公告、职位表和体检标准文件为准。"
        )

    if any(_min_score(job) is None for job in matched_jobs):
        risks.append("暂无该岗位精确进面分记录，不能据此判断分数压力。")
    elif any(
        str(job.get("score_match_type") or "no_match") != "exact_position_code"
        for job in matched_jobs
    ):
        risks.append("当前分数是同类岗位历史分数参考，非该岗位精确进面分。")

    return _dedupe(risks)


def _applicant_count(job: dict) -> int | None:
    value = (
        job.get("applicant_count")
        if job.get("applicant_count") is not None
        else job.get("applicants_count")
    )
    return _optional_int(value)


def _recruit_count(job: dict) -> int | None:
    value = (
        job.get("recruit_count")
        if job.get("recruit_count") is not None
        else job.get("headcount")
    )
    return _optional_int(value)


def _min_score(job: dict) -> float | None:
    value = (
        job.get("min_score")
        if job.get("min_score") is not None
        else job.get("min_interview_score")
    )
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_identity_restriction(job: dict) -> bool:
    identity = str(
        job.get("identity_requirement")
        or job.get("identity_required")
        or ""
    ).strip()
    return bool(identity and identity != "不限")


def _is_police_job(job: dict) -> bool:
    text = " ".join(
        str(job.get(field) or "")
        for field in ["department", "unit", "position_name", "position", "notes"]
    )
    return bool(re.search(r"(公安|人民警察|警务|警察职位)", text))


def _optional_int(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
