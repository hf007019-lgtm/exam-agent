import re

from app.schemas.agent_schema import AgentAnalyzeRequest
from app.services.rag_client import ask_rag


REGION_NAMES = (
    "北京",
    "天津",
    "上海",
    "重庆",
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "台湾",
    "内蒙古",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
    "香港",
    "澳门",
)

QUESTION_POLICY_KEYWORDS = (
    "政策",
    "公告",
    "报考条件",
    "资格审查",
    "资格复审",
    "专业目录",
    "专业限制",
    "专业不限",
    "学历学位",
    "学位要求",
    "应届生",
    "应届毕业生",
    "基层工作经历",
    "服务基层项目人员",
    "最低服务年限",
    "服务年限",
    "户籍",
    "资格证书",
    "政治面貌",
    "退役军人",
    "人民武装",
    "体检",
    "体测",
    "政审",
    "专业测试",
    "岗位备注",
)

JOB_POLICY_KEYWORDS = (
    "应届高校毕业生",
    "应届毕业生",
    "应届生",
    "基层工作经历",
    "服务基层项目人员",
    "最低服务年限",
    "服务年限",
    "户籍",
    "资格证书",
    "职业资格",
    "政治面貌",
    "中共党员",
    "退役军人",
    "人民武装",
    "公安",
    "人民警察",
    "司法",
    "体检",
    "体测",
    "政审",
    "专业测试",
)

DEDICATED_POLICY_FIELDS = {
    "grassroots_requirement": "基层工作经历",
    "fresh_graduate_required": "应届毕业生身份",
    "service_project_required": "服务基层项目人员",
    "political_requirement": "政治面貌",
    "police_position": "人民警察职位",
    "professional_test": "专业测试",
    "household_requirement": "户籍要求",
    "household_registration_requirement": "户籍要求",
    "certificate_requirement": "资格证书",
    "qualification_certificate": "资格证书",
    "service_period_requirement": "最低服务年限",
    "minimum_service_years": "最低服务年限",
    "min_service_years": "最低服务年限",
}

JOB_POLICY_TEXT_FIELDS = (
    "job_description",
    "notes",
    "remark",
    "remarks",
    "major_requirement",
    "major_required",
    "education_requirement",
    "education_required",
    "degree",
    "degree_requirement",
    "identity_requirement",
    "identity_required",
    *DEDICATED_POLICY_FIELDS,
)


def search_policy_sources(payload: AgentAnalyzeRequest) -> dict:
    """查询政策依据。

    这里把用户条件拼成更容易检索到政策资料的问题，再交给政策文件服务。
    """
    query = _build_policy_query(payload)
    result = ask_rag(query)

    result["query"] = query
    if result.get("status") == "error":
        return result

    original_sources = result.get("sources", [])
    matched_sources = _filter_policy_sources(
        payload,
        original_sources,
        require_context_match=True,
    )
    filtered_source_count = len(original_sources) - len(matched_sources)
    result["sources"] = matched_sources
    result["citations"] = matched_sources
    result["filtered_source_count"] = filtered_source_count

    if matched_sources:
        result["status"] = "success"
        result["message"] = (
            f"检索到 {len(matched_sources)} 条与{payload.region}{payload.target}匹配的政策来源"
        )
        if filtered_source_count:
            # 聚合回答可能混入被过滤来源的内容，过滤发生时不继续使用该回答。
            result["answer"] = ""
            result["policy_answer"] = ""
        return result

    message = f"未检索到与{payload.region}{payload.target}匹配的政策来源"
    result.update(
        {
            "status": "warning",
            "message": message,
            "output_summary": message,
            "answer": "",
            "policy_answer": "",
            "sources": [],
            "citations": [],
            "error": "",
        }
    )
    return result


def search_job_policy_sources(
    payload: AgentAnalyzeRequest,
    jobs: list[dict],
) -> dict:
    """只在岗位包含需要解释的政策限制时查询知识库。"""
    trigger_terms = collect_job_policy_terms(payload, jobs)
    if not trigger_terms:
        return {
            "status": "skipped",
            "message": "当前岗位没有触发需要政策解释的限制条件。",
            "answer": "",
            "policy_answer": "",
            "sources": [],
            "citations": [],
            "used_retrieval": False,
            "answer_type": "not_needed",
            "error": "",
            "query": "",
            "trigger_terms": [],
        }

    query = _build_job_policy_query(payload, trigger_terms)
    result = ask_rag(query)
    result["query"] = query
    result["trigger_terms"] = trigger_terms
    if result.get("status") == "error":
        return result

    original_sources = result.get("sources", [])
    matched_sources = _filter_policy_sources(
        payload,
        original_sources,
        require_context_match=False,
    )
    filtered_source_count = len(original_sources) - len(matched_sources)
    result["sources"] = matched_sources
    result["citations"] = matched_sources
    result["filtered_source_count"] = filtered_source_count

    if matched_sources:
        result["status"] = "success"
        result["message"] = f"检索到 {len(matched_sources)} 条岗位条件政策来源"
        if filtered_source_count:
            result["answer"] = ""
            result["policy_answer"] = ""
        return result

    result.update(
        {
            "status": "warning",
            "message": "岗位存在需要核验的政策条件，但当前未检索到匹配来源。",
            "answer": "",
            "policy_answer": "",
            "sources": [],
            "citations": [],
            "error": "",
        }
    )
    return result


def should_search_job_policy_sources(
    payload: AgentAnalyzeRequest,
    jobs: list[dict],
) -> bool:
    """供 Agent 与测试判断普通岗位请求是否需要政策检索。"""
    return bool(collect_job_policy_terms(payload, jobs))


def collect_job_policy_terms(
    payload: AgentAnalyzeRequest,
    jobs: list[dict],
) -> list[str]:
    terms: list[str] = []
    question = str(payload.question or "")
    if _question_requests_policy_explanation(question):
        for keyword in QUESTION_POLICY_KEYWORDS:
            if keyword in question:
                _append_unique(terms, keyword)

    for job in jobs[:5]:
        if not isinstance(job, dict) or job.get("data_error"):
            continue
        for field in JOB_POLICY_TEXT_FIELDS:
            value = str(job.get(field) or "").strip()
            if not value:
                continue
            for keyword in JOB_POLICY_KEYWORDS:
                if _contains_positive_policy_keyword(value, keyword):
                    _append_unique(terms, keyword)
            if field in DEDICATED_POLICY_FIELDS and _is_meaningful_requirement(value):
                _append_unique(terms, DEDICATED_POLICY_FIELDS[field])
    return terms[:8]


def ask_help_policy_question(payload: AgentAnalyzeRequest) -> dict:
    """帮助页政策问答。

    帮助页的问题可能是概念解释，不强制按地区过滤来源；只要政策问答服务
    返回了可核验来源，就把它们作为“政策文件”返回给前端。
    """
    query = _build_help_query(payload)
    result = ask_rag(query)
    result["query"] = query

    if result.get("status") != "success" or not result.get("sources"):
        result.update(
            {
                "status": "fallback",
                "answer": "",
                "policy_answer": "",
                "sources": [],
                "citations": [],
            }
        )
        return result

    result["sources"] = [_normalize_help_source(source) for source in result.get("sources", [])]
    result["citations"] = result["sources"]
    result["message"] = f"检索到 {len(result['sources'])} 条帮助问答政策来源"
    return result


def _build_policy_query(payload: AgentAnalyzeRequest) -> str:
    """构建包含地区和考试类型的政策检索问题。"""
    terms = (
        payload.region,
        payload.target,
        payload.exam_type if payload.target == "公务员" else "",
        payload.major,
        payload.education,
        payload.identity,
        "报考条件",
        "专业要求",
        "职位表",
        "资格审查",
    )
    return " ".join(term.strip() for term in terms if term and term.strip())


def _build_help_query(payload: AgentAnalyzeRequest) -> str:
    """构建帮助页政策查询。"""
    terms = (
        payload.region,
        payload.target,
        payload.exam_type if payload.target == "公务员" else "",
        payload.question,
    )
    return " ".join(term.strip() for term in terms if term and term.strip())


def _build_job_policy_query(
    payload: AgentAnalyzeRequest,
    trigger_terms: list[str],
) -> str:
    terms = (
        payload.region,
        payload.target,
        payload.exam_type if payload.target == "公务员" else "",
        "岗位报考条件解释",
        "、".join(trigger_terms),
        "资格审查",
    )
    return " ".join(term.strip() for term in terms if term and term.strip())


def _normalize_help_source(source: dict) -> dict:
    """整理帮助页来源字段，确保前端可以稳定展示来源类型和片段。"""
    if not isinstance(source, dict):
        return {
            "doc_id": None,
            "chunk_id": "",
            "document_name": "政策来源",
            "score": None,
            "text_preview": str(source or ""),
            "source_type": "政策文件",
            "title": "政策来源",
            "page": "",
            "snippet": str(source or ""),
            "confidence": None,
        }

    return {
        "doc_id": source.get("doc_id"),
        "chunk_id": source.get("chunk_id") or "",
        "document_name": source.get("document_name") or source.get("title") or "政策来源",
        "score": source.get("score", source.get("confidence")),
        "text_preview": source.get("text_preview") or source.get("snippet") or "",
        "source_type": "政策文件",
        "title": source.get("title") or "政策来源",
        "url": source.get("url") or "",
        "page": source.get("page") or "",
        "snippet": source.get("snippet") or "",
        "confidence": source.get("confidence"),
    }


def _filter_policy_sources(
    payload: AgentAnalyzeRequest,
    sources: list[dict],
    require_context_match: bool = True,
) -> list[dict]:
    """过滤地区或考试类型明显错配的政策来源。"""
    return [
        source
        for source in sources
        if _source_matches_payload(payload, source, require_context_match)
    ]


def _source_matches_payload(
    payload: AgentAnalyzeRequest,
    source: dict,
    require_context_match: bool,
) -> bool:
    text = _source_text(source)
    if not text:
        return False

    region = payload.region.strip()
    target = payload.target.strip()
    if (
        require_context_match
        and region
        and target
        and region not in text
        and target not in text
    ):
        return False

    if target == "公务员" and ("事业编" in text or "事业单位" in text):
        if "公务员" not in text:
            return False

    if target in {"事业编", "事业单位"} and "公务员" in text:
        if "事业编" not in text and "事业单位" not in text:
            return False

    if region and region not in text:
        conflicting_regions = [
            name
            for name in REGION_NAMES
            if name != region and name in text
        ]
        if conflicting_regions:
            return False

    return True


def _source_text(source: dict) -> str:
    if not isinstance(source, dict):
        return str(source or "").strip()

    values = (
        source.get("file_name"),
        source.get("filename"),
        source.get("document_name"),
        source.get("title"),
        source.get("chunk_text"),
        source.get("text_preview"),
        source.get("snippet"),
        source.get("content"),
        source.get("text"),
    )
    return " ".join(str(value) for value in values if value).strip()


def _is_meaningful_requirement(value: str) -> bool:
    text = "".join(str(value or "").split())
    if not text:
        return False
    return text not in {"否", "不要求", "不限", "无", "否。", "不限制", "无要求"} and "不要求" not in text


def _contains_positive_policy_keyword(value: str, keyword: str) -> bool:
    if keyword not in value:
        return False
    negative_pattern = rf"{re.escape(keyword)}\s*[：:]?\s*(?:不限|否|无|不要求|不限制)"
    return not re.search(negative_pattern, value)


def _question_requests_policy_explanation(question: str) -> bool:
    text = "".join(str(question or "").split())
    cues = (
        "是什么",
        "意思",
        "怎么",
        "如何",
        "认定",
        "界定",
        "理解",
        "能不能报",
        "都能报",
        "所有人",
        "要求",
        "限制",
        "政策",
        "公告",
        "资格审查",
        "资格复审",
        "报考条件",
    )
    return any(cue in text for cue in cues)


def _append_unique(items: list[str], value: str) -> None:
    text = str(value or "").strip()
    if text and text not in items:
        items.append(text)
