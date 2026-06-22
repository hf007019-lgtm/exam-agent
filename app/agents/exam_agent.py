import re
from pathlib import Path
from typing import Any

from app.agents.intent_router import route_intent
from app.agents.prompt_builder import (
    build_analysis_prompt,
    build_free_chat_system_prompt,
    build_intent_router_prompt,
)
from app.schemas.agent_schema import AgentAnalyzeRequest, AgentAnalyzeResponse
from app.db.import_repository import (
    get_candidate_score_summary_by_job,
    get_review_score_summary_by_job,
)
from app.services.llm_service import generate_llm_chat, generate_llm_json, generate_llm_summary
from app.tools.job_tool import extract_location_preference, find_single_job, search_jobs
from app.tools.policy_tool import ask_help_policy_question, search_job_policy_sources
from app.tools.province_registry import (
    has_jobs_csv,
    jobs_csv_path,
    missing_jobs_message,
    resolve_requested_province,
)
from app.tools.region_resolver import canonical_province, resolve_region
from app.tools.risk_tool import analyze_risks
from app.tools.score_tool import attach_scores_to_jobs, find_single_score_reference, search_scores


SINGLE_JOB_NOT_FOUND_MESSAGE = (
    "当前已导入数据中没有找到该岗位，请确认职位代码、岗位名称、地区、考试类型，或是否已导入对应地区数据。"
)
SINGLE_JOB_FUZZY_NOTICE = "这是根据岗位名称近似匹配到的结果，请以职位代码或官方职位表为准。"
GREETING_REPLY = (
    "我可以帮你做 4 件事：\n\n"
    "1. 岗位推荐：根据省份、学历、专业和身份筛选能报岗位。\n"
    "2. 单岗位分析：你发岗位代码或岗位名称，我帮你看是否适合报。\n"
    "3. 政策解释：解释应届生、服务基层项目人员、专业目录、资格审查等。\n"
    "4. 风险判断：结合招录人数、进面分、报名人数和竞争比判断风险。\n\n"
    "你可以直接问：\n"
    "“推荐广西软件工程本科应届生能报的岗位”\n"
    "或\n"
    "“分析 45010021 这个岗位值不值得报”。"
)
CLARIFICATION_REPLY = (
    "可以，我先帮你理一下方向。你可以补充目标省份、学历、专业和身份，我再帮你筛岗位。"
    "比如：广东、本科、软件工程、应届生。\n\n"
    "如果你已经有具体岗位，也可以直接发岗位代码、岗位名称或单位名称。"
)
SCORE_OR_RISK_CLARIFICATION_REPLY = (
    "可以看，但我需要先知道你想看哪个岗位或哪一类岗位。你可以补充岗位代码、单位/岗位名称，"
    "或者说明省份、城市、学历、专业和身份。\n\n"
    "如果只是想理解规则：缺少进面分不代表不能报，也不代表一定更容易；它只说明当前没有可精确绑定到该岗位的历史分数数据。"
    "报名前仍要重点核对专业、学历、身份、招录人数、岗位备注和官方资格审查口径。"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PROFILE = "gongkao_selection_coach_v1"
JOB_ANALYSIS_FIELDS = [
    "why_recommended",
    "qualification_match",
    "major_match",
    "direction_fit",
    "recruit_risk",
    "competition_data",
    "verify_before_apply",
]


def _decide_llm_first(payload: AgentAnalyzeRequest, requested_position_code: str) -> dict:
    fallback = _fallback_agent_decision(payload, requested_position_code)
    if (
        _is_selection_strategy_question(payload.question)
        or (_references_current_job(payload.question) and _resolve_current_job_context(payload))
    ):
        return fallback
    try:
        prompt = _build_agent_decision_prompt(payload, requested_position_code)
        decision = generate_llm_json(prompt=prompt, fallback_data=fallback)
        if not isinstance(decision, dict):
            return fallback
        decision["intent"] = _normalize_decision_intent(decision.get("intent"))
        decision["used_tools"] = _normalize_used_tools(decision.get("used_tools"))
        decision["missing_fields"] = _normalize_string_list(decision.get("missing_fields"))
        decision["need_follow_up"] = bool(decision.get("need_follow_up"))
        if decision["need_follow_up"] and not str(decision.get("follow_up_question") or "").strip():
            decision["follow_up_question"] = _build_follow_up_question(decision["missing_fields"])
        return decision
    except Exception:
        return fallback


def _build_agent_decision_prompt(payload: AgentAnalyzeRequest, requested_position_code: str) -> str:
    return build_intent_router_prompt(
        payload=payload,
        requested_position_code=requested_position_code,
        recent_messages=_format_recent_messages(payload),
    )


def _fallback_agent_decision(payload: AgentAnalyzeRequest, requested_position_code: str) -> dict:
    try:
        return _fallback_agent_decision_impl(payload, requested_position_code)
    except Exception:
        return {
            "intent": "needs_follow_up",
            "used_tools": [],
            "need_follow_up": True,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": _build_follow_up_question([]),
            "llm_used": False,
        }


def _fallback_agent_decision_impl(payload: AgentAnalyzeRequest, requested_position_code: str) -> dict:
    mode = _normalize_mode(payload.mode)
    question = str(payload.question or "").strip()
    compact = "".join(question.split())

    if _is_selection_strategy_question(question):
        return {
            "intent": "selection_strategy",
            "used_tools": [],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "reason": "选岗方法和岗位类别风险解释不需要查询具体分数或岗位。",
            "llm_used": False,
        }
    if _references_current_job(question) and _resolve_current_job_context(payload):
        return {
            "intent": "single_job_query",
            "used_tools": [],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "reason": "使用当前岗位卡片处理上下文指代。",
            "llm_used": False,
        }
    if mode == "single_job_query":
        return {
            "intent": "single_job_query",
            "used_tools": ["job_tool.find_single_job", "score_tool.find_single_score_reference"],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "llm_used": False,
        }
    if mode in {"help_qa", "policy_qa"}:
        return {
            "intent": "policy_qa",
            "used_tools": ["policy_tool.ask_help_policy_question"],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "llm_used": False,
        }
    if requested_position_code and re.search(r"(分析|查|查询|看看|值不值得|岗位|职位)", question):
        return {
            "intent": "single_job_query",
            "used_tools": ["job_tool.find_single_job", "score_tool.find_single_score_reference"],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "llm_used": False,
        }
    if route_intent(question) == "policy_qa":
        return {
            "intent": "policy_qa",
            "used_tools": ["policy_tool.ask_help_policy_question"],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "llm_used": False,
        }
    if re.search(r"(进面分|最低分|分数线|竞争比|报名人数|缴费人数)", question):
        return {
            "intent": "score_or_risk_query",
            "used_tools": ["score_tool.search_scores"],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "llm_used": False,
        }
    if re.search(r"(推荐|筛|找|能报哪些|能报什么|能报的岗位|可报岗位|岗位推荐|附近.*岗位|岗位.*推荐)", question):
        missing = _missing_recommendation_fields(payload, question)
        if missing:
            return {
                "intent": "needs_follow_up",
                "used_tools": [],
                "need_follow_up": True,
                "missing_fields": missing,
                "direct_answer": "",
                "follow_up_question": _build_follow_up_question(missing),
                "llm_used": False,
            }
        return {
            "intent": "job_recommendation",
            "used_tools": ["job_tool.search_jobs"],
            "need_follow_up": False,
            "missing_fields": [],
            "direct_answer": "",
            "follow_up_question": "",
            "llm_used": False,
        }
    if not compact:
        return {
            "intent": "needs_follow_up",
            "used_tools": [],
            "need_follow_up": True,
            "missing_fields": ["question"],
            "direct_answer": "",
            "follow_up_question": "你可以直接说你的情况或问题，比如：我是软件工程本科应届生，想考广西，应该怎么选岗？",
            "llm_used": False,
        }
    return {
        "intent": "direct_answer",
        "used_tools": [],
        "need_follow_up": False,
        "missing_fields": [],
        "direct_answer": _build_free_chat_fallback_answer(payload),
        "follow_up_question": "",
        "llm_used": False,
    }


def _answer_free_chat_request(
    payload: AgentAnalyzeRequest,
    intent: str,
    trace: list[dict[str, Any]],
    decision: dict,
    need_follow_up: bool = False,
) -> AgentAnalyzeResponse:
    fallback = (
        str(decision.get("follow_up_question") or "").strip()
        if need_follow_up
        else str(decision.get("direct_answer") or "").strip()
    )
    if not fallback:
        fallback = _build_free_chat_fallback_answer(payload)

    llm_result = generate_llm_chat(
        system_prompt=build_free_chat_system_prompt(),
        messages=_messages_for_llm(payload),
        fallback_report=fallback,
        temperature=0.45,
    )
    answer = _ensure_analysis_report(llm_result, fallback)
    _add_trace(
        trace=trace,
        step=len(trace) + 1,
        name="自由对话回答",
        tool="llm_service.generate_llm_chat",
        status="success" if llm_result.get("llm_used") else "warning",
        input_data={"intent": intent, "need_follow_up": need_follow_up},
        output_summary="无需工具，直接生成自然语言回答。",
    )
    return _build_chat_only_response(
        payload=payload,
        intent=intent,
        trace=trace,
        summary=answer,
        trace_summary="LLM-first 判断无需岗位工具。",
        risks=[],
        llm_used=bool(llm_result.get("llm_used") or decision.get("llm_used")),
        need_follow_up=need_follow_up,
        missing_fields=_normalize_string_list(decision.get("missing_fields")),
    )


def _format_recent_messages(payload: AgentAnalyzeRequest) -> str:
    messages = _messages_for_llm(payload)
    if not messages:
        return "（无）"
    return "\n".join(f"{item['role']}: {item['content']}" for item in messages[-10:])


def _messages_for_llm(payload: AgentAnalyzeRequest) -> list[dict]:
    messages = []
    for message in (getattr(payload, "messages", []) or [])[-12:]:
        role = str(getattr(message, "role", "") or "").strip()
        content = str(getattr(message, "content", "") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    question = str(payload.question or "").strip()
    if question and not (messages and messages[-1]["role"] == "user" and messages[-1]["content"] == question):
        messages.append({"role": "user", "content": question})
    return messages[-12:]


def _normalize_decision_intent(intent: Any) -> str:
    value = str(intent or "").strip()
    aliases = {
        "chat": "direct_answer",
        "general": "direct_answer",
        "general_chat": "direct_answer",
        "small_talk": "direct_answer",
        "greeting": "direct_answer",
        "follow_up": "needs_follow_up",
        "needs_clarification": "needs_follow_up",
        "help_qa": "policy_qa",
        "risk_explanation": "selection_strategy",
        "general_job_selection_advice": "selection_strategy",
    }
    value = aliases.get(value, value)
    allowed = {
        "direct_answer",
        "selection_strategy",
        "job_recommendation",
        "single_job_query",
        "score_or_risk_query",
        "policy_qa",
        "needs_follow_up",
    }
    return value if value in allowed else "direct_answer"


def _normalize_used_tools(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _missing_recommendation_fields(payload: AgentAnalyzeRequest, question: str) -> list[str]:
    missing = []
    question_region = resolve_region(question)
    if (
        _is_blank_filter_value(payload.region)
        and not question_region.get("province")
        and not re.search(r"(北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|四川|贵州|云南|陕西|甘肃|青海|宁夏|新疆|西藏|内蒙古)", question)
    ):
        missing.append("region")
    if _is_blank_filter_value(payload.education) and not re.search(r"(大专|本科|硕士|研究生|博士)", question):
        missing.append("education")
    if not str(payload.major or "").strip() and not re.search(r"(专业不限|不限专业|软件工程|计算机|法学|会计|汉语言|土木|临床|经济|金融|管理)", question):
        missing.append("major")
    if not str(payload.identity or "").strip():
        missing.append("identity")
    return missing


def _should_use_filter_profile_for_recommendation(payload: AgentAnalyzeRequest) -> bool:
    question = str(payload.question or "")
    compact = "".join(question.split())
    if not compact:
        return False
    current_filter_words = [
        "已经筛选",
        "筛选好了",
        "当前条件",
        "当前筛选",
        "我选的条件",
        "按我选",
        "按条件",
    ]
    recommendation_words = [
        "推荐",
        "岗位",
        "职位",
        "适合",
        "能报",
        "帮我看看",
    ]
    if not any(word in compact for word in current_filter_words + recommendation_words):
        return False
    return not _missing_recommendation_fields(payload, question)


def _resolve_result_limit(payload: AgentAnalyzeRequest) -> int:
    explicit_limit = _coerce_result_limit(getattr(payload, "result_limit", None), default=0)
    if explicit_limit:
        return explicit_limit
    return _infer_result_limit(payload.question)


def _infer_result_limit(question: str) -> int:
    text = "".join(str(question or "").split())
    if not text:
        return 5

    number_words = {
        "一": 1,
        "一个": 1,
        "1": 1,
        "二": 2,
        "两个": 2,
        "两": 2,
        "2": 2,
        "三": 3,
        "三个": 3,
        "3": 3,
        "四": 4,
        "四个": 4,
        "4": 4,
        "五": 5,
        "五个": 5,
        "5": 5,
    }
    if any(word in text for word in ["推荐一个", "推荐1个", "给我一个", "选一个", "最适合的一个", "一个最适合"]):
        return 1
    for pattern in [
        r"推荐([一二两三四五1-5])个?(?:岗位|职位)?",
        r"给我([一二两三四五1-5])个?(?:岗位|职位)?",
        r"筛出([一二两三四五1-5])个?(?:岗位|职位)?",
    ]:
        match = re.search(pattern, text)
        if match:
            return _coerce_result_limit(number_words.get(match.group(1), match.group(1)))
    return 5


def _coerce_result_limit(value: Any, default: int = 5) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, 5))


def _is_blank_filter_value(value: str) -> bool:
    text = str(value or "").strip()
    return not text or text in {"未设置", "未填写", "请选择"}


def _build_follow_up_question(missing: list[str] | None) -> str:
    labels = {
        "region": "目标省份",
        "education": "学历",
        "major": "专业",
        "identity": "身份",
        "question": "问题",
    }
    missing_names = []
    for item in missing or []:
        key = str(item or "").strip()
        label = labels.get(key, key)
        if label and label not in missing_names:
            missing_names.append(label)
    if not missing_names:
        return "可以，我需要再确认一下你的报考条件。你可以补充省份、学历、专业和身份，我再帮你筛岗位。"
    names = "、".join(missing_names)
    if "目标省份" not in missing_names:
        return (
            f"当前条件可以先做宽口径初筛，但现在不能给精准岗位结论。"
            f"还缺{names}，这些会直接影响资格审查。你可以补充后，我再按职位表筛选。"
        )
    return f"可以，我还需要补充{names}。你可以这样说：广西、本科、软件工程、应届生，我再帮你筛岗位。"


def _build_free_chat_fallback_answer(payload: AgentAnalyzeRequest) -> str:
    question = str(payload.question or "").strip()
    if re.search(r"(你可以干嘛|你能做什么|有什么功能|怎么用|能问你什么|你是谁)", question):
        return (
            "我可以帮你做几类事：第一，按省份、学历、专业和身份帮你筛岗位；第二，你发岗位代码后，我可以帮你看这个岗位是否适合报；"
            "第三，我可以解释应届生、服务基层项目人员、专业目录、资格审查这类政策问题；第四，我可以结合招录人数、进面分、报名人数和竞争比帮你判断风险。\n\n"
            "你不用按固定格式问，直接说你的情况就行。比如：我是软件工程本科应届生，想考广西，应该怎么选岗？"
        )
    if re.search(r"(怎么选岗|选岗思路|制定.*选岗|如何选岗)", question):
        return (
            "你先别急着看分数。选岗第一关是资格审查：先核对学历学位、专业目录、身份、基层经历、户籍和备注限制；"
            "通过硬门槛后，再比较招录人数、历史分数匹配和已有竞争数据。缺报名人数和竞争比时，不能判断岗位热度。\n\n"
            "下一步你可以告诉我省份、学历、专业和身份，我再把这个思路落到具体岗位筛选上。"
        )
    if re.search(r"(软件工程|计算机)", question):
        return (
            "软件工程能不能报，先看职位表的专业口径。岗位可能写具体专业，也可能写“计算机类”等专业大类，"
            "大类相关不等于完全匹配，边界不清就要查官方专业目录或问招考单位。\n\n"
            "没有职位表统计时，我不能判断某个地区的软件工程岗位多不多。下一步先补充目标省份和学历，再按真实职位表筛。"
        )
    if re.search(r"(最低进面分|只看.*分|进面分)", question):
        return (
            "不能只看最低进面分，因为它是过去某次考试的结果，不是今年提前划好的线。岗位代码、招录人数、报名人数、专业限制、地区热度和题目难度一变，分数参考价值都会变化。\n\n"
            "把历史最低进面分当成风险参考，再结合招录人数和限制条件看。没有报名人数和竞争比时，不能判断今年热度。"
        )
    if re.search(r"(没有竞争比|缺少竞争比|没有报名人数)", question):
        return (
            "没有竞争比不代表不能报，也不代表岗位一定冷门。它只说明当前缺少报名或缴费统计，风险判断要更保守。"
            "这时先看硬性限制是否清晰、招录人数是否只有 1 人，以及有没有精确匹配的历史进面分；"
            "但这些都不能替代真实报名人数和竞争比。\n\n"
            "报名前最好等官方报名动态或补充数据出来后，再把意向岗位重新排序。"
        )
    if re.search(r"(应届生.*更好|应届生岗位)", question):
        return (
            "“限应届”只是一项资格限制，不等于竞争优势。没有职位表统计、报名人数和竞争比时，"
            "不能判断应届身份让你占多大优势。\n\n"
            "下一步先核对你是否符合当地应届认定，再看具体岗位的专业、学历、招录人数和备注。"
        )
    if re.search(r"(稳定|稳一点|风险低|保守)", question):
        return (
            "没有哪个岗位能提前说“稳”。想降低不确定性，先筛专业和身份限制明确、备注条件你能核实、"
            "招录人数不只有 1 人的岗位，再看精确匹配的历史分数和真实报名数据。\n\n"
            "先建备选，不要直接押宝。你把目标省份、学历、专业和身份发我，我再按真实职位表筛。"
        )
    return (
        "先说结论：没有结构化岗位或官方数据时，我可以帮你理清筛选方法，但不能编具体岗位结论。"
        "选岗先看硬性条件能不能过资格审查，再看招录人数、历史分数匹配和已有竞争数据。\n\n"
        "你可以继续补充目标省份、学历、专业和身份；如果已经有岗位代码，也可以直接发给我做单岗位分析。"
    )


def _set_response_tool_flags(
    response: AgentAnalyzeResponse,
    used_tools: list[str],
    need_follow_up: bool = False,
    missing_fields: list[str] | None = None,
    llm_used: bool | None = None,
) -> AgentAnalyzeResponse:
    merged_tools = []
    for tool in [*response.used_tools, *used_tools]:
        if tool and tool not in merged_tools:
            merged_tools.append(tool)
    response.tool_used = bool(merged_tools)
    response.used_tools = merged_tools
    response.need_follow_up = need_follow_up
    response.missing_fields = missing_fields or []
    response.recommendations = (
        list(response.matched_jobs)
        if response.intent == "job_recommendation" and response.matched_jobs
        else []
    )
    if llm_used is not None:
        response.llm_used = bool(llm_used)
    return response


def _missing_jobs_region_message(region: str, question: str = "") -> str:
    requested_province = resolve_requested_province(region=region, question=question)
    province = requested_province.get("province", "")
    slug = requested_province.get("slug", "")
    if not slug or has_jobs_csv(slug):
        return ""
    return missing_jobs_message(province)


def _build_response_debug(
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict] | None = None,
    recommendation_count: int | None = None,
    fallback_reason: str = "",
    include_data_source: bool = True,
    prompt_scene: str = "",
) -> dict[str, Any]:
    requested_province = resolve_requested_province(
        region=payload.region,
        question=payload.question,
    )
    slug = requested_province.get("slug", "")
    province = requested_province.get("province", "") or canonical_province(payload.region)
    data_source_file = ""
    if slug and include_data_source:
        data_source_file = _relative_debug_path(jobs_csv_path(slug))

    return {
        "resolved_region": province,
        "selected_province_slug": slug,
        "data_source_file": data_source_file,
        "recommendation_count": (
            recommendation_count
            if recommendation_count is not None
            else _recommendation_count(matched_jobs or [])
        ),
        "fallback_reason": fallback_reason,
        "prompt_profile": PROMPT_PROFILE,
        "prompt_scene": prompt_scene or _infer_prompt_scene(payload, matched_jobs or []),
    }


def _infer_prompt_scene(payload: AgentAnalyzeRequest, matched_jobs: list[dict]) -> str:
    if _references_current_job(payload.question) and matched_jobs:
        return "single_job_analysis"
    mode = _normalize_mode(payload.mode)
    if mode == "selection_strategy" or _is_selection_strategy_question(payload.question):
        return "selection_strategy"
    if mode == "job_recommendation" or matched_jobs:
        return "job_recommendation"
    if mode in {"help_qa", "policy_qa"}:
        return "policy_qa"
    if mode == "score_or_risk_query":
        return "score_risk"
    if mode == "single_job_query":
        return "single_job_analysis"
    return "free_chat"


def _relative_debug_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _recommendation_count(matched_jobs: list[dict]) -> int:
    return len([job for job in matched_jobs if not job.get("data_error")])


def _limit_recommendation_jobs(
    matched_jobs: list[dict],
    result_limit: int,
) -> list[dict]:
    """Return the canonical recommendation set used by the UI and LLM."""
    limit = max(1, min(_safe_int(result_limit), 5))
    return [
        job
        for job in matched_jobs
        if isinstance(job, dict) and not job.get("data_error")
    ][:limit]



def _attach_score_samples_to_jobs(
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict],
) -> None:
    """Attach aggregated score samples when no exact score-line record exists."""
    for job in matched_jobs:
        if not isinstance(job, dict) or job.get("data_error"):
            continue
        if _has_exact_score_line(job):
            job["score_source_type"] = "score_line"
            continue

        position_code = _job_position_code(job)
        if not position_code:
            continue

        province = canonical_province(
            job.get("province") or job.get("region") or payload.region
        ) or str(job.get("province") or job.get("region") or payload.region or "")
        year = _safe_int(job.get("year") or job.get("job_source_year") or 0) or None
        exam_type = str(job.get("exam_type") or payload.exam_type or "").strip()
        job_name = str(job.get("position") or job.get("position_name") or job.get("job_name") or "").strip()
        unit_name = str(job.get("department") or job.get("unit") or job.get("unit_name") or "").strip()

        review_summary = get_review_score_summary_by_job(
            province=province,
            year=year,
            exam_type=exam_type,
            job_code=position_code,
            job_name=job_name,
            unit_name=unit_name,
        )
        if _has_score_sample(review_summary):
            _apply_review_score_sample(job, review_summary)
            continue

        candidate_summary = get_candidate_score_summary_by_job(
            province=province,
            year=year,
            exam_type=exam_type,
            job_code=position_code,
            job_name=job_name,
            unit_name=unit_name,
        )
        if _has_score_sample(candidate_summary):
            _apply_candidate_score_sample(job, candidate_summary)


def _has_exact_score_line(job: dict) -> bool:
    return (
        str(job.get("score_match_type") or "") == "exact_position_code"
        and _safe_optional_float(
            job.get("min_score")
            if job.get("min_score") is not None
            else job.get("min_interview_score")
        ) is not None
    )


def _has_score_sample(summary: dict | None) -> bool:
    if not summary or _safe_int(summary.get("sample_count")) <= 0:
        return False
    return any(
        summary.get(field) is not None
        for field in [
            "written_score_min",
            "xingce_score_min",
            "shenlun_score_min",
            "professional_score_min",
            "total_score_min",
        ]
    )


def _apply_review_score_sample(job: dict, summary: dict) -> None:
    sample_count = _safe_int(summary.get("score_sample_count") or summary.get("sample_count"))
    written_min = _score_summary_stat(summary, "review", "written_score", "min")
    written_avg = _score_summary_stat(summary, "review", "written_score", "avg")
    written_max = _score_summary_stat(summary, "review", "written_score", "max")
    reference_score = written_min
    if reference_score is None:
        reference_score = _safe_optional_float(
            summary.get("total_score_min")
            or summary.get("xingce_score_min")
            or summary.get("shenlun_score_min")
            or summary.get("professional_score_min")
        )

    job["score_source_type"] = "review_candidate_sample"
    job["score_match_type"] = "review_candidate_sample"
    job["score_sample_count"] = sample_count
    job["review_score_sample"] = summary
    job["review_written_score_min"] = written_min
    job["review_written_score_avg"] = written_avg
    job["review_written_score_max"] = written_max
    for stat_key in ["xingce_score", "shenlun_score", "professional_score", "total_score"]:
        for suffix in ["min", "avg", "max"]:
            job[f"review_{stat_key}_{suffix}"] = _score_summary_stat(
                summary,
                "review",
                stat_key,
                suffix,
            )
    for suffix in ["min", "max"]:
        job[f"review_rank_{suffix}"] = _score_summary_stat(
            summary,
            "review",
            "rank",
            suffix,
        )
    if reference_score is not None:
        job["min_score"] = reference_score
    job["score_match_confidence"] = 0.82
    job["score_confidence"] = 0.82
    job["score_match_reason"] = (
        f"已按职位代码聚合资格复审名单 {sample_count} 条成绩样本；"
        "该数据不等同于官方最低进面分。"
    )
    job["score_data_source_label"] = "资格复审名单成绩样本"
    if written_min is not None:
        job["risk_summary"] = (
            f"该岗位已有 {sample_count} 条资格复审入围成绩样本，"
            f"参考最低笔试分 {written_min:g}，平均笔试分 {written_avg:g}。"
            "这不是官方最低进面分，只能辅助判断分数压力。"
            if written_avg is not None
            else f"该岗位已有 {sample_count} 条资格复审入围成绩样本，参考最低笔试分 {written_min:g}。这不是官方最低进面分。"
        )


def _apply_candidate_score_sample(job: dict, summary: dict) -> None:
    sample_count = _safe_int(summary.get("score_sample_count") or summary.get("sample_count"))
    written_min = _score_summary_stat(summary, "candidate", "written_score", "min")
    written_avg = _score_summary_stat(summary, "candidate", "written_score", "avg")
    written_max = _score_summary_stat(summary, "candidate", "written_score", "max")
    reference_score = written_min or _safe_optional_float(summary.get("total_score_min"))

    job["score_source_type"] = "candidate_score_sample"
    job["score_match_type"] = "candidate_score_sample"
    job["score_sample_count"] = sample_count
    job["candidate_score_sample_count"] = sample_count
    job["candidate_score_sample"] = summary
    job["candidate_written_score_min"] = written_min
    job["candidate_written_score_avg"] = written_avg
    job["candidate_written_score_max"] = written_max
    for stat_key in [
        "xingce_score",
        "shenlun_score",
        "professional_score",
        "interview_score",
        "total_score",
    ]:
        for suffix in ["min", "avg", "max"]:
            job[f"candidate_{stat_key}_{suffix}"] = _score_summary_stat(
                summary,
                "candidate",
                stat_key,
                suffix,
            )
    for suffix in ["min", "max"]:
        job[f"candidate_rank_{suffix}"] = _score_summary_stat(
            summary,
            "candidate",
            "rank",
            suffix,
        )
    if reference_score is not None:
        job["min_score"] = reference_score
    job["score_match_confidence"] = 0.72
    job["score_confidence"] = 0.72
    job["score_match_reason"] = (
        f"已按职位代码聚合候选人成绩样本 {sample_count} 条；"
        "该数据不等同于岗位官方最低进面分。"
    )
    job["score_data_source_label"] = "候选人成绩样本"


def _score_summary_stat(
    summary: dict,
    prefix: str,
    field_name: str,
    suffix: str,
) -> float | None:
    return _safe_optional_float(
        summary.get(f"{prefix}_{field_name}_{suffix}")
        if summary.get(f"{prefix}_{field_name}_{suffix}") is not None
        else summary.get(f"{field_name}_{suffix}")
    )


def _prepare_job_response_fields(
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict],
) -> list[dict]:
    """Populate stable, user-facing aliases without changing recommendation order."""
    for job in matched_jobs:
        if job.get("data_error"):
            continue

        position_code = _job_position_code(job)
        _set_job_position_code_fields(job, position_code)
        province = canonical_province(job.get("region") or payload.region) or (
            job.get("region") or payload.region or ""
        )
        score_match_type = str(job.get("score_match_type") or "no_match")
        min_score = _safe_optional_float(
            job.get("min_score")
            if job.get("min_score") is not None
            else job.get("min_interview_score")
        )
        applicant_count = _safe_optional_int(
            job.get("applicant_count")
            if job.get("applicant_count") is not None
            else job.get("applicants_count")
        )
        score_confidence = _safe_optional_float(
            job.get("score_confidence")
            if job.get("score_confidence") is not None
            else job.get("score_match_confidence")
        )

        job["province"] = province
        job["position_name"] = _resolve_job_position_name(job)
        job["unit_name"] = _public_job_field(
            job.get("unit_name"),
            job.get("unit"),
            job.get("department"),
        )
        job["education_requirement"] = (
            job.get("education_requirement") or job.get("education_required") or ""
        )
        job["degree_requirement"] = _public_job_field(
            job.get("degree_requirement"),
            job.get("degree"),
        )
        job["major_requirement"] = (
            job.get("major_requirement") or job.get("major_required") or ""
        )
        job["identity_requirement"] = (
            job.get("identity_requirement") or job.get("identity_required") or "不限"
        )
        job["political_requirement"] = _public_job_field(job.get("political_requirement"))
        job["grassroots_requirement"] = _public_job_field(
            job.get("grassroots_requirement"),
            job.get("grassroots_experience"),
        )
        job["qualification_requirement"] = _public_job_field(
            job.get("qualification_requirement"),
            job.get("qualification"),
            job.get("eligibility_requirement"),
        )
        job["agency_level"] = _public_job_field(
            job.get("agency_level"),
            job.get("institution_level"),
            job.get("organization_level"),
        )
        job["is_public_service"] = _public_job_field(
            job.get("is_public_service"),
            job.get("public_service_status"),
            job.get("is_civil_service_managed"),
        )
        job["is_law_enforcement"] = _public_job_field(
            job.get("is_law_enforcement"),
            job.get("law_enforcement_status"),
        )
        job["job_description"] = _public_job_field(
            job.get("job_description"),
            job.get("position_description"),
            job.get("description"),
        )
        job["contact_phone"] = _public_job_field(
            job.get("contact_phone"),
            job.get("consult_phone"),
            job.get("unit_phone"),
        )
        job["work_address"] = _public_job_field(
            job.get("work_address"),
            job.get("unit_address"),
            job.get("office_address"),
        )
        job["remark"] = _public_job_field(job.get("remark"))
        job["recruit_count"] = _safe_int(job.get("recruit_count") or job.get("headcount"))
        job["interview_count"] = _safe_optional_int(job.get("interview_count"))
        job["min_interview_score"] = _safe_optional_float(
            job.get("min_interview_score")
            if job.get("min_interview_score") is not None
            else min_score
        )
        job["max_interview_score"] = _safe_optional_float(
            job.get("max_interview_score")
            if job.get("max_interview_score") is not None
            else job.get("max_score")
        )
        job["min_score"] = min_score
        job["avg_score"] = _safe_optional_float(job.get("avg_score"))
        job["max_score"] = _safe_optional_float(
            job.get("max_score")
            if job.get("max_score") is not None
            else job.get("max_interview_score")
        )
        job["applicant_count"] = applicant_count
        job["applicants_count"] = applicant_count
        job["score_confidence"] = score_confidence
        job["score_match_confidence"] = score_confidence
        job["recommendation_reason"] = (
            job.get("recommendation_reason")
            or job.get("short_reason")
            or "该岗位通过当前条件初筛，建议继续核对官方职位表。"
        )
        job["risk_flags"] = _build_job_risk_flags(job)
        job["data_source_label"] = _friendly_job_data_source_label(
            year=job.get("year") or job.get("job_source_year"),
            province=province,
            target=job.get("target") or payload.target,
        )
        job["score_data_source_label"] = _friendly_score_data_source_label(
            year=job.get("score_source_year") or job.get("year"),
            province=province,
            score_match_type=score_match_type,
            score_source_type=str(job.get("score_source_type") or ""),
        )
    return matched_jobs


def _public_job_field(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return "是" if value else "否"
        text = " ".join(str(value).split()).strip()
        if text:
            return text
    return ""


def _build_job_risk_flags(job: dict) -> list[str]:
    flags: list[str] = []
    if job.get("applicant_count") is None and job.get("applicants_count") is None:
        flags.append("待补报名数据")
    if not job.get("competition_ratio"):
        flags.append("暂无竞争比")
    score_source_type = str(job.get("score_source_type") or "")
    if job.get("min_score") is None:
        flags.append("待补充分数")
    elif job.get("score_match_type") != "exact_position_code":
        if score_source_type == "review_candidate_sample":
            flags.append("资格复审样本")
        elif score_source_type == "candidate_score_sample":
            flags.append("候选成绩样本")
        else:
            flags.append("暂无精确分数")

    identity_requirement = str(
        job.get("identity_requirement") or job.get("identity_required") or ""
    )
    if identity_requirement and identity_requirement != "不限":
        flags.append("身份需核验")

    major_requirement = str(
        job.get("major_requirement") or job.get("major_required") or ""
    )
    if major_requirement and "不限" not in major_requirement:
        flags.append("专业需核验")

    return list(dict.fromkeys(flags))


def _resolve_job_position_name(job: dict) -> str:
    candidates = [
        job.get("job_name"),
        job.get("position_name"),
        job.get("position"),
        job.get("title"),
    ]
    normalized = [
        " ".join(str(value or "").split())
        for value in candidates
        if str(value or "").strip()
    ]
    for value in normalized:
        if not value.isdigit():
            return value
    if normalized:
        return f"岗位 {normalized[0]}"
    position_code = _job_position_code(job)
    return f"职位代码 {position_code}" if position_code else "未命名岗位"


def _friendly_job_data_source_label(
    year: Any,
    province: str,
    target: str,
) -> str:
    source_year = _safe_int(year) or 2025
    source_province = province or "当前地区"
    if "事业" in str(target or ""):
        return f"{source_year} 年{source_province}事业单位招聘职位表"
    return f"{source_year} 年{source_province}公务员考试职位表"


def _friendly_score_data_source_label(
    year: Any,
    province: str,
    score_match_type: str,
    score_source_type: str = "",
) -> str:
    if score_source_type == "review_candidate_sample" or score_match_type == "review_candidate_sample":
        return "资格复审名单成绩样本"
    if score_source_type == "candidate_score_sample" or score_match_type == "candidate_score_sample":
        return "候选人成绩样本"
    if score_match_type == "no_match":
        return "暂无该岗位精确进面分记录"
    if score_match_type != "exact_position_code":
        return "历史分数参考，非该岗位职位代码精确进面分"
    source_year = _safe_int(year) or 2025
    source_province = province or "当前地区"
    return f"{source_year} 年{source_province}公务员考试进面分数线表"


def _is_explicit_nearby_request(question: str) -> bool:
    text = "".join(str(question or "").split())
    return bool(re.search(r"(附近|周边|就近|离[^，。！？]{0,12}近)", text))


def _build_no_jobs_fallback_reason(payload: AgentAnalyzeRequest) -> str:
    preference = extract_location_preference(
        question=payload.question,
        city=payload.city,
        region=payload.region,
    )
    if preference.get("city") and _is_explicit_nearby_request(payload.question):
        return (
            f"当前没有找到{preference['city']}附近的精确匹配岗位，"
            f"可以放宽到{preference.get('province') or payload.region or '所在省份'}区内，"
            "或补充学历、专业、身份。"
        )
    return (
        f"当前{payload.region or '该省份'}职位表中没有符合本次条件的岗位。"
        "你可以放宽城市、专业、身份或学历条件后再试。"
    )


def _apply_question_region(payload: AgentAnalyzeRequest) -> AgentAnalyzeRequest:
    question_region = resolve_region(payload.question)
    requested_province = resolve_requested_province(
        region=payload.region,
        question=payload.question,
    )
    question_province = (
        requested_province.get("province", "")
        or canonical_province(question_region.get("province", ""))
    )
    updates: dict[str, str] = {}
    current_province = canonical_province(payload.region)
    question_city = question_region.get("city", "")
    if requested_province.get("source") == "question" or question_region.get("province"):
        if question_province:
            updates["region"] = question_province
        if current_province and question_province and current_province != question_province:
            updates["city"] = question_city
        elif question_city:
            updates["city"] = question_city
    elif question_city:
        updates["city"] = question_city

    question_education = _extract_question_education(payload.question)
    question_major = _extract_question_major(payload.question)
    question_identity = _extract_question_identity(payload.question)
    if question_education:
        updates["education"] = question_education
    if question_major:
        updates["major"] = question_major
    if question_identity:
        updates["identity"] = question_identity

    if not updates:
        return payload
    if hasattr(payload, "model_copy"):
        return payload.model_copy(update=updates)
    return payload.copy(update=updates)


def _extract_question_education(question: str) -> str:
    text = "".join(str(question or "").split())
    match = re.search(r"(大专|本科(?:以上)?|硕士(?:研究生)?|研究生|博士(?:研究生)?)", text)
    return match.group(1) if match else ""


def _extract_question_major(question: str) -> str:
    text = "".join(str(question or "").split())
    for major in [
        "软件工程",
        "计算机科学与技术",
        "计算机",
        "法学",
        "会计学",
        "会计",
        "汉语言文学",
        "土木工程",
        "临床医学",
        "经济学",
        "金融学",
        "行政管理",
    ]:
        if major in text:
            return major
    if re.search(r"(专业不限|不限专业)", text):
        return "不限"
    return ""


def _extract_question_identity(question: str) -> str:
    text = "".join(str(question or "").split())
    identity_patterns = [
        ("服务基层项目人员", "服务基层项目人员"),
        ("退役大学生士兵", "退役大学生士兵"),
        ("应届毕业生", "应届生"),
        ("应届生", "应届生"),
        ("普通人员", "普通人员"),
    ]
    for pattern, value in identity_patterns:
        if pattern in text:
            return value
    if re.search(r"(身份不限|不限身份)", text):
        return "不限"
    return ""


def analyze_exam_request(payload: AgentAnalyzeRequest) -> AgentAnalyzeResponse:
    try:
        return _analyze_exam_request_impl(payload)
    except Exception:
        requested_position_code = _extract_requested_position_code(payload.question)
        decision = _fallback_agent_decision(payload, requested_position_code)
        need_follow_up = bool(decision.get("need_follow_up"))
        missing_fields = _normalize_string_list(decision.get("missing_fields"))
        summary = (
            str(decision.get("follow_up_question") or "").strip()
            if need_follow_up
            else ""
        )
        if not summary:
            summary = "这次分析暂时没有完成，可以稍后重试或换一种问法。最终仍请以官方公告、职位表和资格审查为准。"
        return AgentAnalyzeResponse(
            intent="needs_follow_up" if need_follow_up else "general_chat",
            summary=summary,
            analysis_report=summary,
            recommended_directions=[],
            risks=[],
            sources=[],
            matched_jobs=[],
            score_references=[],
            llm_used=False,
            tool_used=False,
            used_tools=[],
            need_follow_up=need_follow_up,
            missing_fields=missing_fields,
            recommendations=[],
            trace=[
                {
                    "step": 1,
                    "name": "安全兜底",
                    "tool": "agent_fallback",
                    "status": "warning",
                    "input": {"question_provided": bool(str(payload.question or "").strip())},
                    "output_summary": "本次分析未完成，已返回可重试的友好提示。",
                }
            ],
        )


def _analyze_exam_request_impl(payload: AgentAnalyzeRequest) -> AgentAnalyzeResponse:
    """执行招考岗位智能匹配主流程。

    流程包括：识别意图、岗位硬性过滤与评分、查询分数线、查询政策依据、
    生成风险提醒、构建提示词、调用大模型生成总结。
    """
    trace: list[dict[str, Any]] = []

    requested_position_code = _extract_requested_position_code(payload.question)
    current_job = _resolve_current_job_context(payload)
    references_current_job = _references_current_job(payload.question)
    mode = _normalize_mode(payload.mode)
    decision = _decide_llm_first(payload, requested_position_code)
    decision_intent = _normalize_decision_intent(decision.get("intent"))
    if decision_intent == "needs_follow_up" and _should_use_filter_profile_for_recommendation(payload):
        decision_intent = "job_recommendation"
        decision["need_follow_up"] = False
        decision["missing_fields"] = []
    _add_trace(
        trace=trace,
        step=1,
        name="LLM-first intent planning",
        tool="llm_service.generate_llm_json",
        status="success" if decision.get("llm_used") else "warning",
        input_data={
            "mode": mode,
            "question": payload.question,
            "message_count": len(getattr(payload, "messages", []) or []),
        },
        output_summary=(
            f"LLM-first intent={decision_intent}, tools={decision.get('used_tools') or []}."
            if decision.get("llm_used")
            else f"Fallback intent={decision_intent}; LLM planner unavailable."
        ),
    )

    if references_current_job and current_job:
        decision_intent = "single_job_query"
    elif mode == "single_job_query":
        decision_intent = "single_job_query"
    elif mode in {"help_qa", "policy_qa"}:
        decision_intent = "policy_qa"

    if references_current_job and current_job:
        if _question_claims_police_job(payload.question) and not _is_police_job(current_job):
            title = (
                current_job.get("job_title")
                or current_job.get("position_name")
                or current_job.get("position")
                or "当前岗位"
            )
            message = (
                f"我看到当前卡片是【{title}】，暂时不能确认它属于公安/人民警察岗位。"
                "如果你要分析公安岗，请发职位代码或岗位名称；"
                "如果你指的是当前这个岗位，我可以先按当前卡片分析。"
            )
            return _build_chat_only_response(
                payload=payload,
                intent="single_job_query",
                trace=trace,
                summary=message,
                trace_summary="当前岗位卡片与用户所称公安岗位类型不一致，未做公安岗推断。",
                prompt_scene="single_job_analysis",
            )
        return _analyze_current_job_request(
            payload=payload,
            trace=trace,
            current_job=current_job,
        )

    if decision_intent == "selection_strategy":
        return _analyze_selection_strategy_request(payload=payload, trace=trace)

    if decision_intent in {"direct_answer", "general_chat", "greeting", "small_talk"}:
        return _answer_free_chat_request(
            payload=payload,
            intent="general_chat",
            trace=trace,
            decision=decision,
        )

    if decision_intent == "needs_follow_up":
        return _answer_free_chat_request(
            payload=payload,
            intent="needs_follow_up",
            trace=trace,
            decision=decision,
            need_follow_up=True,
        )

    if decision_intent == "policy_qa":
        response = _analyze_help_qa_request(
            payload=payload,
            intent="policy_qa",
            trace=trace,
        )
        return _set_response_tool_flags(
            response,
            used_tools=["policy_tool.ask_help_policy_question"],
            llm_used=response.llm_used or bool(decision.get("llm_used")),
        )

    if decision_intent == "score_or_risk_query":
        if requested_position_code:
            response = _analyze_single_job_request(
                payload=payload,
                intent="score_or_risk_query",
                trace=trace,
                requested_position_code=requested_position_code,
            )
            return _set_response_tool_flags(
                response,
                used_tools=["job_tool.find_single_job", "score_tool.find_single_score_reference"],
                llm_used=response.llm_used or bool(decision.get("llm_used")),
            )
        response = _analyze_score_or_risk_request(payload=payload, trace=trace)
        return _set_response_tool_flags(
            response,
            used_tools=["score_tool.search_scores"],
            llm_used=response.llm_used or bool(decision.get("llm_used")),
        )

    if decision_intent == "single_job_query":
        response = _analyze_single_job_request(
            payload=payload,
            intent="single_job_query",
            trace=trace,
            requested_position_code=requested_position_code,
        )
        return _set_response_tool_flags(
            response,
            used_tools=["job_tool.find_single_job", "score_tool.find_single_score_reference"],
            llm_used=response.llm_used or bool(decision.get("llm_used")),
        )

    intent = route_intent(payload.question, has_current_job=bool(current_job))
    _add_trace(
        trace=trace,
        step=1,
        name="意图识别",
        tool="intent_router.route_intent",
        status="success",
        input_data={"question": payload.question},
        output_summary=f"识别到的问题类型为 {intent}。",
    )

    requested_position_code = _extract_requested_position_code(payload.question)
    mode = _normalize_mode(payload.mode)
    if intent == "selection_strategy":
        return _analyze_selection_strategy_request(payload=payload, trace=trace)
    if decision_intent == "job_recommendation":
        intent = "job_recommendation"
    if mode in {"small_talk", "greeting"} or intent in {"greeting", "small_talk"}:
        return _build_chat_only_response(
            payload=payload,
            intent="greeting",
            trace=trace,
            summary=GREETING_REPLY,
            trace_summary="普通问候，不触发岗位检索。",
        )

    if mode == "needs_clarification" or intent == "needs_clarification" or _is_incomplete_question(payload.question):
        return _build_chat_only_response(
            payload=payload,
            intent="needs_clarification",
            trace=trace,
            summary=CLARIFICATION_REPLY,
            trace_summary="问题信息不足，先追问省份、学历、专业和身份，不触发岗位检索。",
        )

    if intent == "general" and mode in {"", "job_recommendation"}:
        return _build_chat_only_response(
            payload=payload,
            intent="needs_clarification",
            trace=trace,
            summary=CLARIFICATION_REPLY,
            trace_summary="未识别到明确岗位推荐、单岗位、政策或分数线意图，先追问关键信息，不触发岗位检索。",
        )

    if mode in {"help_qa", "policy_qa"} or intent == "policy_qa":
        return _analyze_help_qa_request(
            payload=payload,
            intent="policy_qa",
            trace=trace,
        )

    if mode == "score_or_risk_query" or intent == "score_or_risk_query":
        if requested_position_code:
            return _analyze_single_job_request(
                payload=payload,
                intent="score_or_risk_query",
                trace=trace,
                requested_position_code=requested_position_code,
            )
        return _analyze_score_or_risk_request(
            payload=payload,
            trace=trace,
        )

    payload = _apply_question_region(payload)
    missing_jobs_region_message = _missing_jobs_region_message(payload.region, payload.question)
    if missing_jobs_region_message:
        _add_trace(
            trace=trace,
            step=2,
            name="职位表数据检查",
            tool="province_registry.has_jobs_csv",
            status="warning",
            input_data={"region": payload.region, "city": payload.city},
            output_summary=missing_jobs_region_message,
        )
        return AgentAnalyzeResponse(
            intent=intent,
            summary=missing_jobs_region_message,
            analysis_report=missing_jobs_region_message,
            recommended_directions=[],
            risks=[missing_jobs_region_message],
            sources=[],
            matched_jobs=[],
            score_references=[],
            llm_used=bool(decision.get("llm_used")),
            tool_used=True,
            used_tools=["province_registry.has_jobs_csv"],
            need_follow_up=False,
            missing_fields=[],
            recommendations=[],
            trace=trace,
            **_build_response_debug(
                payload=payload,
                matched_jobs=[],
                fallback_reason=missing_jobs_region_message,
            ),
        )

    if _should_use_single_job_query(payload, requested_position_code):
        response = _analyze_single_job_request(
            payload=payload,
            intent=intent,
            trace=trace,
            requested_position_code=requested_position_code,
        )
        return _set_response_tool_flags(
            response,
            used_tools=["job_tool.find_single_job", "score_tool.find_single_score_reference"],
            llm_used=response.llm_used,
        )

    recommendation_position_code = requested_position_code if not mode else ""

    result_limit = _resolve_result_limit(payload)
    matched_jobs = search_jobs(
        target=payload.target,
        exam_type=payload.exam_type,
        region=payload.region,
        city=payload.city,
        education=payload.education,
        major=payload.major,
        identity=payload.identity,
        question=payload.question,
        limit=result_limit,
    )
    _add_trace(
        trace=trace,
        step=2,
        name="岗位筛选与评分",
        tool="job_tool.search_jobs",
        status="success",
        input_data={
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "city": payload.city,
            "education": payload.education,
            "major": payload.major,
            "identity": payload.identity,
            "question": payload.question,
            "result_limit": result_limit,
        },
        output_summary=_build_job_trace_summary(matched_jobs),
    )

    score_lookup_jobs = _with_requested_position_code(
        matched_jobs=matched_jobs,
        payload=payload,
        requested_position_code=recommendation_position_code,
    )
    score_references = search_scores(
        target=payload.target,
        exam_type=payload.exam_type,
        region=payload.region,
        major=payload.major,
        matched_jobs=score_lookup_jobs,
    )
    if recommendation_position_code:
        score_references = [
            score
            for score in score_references
            if _normalize_position_code(score.get("position_code")) == recommendation_position_code
        ]
    attach_scores_to_jobs(matched_jobs, score_references)
    score_references = _public_score_references(score_references)
    _attach_score_samples_to_jobs(payload, matched_jobs)
    matched_jobs = _ensure_requested_position_result(
        payload=payload,
        matched_jobs=matched_jobs,
        score_references=score_references,
        requested_position_code=recommendation_position_code,
    )
    matched_jobs = _limit_recommendation_jobs(matched_jobs, result_limit)
    matched_jobs = _prepare_job_response_fields(payload, matched_jobs)
    recommendations = list(matched_jobs)
    recommendation_count = len(recommendations)
    _add_trace(
        trace=trace,
        step=3,
        name="分数线查询",
        tool="score_tool.search_scores",
        status="success",
        input_data={
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "major": payload.major,
            "matched_job_count": len(matched_jobs),
            "requested_position_code": recommendation_position_code,
        },
        output_summary=_build_score_trace_summary(payload, score_references),
    )

    job_analysis_llm_count = _generate_job_card_analyses(payload, recommendations)
    _add_trace(
        trace=trace,
        step=4,
        name="岗位展开分析",
        tool="llm_service.generate_llm_json",
        status="success" if job_analysis_llm_count else "warning",
        input_data={
            "matched_job_count": recommendation_count,
            "llm_analysis_count": job_analysis_llm_count,
        },
        output_summary=(
            f"已使用大模型生成 {job_analysis_llm_count} 条岗位展开分析。"
            if job_analysis_llm_count
            else "岗位展开分析使用规则兜底；LLM 未配置或调用失败。"
        ),
    )

    policy_result = search_job_policy_sources(payload, recommendations)
    policy_error = policy_result.get("error", "")
    policy_tool_used = policy_result.get("status") != "skipped"
    _add_trace(
        trace=trace,
        step=5,
        name="政策依据检索",
        tool="policy_tool.search_job_policy_sources",
        status=policy_result.get("status", "error"),
        input_data={
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "education": payload.education,
            "major": payload.major,
            "identity": payload.identity,
            "question": payload.question,
            "policy_query": policy_result.get("query", ""),
        },
        output_summary=_build_policy_trace_summary(policy_result),
    )

    risks = analyze_risks(
        payload=payload,
        matched_jobs=recommendations,
        score_references=score_references,
        policy_error=policy_error,
    )
    risks = [
        cleaned
        for item in risks
        if (cleaned := _sanitize_user_facing_text(item))
    ]
    _add_trace(
        trace=trace,
        step=6,
        name="风险分析",
        tool="risk_tool.analyze_risks",
        status="success",
        input_data={
            "matched_job_count": recommendation_count,
            "score_reference_count": len(score_references),
            "has_policy_error": bool(policy_error),
        },
        output_summary=f"生成 {len(risks)} 条风险提醒。",
    )

    recommended_directions = build_recommended_directions(payload, recommendations)
    fallback_report = build_rule_analysis_report(
        payload=payload,
        intent=intent,
        recommended_directions=recommended_directions,
        matched_jobs=recommendations,
        score_references=score_references,
        risks=risks,
        policy_result=policy_result,
    )
    fallback_report = _append_job_policy_context(fallback_report, policy_result)

    prompt = build_analysis_prompt(
        payload=payload,
        intent=intent,
        rule_summary=fallback_report,
        recommended_directions=recommended_directions,
        matched_jobs=recommendations,
        recommendation_count=recommendation_count,
        score_references=score_references,
        risks=risks,
        sources=policy_result.get("sources", []),
        policy_answer=_public_policy_answer(policy_result),
    )
    _add_trace(
        trace=trace,
        step=7,
        name="提示词构建",
        tool="prompt_builder.build_analysis_prompt",
        status="success",
        input_data={
            "recommended_direction_count": len(recommended_directions),
            "matched_job_count": recommendation_count,
            "recommendation_count": recommendation_count,
            "score_reference_count": len(score_references),
            "risk_count": len(risks),
            "source_count": len(policy_result.get("sources", [])),
        },
        output_summary=f"已构建大模型提示词，长度约 {len(prompt)} 个字符。",
    )

    llm_result = generate_llm_summary(
        prompt=prompt,
        fallback_report=fallback_report,
    )
    analysis_report = _ensure_analysis_report(
        llm_result=llm_result,
        fallback_report=fallback_report,
    )
    analysis_report = _apply_report_data_semantics(
        report=analysis_report,
        payload=payload,
        score_references=score_references,
        sources=policy_result.get("sources", []),
    )
    analysis_report = _enforce_recommendation_report_accuracy(
        report=analysis_report,
        payload=payload,
        matched_jobs=recommendations,
        recommendation_count=recommendation_count,
        fallback_report=fallback_report,
    )
    analysis_report = _append_job_policy_context(analysis_report, policy_result)
    analysis_report = _sanitize_user_facing_text(analysis_report)
    quick_conclusion = build_quick_conclusion(
        payload=payload,
        matched_jobs=recommendations,
        score_references=score_references,
    )
    _add_trace(
        trace=trace,
        step=8,
        name="LLM 分析总结",
        tool="llm_service.generate_llm_summary",
        status="success" if llm_result.get("llm_used") else "warning",
        input_data={
            "llm_configured": bool(llm_result.get("llm_used")),
        },
        output_summary=(
            "已使用大模型生成自然语言分析报告。"
            if llm_result.get("llm_used")
            else llm_result.get("error", "未使用大模型，已返回规则版总结。")
        ),
    )

    return AgentAnalyzeResponse(
        intent=intent,
        summary=quick_conclusion,
        analysis_report=analysis_report,
        recommended_directions=recommended_directions,
        risks=risks,
        sources=policy_result.get("sources", []),
        citations=policy_result.get("sources", []),
        rag_used=_rag_result_used(policy_result),
        rag_answer=_public_policy_answer(policy_result),
        matched_jobs=recommendations,
        score_references=score_references,
        llm_used=bool(llm_result.get("llm_used") or decision.get("llm_used") or job_analysis_llm_count),
        tool_used=True,
        used_tools=[
            "job_tool.search_jobs",
            "score_tool.search_scores",
            *(
                ["policy_tool.search_job_policy_sources"]
                if policy_tool_used
                else []
            ),
            "risk_tool.analyze_risks",
        ],
        need_follow_up=False,
        missing_fields=[],
        recommendations=recommendations,
        trace=trace,
        **_build_response_debug(
            payload=payload,
            matched_jobs=recommendations,
            recommendation_count=recommendation_count,
            fallback_reason="" if recommendations else _build_no_jobs_fallback_reason(payload),
        ),
    )


def _analyze_current_job_request(
    payload: AgentAnalyzeRequest,
    trace: list[dict[str, Any]],
    current_job: dict,
) -> AgentAnalyzeResponse:
    job = _build_current_job_record(payload, current_job)
    report = _build_current_job_analysis_report(payload, job)
    score_references = _build_current_job_score_references(job)
    _add_trace(
        trace=trace,
        step=len(trace) + 1,
        name="当前岗位上下文",
        tool="conversation.current_job",
        status="success",
        input_data={
            "position_code": job.get("position_code"),
            "position_name": job.get("position_name"),
        },
        output_summary="已使用最近岗位卡片处理“这个岗位”的上下文指代，未重新执行泛化分数检索。",
    )
    return _build_single_job_response(
        payload=payload,
        intent="single_job_query",
        trace=trace,
        summary=_current_job_direct_conclusion(job),
        analysis_report=report,
        matched_jobs=[job],
        score_references=score_references,
        prompt_scene="single_job_analysis",
        is_context_followup=True,
    )


def _analyze_selection_strategy_request(
    payload: AgentAnalyzeRequest,
    trace: list[dict[str, Any]],
) -> AgentAnalyzeResponse:
    answer = (
        "直接结论：\n"
        "先别急着看分数，选岗先看资格，再看分数，最后看竞争。\n\n"
        "专业不限岗位：\n"
        "岗位专业不限不构成专业门槛，但可报人群可能更大；"
        "没有报名人数和竞争比时，不能直接判断报名热度或竞争强弱。\n\n"
        "公安 / 人民警察岗：\n"
        "通常还要额外关注体检、体测、视力、政审等要求，"
        "具体以公告、职位表和体检标准文件为准，不能只看分数。\n\n"
        "招 1 人岗位：\n"
        "容错率低，可以冲，但不适合当唯一选择；历史低分不代表今年也低。\n\n"
        "下一步：\n"
        "先补充学历、专业和身份画像，再把能报岗位放进备选池做对比。"
    )
    _add_trace(
        trace=trace,
        step=len(trace) + 1,
        name="选岗策略解释",
        tool="exam_agent.selection_strategy",
        status="success",
        input_data={"question": payload.question},
        output_summary="选岗方法问题直接解释，未查询岗位或分数记录。",
    )
    return _build_chat_only_response(
        payload=payload,
        intent="selection_strategy",
        trace=trace,
        summary=answer,
        trace_summary="选岗策略和岗位类别风险解释不触发数据工具。",
        prompt_scene="selection_strategy",
    )


def _build_current_job_record(payload: AgentAnalyzeRequest, current_job: dict) -> dict:
    position_code = _normalize_position_code(current_job.get("position_code"))
    position_name = (
        current_job.get("job_title")
        or current_job.get("position_name")
        or current_job.get("position")
        or (f"职位代码 {position_code}" if position_code else "当前岗位")
    )
    region = (
        current_job.get("province")
        or current_job.get("region")
        or payload.region
        or ""
    )
    recruit_count = _safe_optional_int(current_job.get("recruit_count"))
    min_score = _safe_optional_float(current_job.get("min_score"))
    applicant_count = _safe_optional_int(
        current_job.get("registration_count")
        if current_job.get("registration_count") is not None
        else current_job.get("applicant_count")
    )
    score_match_type = str(current_job.get("score_match_type") or "no_match")
    score_match_reason = str(current_job.get("score_match_reason") or "").strip()
    score_source_type = str(current_job.get("score_source_type") or "").strip()
    if score_source_type in {"review_candidate_sample", "candidate_score_sample"}:
        score_match_type = score_source_type
        if not score_match_reason:
            score_match_reason = (
                "该数据由资格复审名单按岗位聚合得到，不等同于官方最低进面分。"
                if score_source_type == "review_candidate_sample"
                else "该数据由候选人成绩表按岗位聚合得到，不等同于岗位官方最低进面分。"
            )
    elif min_score is None:
        score_match_type = "no_match"
        score_match_reason = "暂无该岗位精确分数记录"
    elif score_match_type == "exact_position_code":
        score_match_reason = (
            f"职位代码 {position_code} 精确匹配"
            if position_code
            else "职位代码精确匹配"
        )
    elif score_match_type not in {
        "partial_position_code",
        "fuzzy_high_confidence",
        "similar_reference",
    }:
        score_match_type = "similar_reference"
        score_match_reason = "当前分数为历史参考，非该岗位职位代码精确匹配"
    elif not score_match_reason:
        score_match_reason = "当前分数为历史参考，非该岗位职位代码精确匹配"
    result = {
        "job_id": position_code or "current-job-context",
        "year": _safe_int(current_job.get("year")) or 2025,
        "target": payload.target,
        "exam_type": current_job.get("exam_type") or payload.exam_type,
        "region": region,
        "province": canonical_province(region) or region,
        "city": current_job.get("city") or payload.city,
        "position_code": position_code,
        "display_position_code": position_code,
        "full_position_code": position_code,
        "department": current_job.get("department") or "",
        "unit": current_job.get("department") or "",
        "unit_name": current_job.get("unit_name") or current_job.get("department") or "",
        "position": position_name,
        "position_name": position_name,
        "education_required": current_job.get("education_requirement") or "",
        "education_requirement": current_job.get("education_requirement") or "",
        "degree_requirement": current_job.get("degree_requirement") or "",
        "major_required": current_job.get("major_requirement") or "",
        "major_requirement": current_job.get("major_requirement") or "",
        "identity_required": current_job.get("identity_requirement") or "不限",
        "identity_requirement": current_job.get("identity_requirement") or "不限",
        "political_requirement": current_job.get("political_requirement") or "",
        "grassroots_requirement": current_job.get("grassroots_requirement") or "",
        "qualification_requirement": current_job.get("qualification_requirement") or "",
        "agency_level": current_job.get("agency_level") or "",
        "is_public_service": current_job.get("is_public_service") or "",
        "is_law_enforcement": current_job.get("is_law_enforcement") or "",
        "job_description": current_job.get("job_description") or "",
        "contact_phone": current_job.get("contact_phone") or "",
        "work_address": current_job.get("work_address") or "",
        "remark": current_job.get("remark") or "",
        "headcount": recruit_count or 0,
        "recruit_count": recruit_count or 0,
        "applicants_count": applicant_count,
        "applicant_count": applicant_count,
        "interview_count": _safe_optional_int(current_job.get("interview_count")),
        "min_interview_score": min_score,
        "min_score": min_score,
        "avg_score": _safe_optional_float(current_job.get("avg_score")),
        "max_score": _safe_optional_float(current_job.get("max_score")),
        "competition_ratio": current_job.get("competition_ratio") or None,
        "score_match_type": score_match_type,
        "score_match_reason": score_match_reason,
        "score_match_confidence": _safe_optional_float(
            current_job.get("score_match_confidence")
        ),
        "score_confidence": _safe_optional_float(
            current_job.get("score_match_confidence")
        ),
        "notes": current_job.get("notes") or "",
        "recommendation_reason": "这是当前对话中最近展示或选择的岗位卡片。",
        "risk_summary": _build_context_job_risk_summary(current_job),
        "data_source_label": current_job.get("data_source_label") or "",
        "score_data_source_label": current_job.get("score_data_source_label") or "",
        "score_source_type": score_source_type,
        "score_sample_count": _safe_int(current_job.get("score_sample_count")),
        "candidate_score_sample_count": _safe_int(
            current_job.get("candidate_score_sample_count")
        ),
        "review_score_sample": current_job.get("review_score_sample") or {},
        "candidate_score_sample": current_job.get("candidate_score_sample") or {},
    }
    score_stat_fields = [
        "review_written_score_min",
        "review_written_score_avg",
        "review_written_score_max",
        "review_xingce_score_min",
        "review_xingce_score_avg",
        "review_xingce_score_max",
        "review_shenlun_score_min",
        "review_shenlun_score_avg",
        "review_shenlun_score_max",
        "review_professional_score_min",
        "review_professional_score_avg",
        "review_professional_score_max",
        "review_total_score_min",
        "review_total_score_avg",
        "review_total_score_max",
        "review_rank_min",
        "review_rank_max",
        "candidate_written_score_min",
        "candidate_written_score_avg",
        "candidate_written_score_max",
        "candidate_interview_score_min",
        "candidate_interview_score_avg",
        "candidate_interview_score_max",
        "candidate_total_score_min",
        "candidate_total_score_avg",
        "candidate_total_score_max",
        "candidate_rank_min",
        "candidate_rank_max",
    ]
    for field_name in score_stat_fields:
        result[field_name] = _safe_optional_float(current_job.get(field_name))
    return result


def _build_context_job_risk_summary(job: dict) -> str:
    risks: list[str] = []
    if _safe_optional_int(job.get("recruit_count")) == 1:
        risks.append("只招 1 人，结果波动和低容错风险更高")
    if job.get("registration_count") is None:
        risks.append("暂无报名人数")
    if not job.get("competition_ratio"):
        risks.append("暂无竞争比")
    if _is_police_job(job):
        risks.append("需额外核对体检、体测、视力和政审要求")
    return "；".join(risks)


def _build_current_job_score_references(job: dict) -> list[dict]:
    if str(job.get("score_source_type") or "") in {
        "review_candidate_sample",
        "candidate_score_sample",
    }:
        return []
    min_score = _safe_optional_float(job.get("min_score"))
    if min_score is None:
        return []
    return [
        {
            "score_id": job.get("position_code") or "",
            "year": job.get("year") or 0,
            "target": job.get("target") or "",
            "exam_type": job.get("exam_type") or "",
            "region": job.get("province") or job.get("region") or "",
            "city": job.get("city") or "",
            "position_code": job.get("position_code") or "",
            "display_position_code": job.get("position_code") or "",
            "full_position_code": job.get("position_code") or "",
            "department": job.get("department") or "",
            "unit": job.get("unit") or "",
            "position_name": job.get("position_name") or "",
            "recruit_count": job.get("recruit_count"),
            "interview_count": job.get("interview_count"),
            "min_interview_score": min_score,
            "min_score": min_score,
            "source_type": "current_job_context",
            "data_status": "historical_reference",
        }
    ]


def _current_job_direct_conclusion(job: dict) -> str:
    title = job.get("position_name") or "当前岗位"
    return (
        f"仅凭历史最低进面分不能判断【{title}】能不能报。"
        "能否报考先看学历、专业、身份和岗位备注等资格门槛；"
        "通过硬性条件后，历史分数才适合作为风险参考。"
    )


def _build_current_job_analysis_report(payload: AgentAnalyzeRequest, job: dict) -> str:
    qualification = (
        "先逐项核对学历、专业、身份和岗位备注。"
        "当前卡片只能用于分析，不能替代官方资格审查。"
    )
    min_score = _safe_optional_float(job.get("min_score"))
    score_match_type = str(job.get("score_match_type") or "no_match")
    score_source_type = str(job.get("score_source_type") or "")
    if score_source_type == "review_candidate_sample":
        sample_count = _safe_int(job.get("score_sample_count"))
        average_score = _safe_optional_float(job.get("review_written_score_avg"))
        average_text = f"，平均笔试分 {average_score:g}" if average_score is not None else ""
        score_text = (
            f"该岗位有资格复审成绩样本 {sample_count} 条，"
            f"入围样本最低笔试分 {min_score:g}{average_text}。"
            "这些数据来自资格复审名单聚合，不等同于官方最低进面分。"
            if min_score is not None
            else f"该岗位有资格复审成绩样本 {sample_count} 条，但暂无可用笔试分统计。"
        )
    elif score_source_type == "candidate_score_sample":
        sample_count = _safe_int(
            job.get("candidate_score_sample_count") or job.get("score_sample_count")
        )
        score_text = (
            f"该岗位有候选人成绩样本 {sample_count} 条，"
            "聚合结果只用于分数分布参考，不等同于岗位官方最低进面分。"
        )
    elif min_score is not None and score_match_type == "exact_position_code":
        score_text = (
            f"该岗位有职位代码精确匹配的历史最低进面分 {min_score:g}，"
            "可以作为往年门槛参考，但不代表今年难度。"
        )
    elif min_score is not None:
        score_text = (
            f"当前卡片中的 {min_score:g} 仅是同类或历史参考，"
            "不是该岗位精确进面分。"
        )
    else:
        score_text = "暂无该岗位精确进面分记录，不能据此判断分数压力。"

    data_gaps = []
    if job.get("applicant_count") is None:
        data_gaps.append("暂无报名人数，不能判断报名热度。")
    if not job.get("competition_ratio"):
        data_gaps.append("暂无竞争比，不能判断竞争强弱。")
    if not data_gaps:
        data_gaps.append("当前卡片已有报名和竞争数据，仍需确认数据年份与官方口径。")

    special_risk = ""
    if _is_police_job(job):
        special_risk = (
            "\n\n特殊岗位提醒：\n"
            "公安岗通常还要关注体检、体测、视力、政审等要求，"
            "具体以公告、职位表和体检标准文件为准。"
        )
    headcount_risk = ""
    if _safe_int(job.get("recruit_count")) == 1:
        headcount_risk = "\n* 该岗位只招 1 人，结果波动和低容错风险更高。"

    return (
        "直接结论：\n"
        f"{_current_job_direct_conclusion(job)}\n\n"
        "资格判断：\n"
        f"{qualification}\n\n"
        "分数参考：\n"
        f"{score_text}\n\n"
        "数据缺口：\n"
        + "\n".join(f"* {item}" for item in data_gaps)
        + headcount_risk
        + special_risk
        + "\n\n下一步：\n"
        "先核对公告和职位表中的资格条件；再补充你的笔试分数或完整画像，"
        "才能继续判断这个岗位是否值得放进备选。"
    )


def _analyze_single_job_request(
    payload: AgentAnalyzeRequest,
    intent: str,
    trace: list[dict[str, Any]],
    requested_position_code: str,
) -> AgentAnalyzeResponse:
    job_lookup = find_single_job(
        target=payload.target,
        exam_type=payload.exam_type,
        region=payload.region,
        city=payload.city,
        query=payload.question,
    )
    _add_trace(
        trace=trace,
        step=2,
        name="单岗位定位",
        tool="job_tool.find_single_job",
        status=job_lookup.get("status", "not_found"),
        input_data={
            "mode": "single_job_query",
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "city": payload.city,
            "question": payload.question,
            "requested_position_code": requested_position_code,
        },
        output_summary=_build_single_lookup_trace_summary(job_lookup, "职位表"),
    )

    score_lookup = find_single_score_reference(
        target=payload.target,
        exam_type=payload.exam_type,
        region=payload.region,
        city=payload.city,
        query=payload.question,
    )
    _add_trace(
        trace=trace,
        step=3,
        name="单岗位分数线定位",
        tool="score_tool.find_single_score_reference",
        status=score_lookup.get("status", "not_found"),
        input_data={
            "mode": "single_job_query",
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "city": payload.city,
            "question": payload.question,
            "requested_position_code": requested_position_code,
        },
        output_summary=_build_single_lookup_trace_summary(score_lookup, "分数线"),
    )

    ambiguous_message = _single_lookup_message(job_lookup)
    if not ambiguous_message and job_lookup.get("status") != "found":
        ambiguous_message = _single_lookup_message(score_lookup)
    if ambiguous_message:
        return _build_single_job_response(
            payload=payload,
            intent=intent,
            trace=trace,
            summary=ambiguous_message,
            matched_jobs=[],
            score_references=[],
        )

    matched_jobs: list[dict] = []
    score_references: list[dict] = []
    match_type = job_lookup.get("match_type") or score_lookup.get("match_type") or ""

    if job_lookup.get("status") == "found" and job_lookup.get("job"):
        job = _build_single_query_job(
            payload=payload,
            job=job_lookup["job"],
            match_type=match_type,
        )
        score_references = _single_score_references_for_job(
            payload=payload,
            job=job,
            score_lookup=score_lookup,
        )
        attach_scores_to_jobs([job], score_references)
        _attach_score_samples_to_jobs(payload, [job])
        matched_jobs = [job]
    elif score_lookup.get("status") == "found" and score_lookup.get("score"):
        score = score_lookup["score"]
        score_references = [score]
        score_job = _build_score_reference_job(
            payload=payload,
            score=score,
            position_code=_normalize_position_code(score.get("position_code") or score.get("score_id")),
        )
        _apply_single_score_match_text(score_job, match_type)
        matched_jobs = [score_job]

    if not matched_jobs:
        return _build_single_job_response(
            payload=payload,
            intent=intent,
            trace=trace,
            summary=SINGLE_JOB_NOT_FOUND_MESSAGE,
            matched_jobs=[],
            score_references=[],
        )

    summary = _build_single_job_summary(matched_jobs[0], match_type)
    return _build_single_job_response(
        payload=payload,
        intent=intent,
        trace=trace,
        summary=summary,
        matched_jobs=matched_jobs[:1],
        score_references=score_references[:1],
    )


def _build_single_job_response(
    payload: AgentAnalyzeRequest,
    intent: str,
    trace: list[dict[str, Any]],
    summary: str,
    matched_jobs: list[dict],
    score_references: list[dict],
    analysis_report: str = "",
    prompt_scene: str = "single_job_analysis",
    is_context_followup: bool = False,
) -> AgentAnalyzeResponse:
    score_references = _public_score_references(score_references)
    matched_jobs = _prepare_job_response_fields(payload, matched_jobs)
    job_analysis_llm_count = _generate_job_card_analyses(payload, matched_jobs) if matched_jobs else 0
    policy_result = search_job_policy_sources(payload, matched_jobs)
    policy_tool_used = policy_result.get("status") != "skipped"
    if policy_tool_used:
        _add_trace(
            trace=trace,
            step=len(trace) + 1,
            name="岗位条件政策解释",
            tool="policy_tool.search_job_policy_sources",
            status=policy_result.get("status", "error"),
            input_data={
                "question": payload.question,
                "policy_query": policy_result.get("query", ""),
                "trigger_terms": policy_result.get("trigger_terms", []),
            },
            output_summary=_build_policy_trace_summary(policy_result),
        )
    final_report = _append_job_policy_context(analysis_report or summary, policy_result)
    sources = policy_result.get("sources", [])
    return AgentAnalyzeResponse(
        intent=intent,
        summary=summary,
        analysis_report=final_report,
        recommended_directions=[],
        risks=[],
        sources=sources,
        citations=sources,
        rag_used=_rag_result_used(policy_result),
        rag_answer=_public_policy_answer(policy_result),
        matched_jobs=matched_jobs,
        score_references=score_references,
        llm_used=bool(job_analysis_llm_count),
        tool_used=policy_tool_used,
        used_tools=(
            ["policy_tool.search_job_policy_sources"]
            if policy_tool_used
            else []
        ),
        is_context_followup=is_context_followup,
        trace=trace,
        **_build_response_debug(
            payload=payload,
            matched_jobs=matched_jobs,
            fallback_reason="" if matched_jobs else summary,
            prompt_scene=prompt_scene,
        ),
    )


def _build_chat_only_response(
    payload: AgentAnalyzeRequest,
    intent: str,
    trace: list[dict[str, Any]],
    summary: str,
    trace_summary: str,
    risks: list[str] | None = None,
    llm_used: bool = False,
    need_follow_up: bool = False,
    missing_fields: list[str] | None = None,
    prompt_scene: str = "",
) -> AgentAnalyzeResponse:
    next_step = len(trace) + 1
    _add_trace(
        trace=trace,
        step=next_step,
        name="聊天式回复",
        tool="exam_agent.chat_guard",
        status="success",
        input_data={
            "mode": payload.mode,
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "city": payload.city,
            "education": payload.education,
            "major": payload.major,
            "identity": payload.identity,
            "question": payload.question,
        },
        output_summary=trace_summary,
    )
    return AgentAnalyzeResponse(
        intent=intent,
        summary=summary,
        analysis_report=summary,
        recommended_directions=[],
        risks=risks or [],
        sources=[],
        matched_jobs=[],
        score_references=[],
        llm_used=llm_used,
        tool_used=False,
        used_tools=[],
        need_follow_up=need_follow_up,
        missing_fields=missing_fields or [],
        recommendations=[],
        trace=trace,
        **_build_response_debug(
            payload=payload,
            matched_jobs=[],
            fallback_reason="",
            include_data_source=False,
            prompt_scene=prompt_scene,
        ),
    )


def _analyze_score_or_risk_request(
    payload: AgentAnalyzeRequest,
    trace: list[dict[str, Any]],
) -> AgentAnalyzeResponse:
    payload = _apply_question_region(payload)
    score_references = _public_score_references(
        search_scores(
            target=payload.target,
            exam_type=payload.exam_type,
            region=payload.region,
            major=payload.major,
            matched_jobs=[],
        )
    )
    score_line_count = sum(
        1 for item in score_references if item.get("is_min_score_reference") is not False
    )
    candidate_sample_count = len(score_references) - score_line_count
    _add_trace(
        trace=trace,
        step=len(trace) + 1,
        name="分数线与风险查询",
        tool="score_tool.search_scores",
        status="success" if score_references else "warning",
        input_data={
            "mode": "score_or_risk_query",
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "major": payload.major,
            "question": payload.question,
            "matched_job_count": 0,
        },
        output_summary=(
            f"找到 {score_line_count} 条最低进面分参考、{candidate_sample_count} 条候选人成绩样本；未触发岗位推荐。"
            if score_references
            else "未找到可直接参考的分数线记录；未触发岗位推荐。"
        ),
    )

    risks = [
        "缺少进面分不代表岗位不能报，也不代表竞争一定更小；最终风险仍要结合招录人数、报名热度、岗位限制和官方资格审查判断。"
    ]
    if score_references:
        summary = (
            f"我先按{payload.region or '当前地区'}、{payload.major or '当前专业'}查询了相关记录，"
            f"找到 {score_line_count} 条最低进面分参考、{candidate_sample_count} 条候选人成绩样本。"
            "候选人成绩只是人员成绩样本，不是岗位最低进面线；历史最低进面分也不能替代今年公告和报名阶段数据。\n\n"
            "如果你想看某个具体岗位，请继续发岗位代码、岗位名称或单位名称，我再帮你做单岗位分析。"
        )
    else:
        summary = SCORE_OR_RISK_CLARIFICATION_REPLY

    return AgentAnalyzeResponse(
        intent="score_or_risk_query",
        summary=summary,
        analysis_report=summary,
        recommended_directions=[],
        risks=risks,
        sources=[],
        matched_jobs=[],
        score_references=score_references,
        llm_used=False,
        trace=trace,
        **_build_response_debug(
            payload=payload,
            matched_jobs=[],
            fallback_reason="" if score_references else SCORE_OR_RISK_CLARIFICATION_REPLY,
            include_data_source=False,
        ),
    )


def _analyze_help_qa_request(
    payload: AgentAnalyzeRequest,
    intent: str,
    trace: list[dict[str, Any]],
) -> AgentAnalyzeResponse:
    policy_result = ask_help_policy_question(payload)
    sources = policy_result.get("sources", [])
    _add_trace(
        trace=trace,
        step=2,
        name="帮助问答政策检索",
        tool="policy_tool.ask_help_policy_question",
        status=policy_result.get("status", "fallback"),
        input_data={
            "mode": "help_qa",
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "question": payload.question,
            "policy_query": policy_result.get("query", ""),
        },
        output_summary=policy_result.get("message", "未检索到已导入的相关政策文件，使用通用解释。"),
    )

    if sources:
        answer = _build_rag_help_answer(payload, policy_result)
        response_sources = sources
        llm_used = False
    else:
        answer = _build_unsourced_policy_explanation(payload.question)
        response_sources = []
        llm_used = False
        _add_trace(
            trace=trace,
            step=3,
            name="无来源政策通用解释",
            tool="exam_agent.unsourced_policy_fallback",
            status="warning",
            input_data={
                "mode": "help_qa",
                "has_policy_source": False,
            },
            output_summary="未检索到已导入的相关政策文件，已返回保守的通用理解。",
        )

    risks = [
        "不同地区、不同年份的招考政策可能存在差异，本回答仅用于辅助理解，最终请以官方公告、职位表、报考指南和资格审查结果为准。"
    ]

    return AgentAnalyzeResponse(
        intent=intent,
        summary=answer,
        analysis_report=answer,
        recommended_directions=[],
        risks=risks,
        sources=response_sources,
        citations=response_sources,
        rag_used=_rag_result_used(policy_result),
        rag_answer=_public_policy_answer(policy_result),
        matched_jobs=[],
        score_references=[],
        llm_used=llm_used,
        tool_used=True,
        used_tools=["policy_tool.ask_help_policy_question"],
        trace=trace,
    )


def _build_rag_help_answer(payload: AgentAnalyzeRequest, policy_result: dict) -> str:
    answer = str(policy_result.get("answer") or policy_result.get("policy_answer") or "").strip()
    snippets = [
        str(source.get("snippet") or "").strip()
        for source in policy_result.get("sources", [])
        if str(source.get("snippet") or "").strip()
    ]
    source_text = "\n".join([answer, *snippets[:2]]).strip()
    return _build_structured_help_explanation(
        question=payload.question,
        source_text=source_text,
        has_policy_source=True,
    )


def _append_job_policy_context(report: str, policy_result: dict) -> str:
    """把有来源的政策解释作为岗位分析补充，不参与岗位排序。"""
    base_report = str(report or "").strip()
    sources = policy_result.get("sources", [])
    if not sources:
        return base_report
    if "政策条件补充：" in base_report:
        return base_report

    policy_answer = _public_policy_answer(policy_result)
    if not policy_answer:
        policy_answer = " ".join(
            str(source.get("snippet") or source.get("text_preview") or "").strip()
            for source in sources[:2]
            if str(source.get("snippet") or source.get("text_preview") or "").strip()
        )
    policy_answer = " ".join(policy_answer.split())
    if len(policy_answer) > 600:
        policy_answer = f"{policy_answer[:600]}..."
    if not policy_answer:
        return base_report

    supplement = (
        "政策条件补充：\n"
        f"{policy_answer}\n\n"
        "这部分只用于解释岗位限制，不参与岗位筛选或排序；"
        "最终仍以官方公告、职位表、报考指南和资格审查为准。"
    )
    return f"{base_report}\n\n{supplement}".strip()


def _public_policy_answer(policy_result: dict) -> str:
    if not policy_result.get("sources"):
        return ""
    return _sanitize_user_facing_text(
        policy_result.get("answer") or policy_result.get("policy_answer") or ""
    )


def _public_score_references(score_references: list[dict]) -> list[dict]:
    """Only expose aggregate-safe score-line records, never individual candidate rows."""
    public_rows: list[dict] = []
    for score in score_references or []:
        if not isinstance(score, dict):
            continue
        if (
            score.get("is_min_score_reference") is False
            or str(score.get("score_record_type") or "") == "candidate_score"
            or str(score.get("data_type") or "") == "candidate_score_table"
        ):
            continue
        public_row = dict(score)
        for field_name in [
            "candidate_name",
            "candidate_no",
            "id_card",
            "mobile",
            "phone",
            "raw_row_json",
        ]:
            public_row.pop(field_name, None)
        public_rows.append(public_row)
    return public_rows


def _rag_result_used(policy_result: dict) -> bool:
    return bool(
        policy_result.get("used_retrieval")
        and policy_result.get("sources")
    )

def _build_help_fallback_prompt(payload: AgentAnalyzeRequest) -> str:
    return (
        "你是招考政策帮助助手。当前没有检索到已导入的相关政策文件，请只做通用概念解释，"
        "不要说“根据公告”，不要伪造来源，不要推导具体年份届别或具体省份认定口径，"
        "不要把社保、劳动关系、档案或就业手续中的任一因素写成确定结论。"
        "回答按“直接结论、一般理解、你现在要做、边界提醒”组织。\n\n"
        f"问题：{payload.question}"
    )


def _build_basic_help_explanation(question: str) -> str:
    return _build_unsourced_policy_explanation(question)


def _clean_help_fallback_answer(answer: str, question: str = "") -> str:
    value = _sanitize_help_user_text(answer)
    forbidden_unsourced_claims = [
        "2023届",
        "2024届",
        "2025届",
        "毕业两年内",
        "未缴纳职工社保就",
        "缴纳社保就不算",
        "广西省考报名场景",
    ]
    if (
        not value
        or len(value) < 160
        or any(claim in value for claim in forbidden_unsourced_claims)
    ):
        return _build_basic_help_explanation(question)
    return value.replace("根据官方公告", "一般来说").replace("依据官方公告", "一般来说")


def _build_unsourced_policy_explanation(question: str) -> str:
    text = str(question or "")
    if re.search(r"(应届|应届生|应届毕业生)", text):
        return (
            "直接结论：\n"
            "应届生身份不是只看你毕业多久，关键看目标省份当年公告和资格审查口径。\n\n"
            "一般理解：\n"
            "通常可能核对毕业时间、劳动关系、社保缴纳记录、档案和就业手续等因素，"
            "但不同地区、不同考试的口径可能不同，任何单一因素都不能直接替代官方认定。\n\n"
            "你现在要做：\n"
            "1. 看目标省份当年公告里的“应届毕业生”“择业期”“高校毕业生”定义。\n"
            "2. 看职位表备注是否限制“限应届”。\n"
            "3. 拿不准就联系招录单位确认。\n\n"
            "边界提醒：\n"
            "当前未命中已导入政策文件，以上只能作为通用理解，"
            "最终以官方公告、职位表和资格审查结果为准。"
        )

    return (
        "直接结论：\n"
        "这类资格或政策问题不能只按日常理解判断，要以目标地区当年公告和职位表口径为准。\n\n"
        "一般理解：\n"
        "可以先确认概念涉及的学历、身份、经历、证明材料和岗位备注，但不能据此直接认定自己符合。\n\n"
        "你现在要做：\n"
        "1. 查当年公告、报考指南和职位表备注。\n"
        "2. 核对需要提交的证明材料和资格审查要求。\n"
        "3. 条件边界不清时联系招录单位确认。\n\n"
        "边界提醒：\n"
        "当前未命中已导入政策文件，以上只能作为通用理解，"
        "最终以官方公告、职位表和资格审查结果为准。"
    )


def _build_structured_help_explanation(
    question: str,
    source_text: str = "",
    has_policy_source: bool = False,
) -> str:
    topic = _match_help_topic(question)
    source_note = _build_help_source_note(source_text, has_policy_source)
    return _sanitize_help_user_text(
        "\n\n".join(
            [
                topic["concept"],
                f"判断时，建议重点看这些条件：{topic['conditions']}",
                f"放到公务员、省考和岗位报名场景里，{topic['scenario']} {source_note}",
                "最后要提醒的是，不同地区、不同年份的招考政策可能存在差异，不能只凭经验或他人的报名结果判断自己一定符合。正式报名和资格复审前，请同时核对官方公告、职位表、报考指南、专业目录、岗位备注以及招录单位的资格审查要求；如果条件边界不清楚，建议向招录单位咨询确认。"
            ]
        )
    )


def _match_help_topic(question: str) -> dict[str, str]:
    text = str(question or "").strip()
    topics = [
        {
            "keywords": ("最低进面分", "进面分", "进面线"),
            "concept": "最低进面分通常是指某个岗位或某类岗位在上一轮考试中，进入面试人员里最低的笔试成绩。它反映的是当年该岗位的竞争结果，不是官方提前设定的固定分数线，也不等于今年报考同一岗位一定需要达到的分数。",
            "conditions": "年份是否一致、岗位代码或岗位类别是否一致、招录人数是否变化、报名人数和缴费人数是否变化、考试科目和计分方式是否相同，以及是否存在合并岗位、递补、调剂等情况。只看一个最低分，容易忽略岗位热度和资格条件变化。",
            "scenario": "如果你在省考报名时用最低进面分做参考，可以把它当作竞争强弱的历史信号：分数高通常说明竞争更集中，分数低也不代表今年就容易。更稳妥的做法是把职位表条件、招录人数、地区热度和历年进面情况放在一起看。",
        },
        {
            "keywords": ("服务基层项目", "基层项目", "三支一扶", "西部计划", "大学生村官"),
            "concept": "服务基层项目人员通常是指参加过规定基层服务项目，并且服务期、考核结果、证明材料等达到招考要求的人员。常见项目可能包括三支一扶、大学生村官、西部计划、特岗教师等，但不同考试认可的项目范围并不完全相同。",
            "conditions": "项目名称是否属于当年认可范围、服务期是否届满、考核是否合格、是否仍在服务期内、是否已经享受过定向招录政策、证明材料由哪个主管部门出具，以及岗位备注是否要求特定地区或特定项目经历。",
            "scenario": "在公务员或省考报名中，如果职位表写明面向服务基层项目人员，普通考生一般不能按这个身份报考。即使你确实参加过基层服务，也要确认项目类型、服务年限和证明材料能够对应岗位要求，避免初审通过后在资格复审阶段被要求补充材料或被认定不符合条件。",
        },
        {
            "keywords": ("应届", "应届生", "应届毕业生"),
            "concept": "应届生身份通常不是只看“今年毕业”这一个条件，而是要结合毕业时间、是否处在择业期、是否已经落实工作单位、是否签订劳动合同、是否缴纳社保、档案和组织关系是否保留在学校或人才服务机构等因素综合判断。",
            "conditions": "毕业年份、学历层次、是否取得毕业证和学位证、是否落实工作单位、是否缴纳职工社保、档案去向、报到证或就业手续、择业期口径，以及职位表是否只写“应届高校毕业生”还是写了更具体的年份限制。",
            "scenario": "在公务员省考报名中，职位表如果明确要求应届高校毕业生，考生就需要确认自己是否符合当年公告对应届身份的定义。有些考试只认可当年毕业生，有些会把择业期内未落实工作的毕业生也纳入范围，所以不能只凭自己的理解判断能不能报。",
        },
        {
            "keywords": ("专业", "计算机类", "软件工程", "专业要求", "专业目录"),
            "concept": "专业要求是职位表中决定能不能报考的核心条件之一，通常会用专业类别、具体专业名称或“不限专业”等方式表达。专业名称相近并不一定代表可以报考，同一个专业在不同目录、不同学历层次下也可能归入不同类别。",
            "conditions": "职位表写的是专业大类还是具体专业名称，学历层次对应的专业目录是否一致，毕业证上的专业名称是否完全匹配，岗位备注是否扩大或收紧专业范围，是否允许相近专业报考，以及招录单位是否有补充解释。",
            "scenario": "在公务员、省考岗位报名时，如果岗位写“计算机类”，软件工程能否报考要看当年适用的专业目录和职位表备注；如果岗位写的是具体专业名称，就更要核对毕业证专业是否一致。不要只按字面相似、课程相近或就业方向相近来判断。",
        },
        {
            "keywords": ("没有进面分", "暂无进面分", "进面名单", "分数线数据"),
            "concept": "岗位显示暂无进面分，通常表示当前只能看到职位表或岗位条件，还没有可对应到该岗位的历年进面名单、最低进面分或分数线记录。这不代表岗位没有竞争，也不代表该岗位一定容易或一定难。",
            "conditions": "是否已导入对应年份的进面名单，岗位代码是否发生变化，岗位名称或单位名称是否调整，历年数据是否能和当前职位表精确对应，以及该岗位是否为新增岗位、合并岗位或名称变动较大的岗位。",
            "scenario": "在省考选岗时，没有进面分的岗位仍然可以纳入备选，但不能用空白数据推断竞争小。你需要更多看职位表限制、招录人数、地区热度、专业宽窄、工作地点和个人条件匹配度，等报名阶段人数和后续分数数据补充后再判断风险。",
        },
        {
            "keywords": ("资格复审", "复审", "材料", "证明材料"),
            "concept": "资格复审是在笔试、面试或体检等环节前后，对考生报名信息和报考资格进行再次核验的环节。它不是简单交材料，而是确认你的学历、专业、身份、年龄、基层经历、政治面貌等条件是否和职位要求一致。",
            "conditions": "身份证明、毕业证和学位证、学历认证材料、专业名称、户籍或生源要求、应届身份材料、基层项目证明、工作经历证明、单位同意报考证明、职位表备注要求，以及复审通知中列出的提交时间和提交方式。",
            "scenario": "在公务员和省考报名中，网上初审通过并不等于最终资格一定成立。资格复审阶段如果材料不完整、专业不一致、身份口径不符合或证明出具单位不符合要求，都可能影响后续环节，所以报名时就要按复审标准提前准备。",
        },
    ]
    for topic in topics:
        if any(keyword in text for keyword in topic["keywords"]):
            return topic

    return {
        "concept": "这个问题属于招考条件理解问题，通常不能脱离具体地区、年份、考试类型和职位表单独判断。它的核心是先弄清概念本身，再把概念放回公告、职位表和资格审查要求里核对。",
        "conditions": "当年公告的定义、职位表中的限制条件、岗位备注、报考指南、专业目录、学历学位要求、身份或经历证明材料，以及这些条件之间是否存在同时满足的要求。",
        "scenario": "在公务员、省考或具体岗位报名时，建议先判断自己是否满足硬性条件，再看岗位竞争和个人偏好。只要问题涉及身份、专业、学历、基层经历、户籍或资格材料，就不要只按日常理解判断。",
    }


def _build_help_source_note(source_text: str, has_policy_source: bool) -> str:
    cleaned = _sanitize_help_user_text(source_text)
    if has_policy_source:
        if cleaned:
            return f"已导入的政策文件中，与这个问题相关的内容主要涉及：{_truncate_help_text(cleaned, 180)}。这些内容可以作为理解口径的参考，但仍需要回到原文件和职位表逐项核对。"
        return "本次已检索到已导入的政策文件，但可直接展示的片段较少，因此仍建议打开对应文件并结合职位表继续核对。"

    return "目前没有检索到已导入的相关政策文件，所以这里按常见招考规则整理，只能帮助你理解概念和核对方向，不能当作某份公告的明确结论。"


def _sanitize_help_user_text(text: str) -> str:
    return _sanitize_user_facing_text(text)


def _sanitize_user_facing_text(text: Any) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    rag = "R" + "AG"
    fallback = "fall" + "back"
    chunks = "chunk" + "s"
    retriever = "检索" + "器"
    vector_store = "向量" + "库"
    value = re.sub(
        r"政策依据暂未获取成功[^。！？\n]*(?:[。！？]|$)",
        "暂未获取到可核验的政策依据，请以官方公告和职位表为准。",
        value,
    )
    value = re.sub(r"(?i)rag[_\s-]*builder", "政策文件服务", value)
    replacements = {
        f"本地 {rag} 资料": "已导入的相关政策文件",
        f"本地 {rag} 政策文件": "已导入的相关政策文件",
        f"{rag}政策文件": "政策文件",
        f"{rag} 政策文件": "政策文件",
        f"{rag} 资料": "政策文件",
        f"命中 {rag}": "检索到政策文件",
        f"AI {fallback}": "通用解释",
        fallback: "通用解释",
        chunks: "片段",
        "chunk": "片段",
        retriever: "政策文件查询服务",
        vector_store: "已导入政策文件库",
        rag: "政策文件",
        "Elasticsearch": "政策文件服务",
        "Celery": "后台服务",
        "Redis": "后台服务",
        "MinIO": "文件服务",
        "内部检索器": "政策文件查询服务",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\b[a-z_]+_tool(?:\.[a-z_][a-z0-9_]*)?\b", "系统能力", value)
    value = re.sub(r"\b[\w.-]+\.py\b", "内部模块", value)
    value = re.sub(r"\b(?:jobs|job_scores)_[a-z_]+_\d{4}\.csv\b", "已导入招考数据", value)
    value = re.sub(r"(?i)\btraceback\b", "内部错误信息", value)
    return value


def _truncate_help_text(text: str, max_length: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def _single_score_references_for_job(
    payload: AgentAnalyzeRequest,
    job: dict,
    score_lookup: dict,
) -> list[dict]:
    if score_lookup.get("status") == "found" and score_lookup.get("score"):
        score = score_lookup["score"]
        job_code = _job_position_code(job)
        score_code = _normalize_position_code(score.get("position_code"))
        if not job_code or not score_code or job_code == score_code:
            return [score]

    job_code = _job_position_code(job)
    if not job_code:
        return []

    scores = search_scores(
        target=payload.target,
        exam_type=payload.exam_type,
        region=payload.region,
        major=payload.major,
        matched_jobs=[job],
    )
    return [
        score
        for score in scores
        if _normalize_position_code(score.get("position_code")) == job_code
    ][:1]


def _build_single_query_job(
    payload: AgentAnalyzeRequest,
    job: dict,
    match_type: str,
) -> dict:
    result = dict(job)
    _set_job_position_code_fields(result, _job_position_code(result))
    result["recruit_count"] = _safe_int(result.get("recruit_count") or result.get("headcount"))
    result["applicants_count"] = _safe_optional_int(result.get("applicants_count"))
    result["interview_count"] = _safe_optional_int(result.get("interview_count"))
    result["min_interview_score"] = _safe_optional_float(result.get("min_interview_score"))
    result["max_interview_score"] = _safe_optional_float(result.get("max_interview_score"))
    result["competition_ratio"] = result.get("competition_ratio") or None
    result["competition_score"] = _safe_optional_int(result.get("competition_score"))
    result["competition_level"] = result.get("competition_level") or "未知"
    result["unit"] = result.get("unit") or _extract_note_field(result.get("notes", ""), "用人单位")
    result["work_location"] = result.get("work_location") or _format_score_job_location(payload, result)
    result["qualification_score"] = 0
    result["suitability_score"] = 0
    result["match_score"] = 100 if match_type != "position_fuzzy" else 80
    result["match_level"] = "近似匹配" if match_type == "position_fuzzy" else "精确回查"
    result["short_reason"] = _build_single_short_reason(result, match_type)
    result["risk_summary"] = "这是单岗位查询结果，不代表系统推荐优先级；报名前仍需核对官方职位表和资格审核口径。"
    result["match_reason"] = result["short_reason"]
    result["risk_notes"] = [
        "单岗位查询只负责回查用户指定岗位，不补充其他无关岗位。",
        "资格条件、专业目录和岗位备注仍需以官方职位表为准。",
    ]
    result["verify_notes"] = [
        f"核对职位代码 {result.get('position_code') or result.get('job_id') or '暂无'} 是否对应最新职位表。",
        "核对招录机关、用人单位、岗位名称、专业要求和备注限制。",
    ]
    result["ai_analysis"] = {
        "why_recommended": result["short_reason"],
        "qualification_match": "当前是单岗位回查，没有按用户学历、专业和身份进行推荐排序。",
        "major_match": "是否能报考仍需逐字核对官方专业目录和资格审查口径。",
        "direction_fit": f"岗位名称为“{result.get('position', '')}”，具体职责以职位表和公告为准。",
        "recruit_risk": f"招录人数 {result.get('recruit_count') or result.get('headcount') or '暂无'}，仍需结合报名人数和进面数据判断竞争。",
        "competition_data": "若卡片展示进面分或进面人数，表示已按职位代码关联到已导入分数线记录；缺失字段不会推测。",
        "verify_before_apply": "核对职位代码、招录机关、用人单位、岗位名称、专业目录和岗位备注后再决定是否报名。",
    }
    return result


def _build_single_short_reason(job: dict, match_type: str) -> str:
    code = _job_position_code(job)
    if match_type == "code_exact":
        return f"按职位代码 {code} 精确回查到这条岗位。" if code else "按职位代码精确回查到这条岗位。"
    if match_type == "position_exact":
        return "按岗位名称精确匹配到这条岗位。"
    if match_type == "unit_position_exact":
        return "按单位或招录机关加岗位名称联合匹配到这条岗位。"
    if match_type == "position_fuzzy":
        return SINGLE_JOB_FUZZY_NOTICE
    return "按你输入的岗位信息回查到这条岗位。"


def _apply_single_score_match_text(job: dict, match_type: str) -> None:
    short_reason = _build_single_short_reason(job, match_type)
    job["match_level"] = "近似匹配" if match_type == "position_fuzzy" else "精确回查"
    job["short_reason"] = short_reason
    job["match_reason"] = short_reason
    if isinstance(job.get("ai_analysis"), dict):
        job["ai_analysis"]["why_recommended"] = short_reason


def _build_single_job_summary(job: dict, match_type: str) -> str:
    prefix = SINGLE_JOB_FUZZY_NOTICE if match_type == "position_fuzzy" else "已找到 1 条查询结果。"
    code = _job_position_code(job)
    code_text = f"职位代码 {code}，" if code else ""
    score_text = (
        "已匹配到该岗位分数线记录。"
        if _single_job_has_score_data(job)
        else "当前已导入数据中还没有该岗位的分数线记录。"
    )
    return f"{prefix}{code_text}{job.get('department', '')} - {job.get('position', '')}。{score_text}"


def _single_job_has_score_data(job: dict) -> bool:
    return any(
        job.get(field) is not None
        for field in ["interview_count", "min_interview_score", "max_interview_score"]
    )


def _single_lookup_message(lookup: dict) -> str:
    return lookup.get("message", "") if lookup.get("status") == "ambiguous" else ""


def _build_single_lookup_trace_summary(lookup: dict, source_name: str) -> str:
    status = lookup.get("status")
    if status == "found":
        return f"{source_name}已定位到 1 条记录，匹配方式为 {lookup.get('match_type', '')}。"
    if status == "ambiguous":
        return lookup.get("message", "找到多个相似岗位。")
    return f"{source_name}没有定位到记录。"


def _normalize_mode(mode: str) -> str:
    value = str(mode or "").strip()
    allowed_modes = {
        "single_job_query",
        "job_recommendation",
        "help_qa",
        "policy_qa",
        "score_or_risk_query",
        "selection_strategy",
        "small_talk",
        "greeting",
        "needs_clarification",
    }
    return value if value in allowed_modes else ""


def _is_selection_strategy_question(question: str) -> bool:
    text = "".join(str(question or "").split())
    patterns = [
        r"怎么选岗",
        r"岗位怎么选",
        r"如何选岗",
        r"选岗思路",
        r"帮我分析.*怎么选",
        r"专业不限.*(?:风险|能不能报|怎么选)",
        r"三不限.*(?:风险|能不能报|怎么选)",
        r"(?:公安岗|人民警察岗).*有什么风险",
        r"招\s*1\s*人岗位.*有什么风险",
        r"岗位风险分别是什么",
        r"(?:专业不限岗位|公安岗|人民警察岗|招\s*1\s*人岗位).*(?:分别|各自).*风险",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _references_current_job(question: str) -> bool:
    text = "".join(str(question or "").split())
    phrases = [
        "这个岗位",
        "这个岗",
        "上面这个",
        "上一张岗位卡片",
        "上一个岗位",
        "刚才这个",
        "刚才推荐的岗位",
        "这个公安岗位",
        "这个分数能不能报",
    ]
    return any(phrase in text for phrase in phrases) or bool(
        re.search(r"最低进面分[-+]?\d+(?:\.\d+)?[，,。；;：:\s]*能不能报", text)
    )


def _resolve_current_job_context(payload: AgentAnalyzeRequest) -> dict:
    current_job = _model_to_dict(getattr(payload, "current_job", None))
    if current_job:
        return current_job

    recommendations = [
        item
        for value in (getattr(payload, "last_recommendations", []) or [])
        if (item := _model_to_dict(value))
    ]
    if not recommendations:
        return {}
    if _question_claims_police_job(payload.question):
        police_jobs = [job for job in recommendations if _is_police_job(job)]
        if len(police_jobs) == 1:
            return police_jobs[0]
    return recommendations[0]


def _model_to_dict(value: Any) -> dict:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value) if isinstance(value, dict) else {}


def _question_claims_police_job(question: str) -> bool:
    return bool(re.search(r"(这个公安岗位|这个人民警察岗位|这个警务岗位)", str(question or "")))


def _is_police_job(job: dict) -> bool:
    text = " ".join(
        str(job.get(field) or "")
        for field in [
            "department",
            "unit",
            "job_title",
            "position_name",
            "position",
            "notes",
        ]
    )
    return bool(re.search(r"(公安|人民警察|警务|警察职位)", text))


def _is_incomplete_question(question: str) -> bool:
    text = "".join(str(question or "").split())
    if not text:
        return True
    if text in {"你好", "您好", "在吗", "帮我看看", "看看", "我想考公", "想考公", "我要考公"}:
        return True
    if (
        _references_current_job(text)
        and not _extract_requested_position_code(text)
        and not any(keyword in text for keyword in ["进面分", "分数", "风险", "竞争", "报名人数"])
    ):
        return True
    if len(text) <= 4 and not _extract_requested_position_code(text):
        return True
    return False


def _should_use_single_job_query(
    payload: AgentAnalyzeRequest,
    requested_position_code: str,
) -> bool:
    mode = _normalize_mode(payload.mode)
    if mode == "single_job_query":
        return True
    return not mode and bool(requested_position_code)


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_requested_position_code(question: str) -> str:
    """从用户问题中提取明确指定的职位代码。"""
    text = str(question or "").strip()
    if not text:
        return ""

    contextual_match = re.search(
        r"(?:职位代码|岗位代码|职位编号|岗位编号|position_code)\D{0,12}(\d{6,20})",
        text,
        flags=re.IGNORECASE,
    )
    if contextual_match:
        return _normalize_position_code(contextual_match.group(1))

    prefixed_match = re.search(r"\b[A-Z]{2,}\d{4}[-_]?(\d{6,20})\b", text, flags=re.IGNORECASE)
    if prefixed_match:
        return _normalize_position_code(prefixed_match.group(1))

    if "职位" in text or "岗位" in text:
        standalone_match = re.search(r"(?<!\d)(\d{8,20})(?!\d)", text)
        if standalone_match:
            return _normalize_position_code(standalone_match.group(1))

    standalone_match = re.search(r"(?<!\d)(\d{8,20})(?!\d)", text)
    return _normalize_position_code(standalone_match.group(1)) if standalone_match else ""


def _extract_note_field(notes: str, field_name: str) -> str:
    match = re.search(rf"{re.escape(field_name)}[:：]\s*([^；;，,。]+)", str(notes or ""))
    return match.group(1).strip() if match else ""


def _with_requested_position_code(
    matched_jobs: list[dict],
    payload: AgentAnalyzeRequest,
    requested_position_code: str,
) -> list[dict]:
    if not requested_position_code:
        return matched_jobs
    if any(_job_position_code(job) == requested_position_code for job in matched_jobs):
        return matched_jobs

    return [
        *matched_jobs,
        {
            "job_id": requested_position_code,
            "position_code": requested_position_code,
            "target": payload.target,
            "exam_type": payload.exam_type,
            "region": payload.region,
            "city": payload.city,
        },
    ]


def _ensure_requested_position_result(
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict],
    score_references: list[dict],
    requested_position_code: str,
) -> list[dict]:
    if not requested_position_code:
        return matched_jobs

    for index, job in enumerate(matched_jobs):
        if _job_position_code(job) != requested_position_code:
            continue
        print(f"职位代码精确召回：position_code={requested_position_code} 来源=职位表")
        return [job]

    score = next(
        (
            item
            for item in score_references
            if _normalize_position_code(item.get("position_code")) == requested_position_code
        ),
        None,
    )
    if not score:
        print(f"职位代码精确召回：position_code={requested_position_code} 未找到已导入记录")
        return []

    print(f"职位代码精确召回：position_code={requested_position_code} 来源=分数线记录")
    score_job = _build_score_reference_job(payload, score, requested_position_code)
    return [score_job]


def _build_score_reference_job(
    payload: AgentAnalyzeRequest,
    score: dict,
    position_code: str,
) -> dict:
    position_name = score.get("position_name") or f"职位代码 {position_code}"
    department = score.get("department") or score.get("unit") or "分数线记录"
    min_score = score.get("min_interview_score") or score.get("min_score")
    max_score = score.get("max_interview_score") or score.get("max_score")
    interview_count = score.get("interview_count")
    recruit_count = _safe_int(score.get("recruit_count"))
    location = _format_score_job_location(payload, score)
    source_text = "，".join(
        part
        for part in [score.get("source_type"), score.get("data_status")]
        if part
    )

    return {
        "job_id": position_code,
        "year": score.get("year") or 0,
        "target": score.get("target") or payload.target,
        "exam_type": score.get("exam_type") or payload.exam_type,
        "region": score.get("region") or payload.region,
        "city": score.get("city") or payload.city,
        "position_code": position_code,
        "display_position_code": position_code,
        "full_position_code": position_code,
        "raw_position_code": position_code,
        "source_position_code": position_code,
        "score_match_position_code": position_code,
        "matched_position_code": position_code,
        "source_type": score.get("source_type") or "",
        "data_status": score.get("data_status") or "",
        "job_source_file": "",
        "job_source_year": 0,
        "department": department,
        "unit": score.get("unit") or department,
        "position": position_name,
        "education_required": "待核对职位表",
        "major_required": "待核对职位表",
        "identity_required": "待核对职位表",
        "headcount": recruit_count,
        "recruit_count": recruit_count,
        "applicants_count": None,
        "interview_count": interview_count,
        "min_interview_score": min_score,
        "min_score": min_score,
        "max_interview_score": max_score,
        "avg_score": _safe_optional_float(score.get("avg_score")),
        "max_score": max_score,
        "competition_ratio": None,
        "competition_score": None,
        "competition_level": "未知",
        "work_location": location,
        "notes": (
            "该卡片由已导入的官方进面名单分数线生成；"
            "职位资格条件、招录人数和备注限制仍需回到最新职位表核对。"
        ),
        "qualification_score": 0,
        "suitability_score": 0,
        "match_score": 100,
        "match_level": "精确召回",
        "short_reason": f"按你输入的职位代码 {position_code} 精确召回分数线记录。",
        "risk_summary": (
            f"已接入真实进面数据：进面人数 {interview_count if interview_count is not None else '暂无'}，"
            f"最低进面分 {min_score if min_score is not None else '暂无'}。"
            "但资格条件仍需以职位表为准。"
        ),
        "match_reason": f"用户问题明确指定职位代码 {position_code}，优先展示对应分数线记录。",
        "risk_notes": [
            "这是分数线记录型卡片，不代表已完整接入职位表资格条件。",
            "正式报名前仍需核对最新职位表、公告和专业目录。",
        ],
        "verify_notes": [
            f"核对职位代码 {position_code} 是否对应最新职位表。",
            "核对学历、学位、专业、身份限制和岗位备注。",
        ],
        "score_match_type": "exact_position_code",
        "score_source_type": "score_line",
        "score_source_file": score.get("score_source_file") or "",
        "score_source_year": score.get("score_source_year") or score.get("year") or 0,
        "score_match_confidence": 1.0,
        "score_match_reason": f"职位代码 {position_code} 精确匹配",
        "job_analysis_llm_used": False,
        "job_analysis_model": "",
        "job_analysis_error": "",
        "ai_analysis": {
            "why_recommended": (
                f"你明确输入了职位代码 {position_code}，系统优先展示这条已导入的进面分记录。"
            ),
            "qualification_match": "当前只基于分数线 CSV 精确召回，资格条件需要回到官方职位表核对。",
            "major_match": "专业匹配情况暂未从职位表确认，不能仅凭分数线判断能否报考。",
            "direction_fit": f"岗位名称为“{position_name}”，具体职责需以职位表和公告为准。",
            "recruit_risk": "招录人数和报考人数暂未在这条分数线记录中提供。",
            "competition_data": (
                f"进面人数 {interview_count if interview_count is not None else '暂无'}，"
                f"最低进面分 {min_score if min_score is not None else '暂无'}，"
                f"最高进面分 {max_score if max_score is not None else '暂无'}。"
                f"{source_text + '。' if source_text else ''}"
            ),
            "verify_before_apply": "核对职位代码、职位名称、招录机关、专业目录和岗位备注后再决定是否报名。",
        },
    }


def _format_score_job_location(payload: AgentAnalyzeRequest, score: dict) -> str:
    region = score.get("region") or payload.region
    city = score.get("city") or payload.city
    if region and city:
        return f"{region}-{city}"
    return region or city or ""


def _job_position_code(job: dict) -> str:
    score_match = job.get("score_match") if isinstance(job.get("score_match"), dict) else {}
    raw = job.get("raw") if isinstance(job.get("raw"), dict) else {}
    candidates = [
        _normalize_position_code(job.get("display_position_code")),
        _normalize_position_code(job.get("full_position_code")),
        _normalize_position_code(job.get("position_code")),
        _normalize_position_code(job.get("positionCode")),
        _normalize_position_code(job.get("job_code")),
        _normalize_position_code(job.get("code")),
        _normalize_position_code(job.get("职位代码")),
        _normalize_position_code(job.get("岗位代码")),
        _normalize_position_code(job.get("raw_position_code")),
        _normalize_position_code(job.get("source_position_code")),
        _normalize_position_code(job.get("score_match_position_code")),
        _normalize_position_code(job.get("matched_position_code")),
        _normalize_position_code(score_match.get("position_code")),
        _normalize_position_code(score_match.get("matched_position_code")),
        _normalize_position_code(raw.get("职位代码")),
        _normalize_position_code(raw.get("岗位代码")),
        _normalize_position_code(job.get("job_id")),
    ]
    return max((code for code in candidates if code), key=len, default="")


def _normalize_position_code(value: Any) -> str:
    text = re.sub(r"[\s_#/:：,，;；()（）\[\]【】]+", "", str(value or "").strip())
    if not text:
        return ""
    digit_groups = re.findall(r"\d+", text)
    if digit_groups:
        return max(enumerate(digit_groups), key=lambda item: (len(item[1]), item[0]))[1]
    return text


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


def _generate_job_card_analyses(payload: AgentAnalyzeRequest, matched_jobs: list[dict]) -> int:
    llm_count = 0
    for job in matched_jobs:
        if job.get("data_error"):
            _apply_job_analysis_metadata(job, llm_used=False, model="", error="")
            continue

        fallback_analysis = _fallback_job_analysis(job)
        llm_result = generate_llm_json(
            prompt=_build_job_card_analysis_prompt(payload, job, fallback_analysis),
            fallback_data=fallback_analysis,
        )
        analysis = {
            field: _clean_job_analysis_text(llm_result.get(field)) or fallback_analysis[field]
            for field in JOB_ANALYSIS_FIELDS
        }
        analysis = _enforce_job_analysis_accuracy(
            payload=payload,
            job=job,
            analysis=analysis,
            fallback_analysis=fallback_analysis,
        )
        job["ai_analysis"] = analysis
        llm_used = bool(llm_result.get("llm_used"))
        if llm_used:
            llm_count += 1
        _apply_job_analysis_metadata(
            job,
            llm_used=llm_used,
            model=str(llm_result.get("model") or ""),
            error=str(llm_result.get("error") or ""),
        )
    return llm_count


def _fallback_job_analysis(job: dict) -> dict:
    existing = job.get("ai_analysis") if isinstance(job.get("ai_analysis"), dict) else {}
    return {
        field: _clean_job_analysis_text(existing.get(field)) or _fallback_job_analysis_text(job, field)
        for field in JOB_ANALYSIS_FIELDS
    }


def _fallback_job_analysis_text(job: dict, field: str) -> str:
    fallback_map = {
        "why_recommended": job.get("short_reason") or "这条岗位通过了当前筛选条件，可以作为候选继续核对。",
        "qualification_match": job.get("match_reason") or "学历、专业、身份等条件需要以官方职位表和资格审查为准。",
        "major_match": "专业要求需要逐字核对官方专业目录，长专业列表不代表一定可报。",
        "direction_fit": "岗位方向还要结合职位简介、单位职责和个人职业偏好判断。",
        "recruit_risk": job.get("risk_summary") or "招录人数、报名人数和进面分都会影响最终风险。",
        "competition_data": _job_score_status_text(job),
        "verify_before_apply": "；".join(job.get("verify_notes", [])[:3]) or "报名前核对公告、职位表、专业目录和资格审查口径。",
    }
    return fallback_map[field]


def _build_job_card_analysis_prompt(
    payload: AgentAnalyzeRequest,
    job: dict,
    fallback_analysis: dict,
) -> str:
    recruit_count = _safe_int(job.get("recruit_count") or job.get("headcount"))
    missing_data = []
    if job.get("applicants_count") is None:
        missing_data.append("报名人数")
    if job.get("payment_count") is None:
        missing_data.append("缴费人数")
    if not job.get("competition_ratio"):
        missing_data.append("竞争比")
    if job.get("min_interview_score") is None:
        missing_data.append("最低进面分")

    return f"""
你是中文招考岗位顾问。请基于真实筛选条件、当前岗位字段和分数匹配信息，为“岗位卡片展开分析”生成 JSON。
只返回一个 JSON 对象，不要 markdown，不要解释字段名。字段必须是：
{{
  "why_recommended": "",
  "qualification_match": "",
  "major_match": "",
  "direction_fit": "",
  "recruit_risk": "",
  "competition_data": "",
  "verify_before_apply": ""
}}

写作要求：
- 像真实顾问，不要像模板拼接；不要出现 fallback、LLM、debug 等开发词。
- 不要输出内部 CSV 文件名、磁盘路径、模型名称或服务实现细节。数据来源只能写成用户友好的年份、省份和资料类型。
- 不能大段复制原始专业字段。专业字段很长时，概括成方向，例如统计、数学、计算机、软件工程、网络安全、人工智能、大数据等。
- 如果缺少报名人数、竞争比或进面分，不允许说“稳”“保”“高度推荐”。
- 如果只招 1 人，必须提醒波动风险。
- 如果岗位身份要求是“不限”，只能说用户身份可以报，但不形成身份限制优势。
- 如果用户学历、专业或身份是空值、“不限”或未完善，不得说对应条件已满足，也不得说整体完全符合。
- 如果岗位专业要求是“不限专业”，只能说专业本身不构成门槛，不能说“专业条件可以满足”或“你的专业符合”。
- 只有 score_match_type 是 exact_position_code 时，才能写成该岗位精确进面分；其他匹配类型都必须说明只是历史参考，no_match 要说明暂无该岗位精确进面分。
- applicants_count 为空时只能说暂无报名人数数据；competition_ratio 为空时只能说暂无竞争比数据，不能判断竞争激烈程度。

用户筛选器条件：
- target: {payload.target}
- exam_type: {payload.exam_type}
- region: {payload.region}
- city: {payload.city}
- education: {payload.education}
- major: {payload.major}
- identity: {payload.identity}

当前岗位：
- year: {job.get("year")}
- department: {job.get("department")}
- unit: {job.get("unit")}
- position: {job.get("position_name") or job.get("position")}
- position_code: {job.get("position_code") or job.get("job_id")}
- recruit_count: {recruit_count}
- education_required: {job.get("education_required")}
- major_required: {_summarize_long_field(job.get("major_required"))}
- identity_required: {job.get("identity_required")}
- notes: {_summarize_long_field(job.get("notes"), max_length=180)}

分数匹配：
- min_interview_score: {job.get("min_interview_score")}
- interview_count: {job.get("interview_count")}
- applicants_count: {job.get("applicants_count")}
- competition_ratio: {job.get("competition_ratio")}
- score_match_type: {job.get("score_match_type")}
- score_match_confidence: {job.get("score_match_confidence")}
- score_match_reason: {job.get("score_match_reason")}

数据缺口：{ "、".join(missing_data) if missing_data else "暂无明显缺口" }

规则兜底参考（只能参考语气，不要照抄）：
- why_recommended: {fallback_analysis.get("why_recommended")}
- qualification_match: {fallback_analysis.get("qualification_match")}
- recruit_risk: {fallback_analysis.get("recruit_risk")}
""".strip()


def _apply_job_analysis_metadata(job: dict, llm_used: bool, model: str, error: str) -> None:
    job["job_analysis_llm_used"] = bool(llm_used)
    job["job_analysis_model"] = model
    job["job_analysis_error"] = error


def _clean_job_analysis_text(value: Any) -> str:
    return _sanitize_user_facing_text(value)


def _enforce_job_analysis_accuracy(
    payload: AgentAnalyzeRequest,
    job: dict,
    analysis: dict,
    fallback_analysis: dict,
) -> dict:
    result = dict(analysis)
    profile_missing = any(
        str(value or "").strip() in {"", "不限", "未设置", "未填写", "请选择"}
        for value in [payload.education, payload.major, payload.identity]
    )
    forbidden_profile_claims = [
        "专业条件可以满足",
        "你的专业符合",
        "学历专业身份都满足",
        "整体完全符合",
    ]
    for field in ["qualification_match", "major_match", "why_recommended"]:
        text = str(result.get(field) or "")
        if profile_missing and any(claim in text for claim in forbidden_profile_claims):
            result[field] = fallback_analysis[field]

    recruit_count = _safe_int(job.get("recruit_count") or job.get("headcount"))
    recruit_risk = str(result.get("recruit_risk") or "")
    if recruit_count != 1 and re.search(
        r"只招\s*1\s*人|招录人数为\s*1\s*人|1\s*人岗|一人岗",
        recruit_risk,
    ):
        result["recruit_risk"] = fallback_analysis["recruit_risk"]
    return result


def _summarize_long_field(value: Any, max_length: int = 140) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def _job_score_status_text(job: dict) -> str:
    score_match_type = job.get("score_match_type") or "no_match"
    if score_match_type == "review_candidate_sample":
        count = _safe_int(job.get("score_sample_count"))
        min_score = _safe_optional_float(job.get("review_written_score_min") or job.get("min_score"))
        avg_score = _safe_optional_float(job.get("review_written_score_avg"))
        if min_score is not None:
            avg_text = f"，平均笔试分 {avg_score:g}" if avg_score is not None else ""
            return (
                f"该岗位有资格复审名单成绩样本 {count} 条，参考最低笔试分 {min_score:g}{avg_text}。"
                "这不是官方最低进面分，只能作为入围样本参考。"
            )
        return f"该岗位有资格复审名单成绩样本 {count} 条，但暂未形成官方最低进面分。"
    if score_match_type == "candidate_score_sample":
        count = _safe_int(job.get("score_sample_count"))
        min_score = _safe_optional_float(job.get("candidate_written_score_min") or job.get("min_score"))
        if min_score is not None:
            return f"该岗位有候选人成绩样本 {count} 条，参考最低笔试分 {min_score:g}，不等同于官方最低进面分。"
        return f"该岗位有候选人成绩样本 {count} 条，但暂未形成官方最低进面分。"
    if score_match_type == "exact_position_code":
        min_score = (
            job.get("min_score")
            if job.get("min_score") is not None
            else job.get("min_interview_score")
        )
        interview_count = job.get("interview_count")
        if min_score is None:
            return "该岗位已按职位代码精确匹配历史记录，但历史最低进面分暂无。"
        interview_text = (
            f"进面人数 {interview_count} 人。"
            if interview_count is not None
            else ""
        )
        return (
            f"该岗位有职位代码精确匹配的历史最低进面分 {min_score}，"
            f"可以作为往年门槛参考，但不代表今年难度。{interview_text}"
        )
    if score_match_type in {
        "partial_position_code",
        "fuzzy_high_confidence",
        "similar_reference",
    }:
        min_score = (
            job.get("min_score")
            if job.get("min_score") is not None
            else job.get("min_interview_score")
        )
        value = f"参考分 {min_score}" if min_score is not None else "暂无可展示分数"
        return f"{value}，不是该岗位职位代码精确匹配的进面分，只能作为历史参考。"
    return "暂无该岗位精确进面分。"


def _ensure_analysis_report(llm_result: dict, fallback_report: str) -> str:
    """确保最终 analysis_report 一定不是空字符串。"""
    report = str(llm_result.get("analysis_report") or "").strip()
    if report:
        return report

    fallback_report = (fallback_report or "").strip()
    if fallback_report:
        return fallback_report

    return "规则版分析报告生成失败，请检查岗位、分数线、风险和政策检索结果。"


def _build_policy_trace_summary(policy_result: dict) -> str:
    """根据政策检索结果生成 trace 文案。"""
    status = policy_result.get("status")
    if status == "success":
        source_count = len(policy_result.get("sources", []))
        return f"检索到 {source_count} 条政策来源"

    if status == "empty":
        return "政策文件服务已响应，但没有检索到相关政策来源"

    if status == "skipped":
        return "当前请求不需要政策解释，未调用政策知识库"

    if status == "warning":
        return policy_result.get("output_summary") or policy_result.get(
            "message",
            "未检索到匹配的政策来源",
        )

    if status == "error":
        return "政策文件服务暂不可用，已使用无政策来源模式继续分析"

    return policy_result.get("message", "未检索到政策来源")


def _build_score_trace_summary(
    payload: AgentAnalyzeRequest,
    score_references: list[dict],
) -> str:
    """生成真实历年分数线查询步骤摘要。"""
    if not score_references:
        return _score_unavailable_notice(payload)

    line_count = sum(
        1 for item in score_references if item.get("is_min_score_reference") is not False
    )
    sample_count = len(score_references) - line_count
    return f"找到 {line_count} 条最低进面分参考、{sample_count} 条候选人成绩样本。"


def _build_job_trace_summary(matched_jobs: list[dict]) -> str:
    """生成岗位过滤和评分步骤摘要。"""
    if not matched_jobs:
        return "完成硬性条件过滤，当前没有可推荐岗位。"

    top_score = matched_jobs[0].get("match_score", 0)
    return (
        f"完成硬性条件过滤、岗位适配评分和保守排序，返回 {len(matched_jobs)} 个可报备选岗位，"
        f"最高基础匹配度 {top_score}。"
    )


def _add_trace(
    trace: list[dict[str, Any]],
    step: int,
    name: str,
    tool: str,
    status: str,
    input_data: dict[str, Any],
    output_summary: str,
) -> None:
    """向 trace 中追加一步执行记录。"""
    trace.append(
        {
            "step": step,
            "name": name,
            "tool": tool,
            "status": status,
            "input": input_data,
            "output_summary": output_summary,
        }
    )


def build_recommended_directions(
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict],
) -> list[str]:
    """根据岗位评分结果生成推荐方向。

    如果有匹配岗位，优先返回岗位名称；如果没有匹配岗位，则按专业给出保守建议。
    """
    directions: list[str] = []

    for job in matched_jobs:
        direction = (
            f"{job['department']} - {job['position']} "
            f"（基础匹配度 {job.get('match_score', 0)}，{job.get('match_level', '')}）"
        )
        if direction not in directions:
            directions.append(direction)

    if directions:
        return directions[:5]

    # 没有匹配岗位时，给出宽泛方向，提示用户后续扩大筛选。
    if _is_computer_related_major(payload.major):
        return [
            "信息技术岗",
            "数据管理岗",
            "数字政务或信息化岗位",
        ]

    return [
        f"{payload.region}{payload.target}综合管理方向",
        "专业不限岗位",
        "基层综合服务岗位",
    ]


def build_quick_conclusion(
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict],
    score_references: list[dict],
) -> str:
    """生成页面首屏展示的简短结论。"""
    requested_position_code = _extract_requested_position_code(payload.question)
    if _should_use_single_job_query(payload, requested_position_code):
        if matched_jobs:
            return (
                f"你查的是具体职位代码 {requested_position_code}，这里不按普通推荐逻辑排序，"
                "而是直接回查这条岗位。"
            )
        return (
            f"当前已导入数据中没有找到职位代码 {requested_position_code}，"
            "请确认地区、考试类型或是否已导入对应地区数据。"
        )

    if not matched_jobs:
        preference = extract_location_preference(
            question=payload.question,
            city=payload.city,
            region=payload.region,
        )
        if preference.get("city") and _is_explicit_nearby_request(payload.question):
            return (
                f"当前没有找到{preference['city']}附近的精确匹配岗位，"
                f"可以放宽到{preference.get('province') or payload.region or '所在省份'}区内，"
                "或补充学历、专业、身份。"
            )
        return (
            f"按你目前的{payload.region}、{payload.education}、{payload.major}和"
            f"{payload.identity}条件，暂时没有岗位通过全部硬性筛选。"
            "建议先核对专业目录和身份口径，再考虑扩大城市或岗位方向。"
        )

    preference = extract_location_preference(
        question=payload.question,
        city=payload.city,
        region=payload.region,
    )
    location_text = _build_location_conclusion(preference, matched_jobs)

    direction_text = (
        "信息化、数据管理、大数据和网络安全这类岗位"
        if _is_computer_related_major(payload.major)
        else f"和{payload.major}方向更贴近的岗位"
    )
    data_text = (
        "历史分数仅按结构化匹配状态作为风险参考。"
        if score_references
        else "暂无可用的精确分数数据，不能据此判断分数压力。"
    )
    lead_job = matched_jobs[0]
    lead_position = str(
        lead_job.get("position_name")
        or lead_job.get("position")
        or lead_job.get("department")
        or "这个岗位"
    ).strip()
    count_text = (
        f"这个“{lead_position}”可以先作为备选来看。"
        if len(matched_jobs) == 1
        else f"这 {len(matched_jobs)} 个岗位可以先进入比较，先看“{lead_position}”。"
    )

    if location_text:
        return (
            f"{count_text}"
            f"{location_text}"
            f"按你的条件，我会优先看{direction_text}。"
            f"{data_text}"
        )

    return (
        f"{count_text}"
        f"按你的条件，我会优先看{direction_text}。"
        f"{data_text}"
    )


def _build_location_conclusion(preference: dict, matched_jobs: list[dict]) -> str:
    focus_city = preference.get("city", "")
    if not focus_city:
        return ""

    display_location = preference.get("display") or focus_city
    conflict_city = preference.get("conflict_city", "")
    conflict_text = (
        f"你问题里写的是{display_location}，已优先覆盖筛选器里的城市{conflict_city}。"
        if conflict_city
        else ""
    )

    nearby_notice = (
        f"当前未接入地理距离数据，先按{focus_city}及"
        f"{preference.get('province') or payload_region_text(preference)}区内岗位筛选。"
        if preference.get("explicit_nearby_requested")
        else ""
    )

    if preference.get("source") == "question":
        base_text = (
            f"{conflict_text}{nearby_notice}你提到{display_location}，我会优先看{focus_city}及周边岗位，"
            "再结合专业、学历和身份筛选。"
        )
    else:
        base_text = f"结合你希望离{focus_city}近，我把{focus_city}及周边岗位往前排了。"

    if preference.get("source") != "question":
        return base_text

    district = preference.get("district", "")
    province = preference.get("province") or preference.get("region", "")
    city_match_count = sum(1 for job in matched_jobs if _job_matches_city(job, focus_city))
    district_match_count = (
        sum(1 for job in matched_jobs if _job_matches_text(job, district))
        if district
        else 0
    )
    non_city_count = len(matched_jobs) - city_match_count
    shortage_target = display_location if district else focus_city

    if district:
        if district_match_count == 0 and city_match_count > 0:
            return (
                f"{base_text}当前已导入数据中未找到{district}岗位，"
                f"下面优先展示{focus_city}市内相对相关的岗位。"
            )
        if district_match_count == 0 and city_match_count == 0 and matched_jobs:
            return (
                f"{base_text}当前{district}及{focus_city}市岗位不足，"
                f"已补充{province or payload_region_text(preference)}范围内相关岗位。"
            )
        if city_match_count > district_match_count and non_city_count == 0:
            return (
                f"{base_text}当前{district}岗位不足，"
                f"已优先补充{focus_city}市内相对相关岗位。"
            )
        if non_city_count > 0:
            return (
                f"{base_text}当前{district}及{focus_city}市岗位不足，"
                f"已补充{province or payload_region_text(preference)}范围内相关岗位。"
            )
        if district_match_count < 5:
            return f"{base_text}当前{shortage_target}可展示岗位不多。"

    if city_match_count < 5:
        if non_city_count > 0:
            return (
                f"{base_text}当前{focus_city}相关岗位不足，"
                f"已补充{province or payload_region_text(preference)}范围内相关岗位。"
            )
        return f"{base_text}当前{focus_city}相关可展示岗位不多。"

    return base_text


def _job_matches_city(job: dict, city: str) -> bool:
    return _job_matches_text(job, city)


def _job_matches_text(job: dict, text: str) -> bool:
    if not text:
        return False
    value = "".join(
        str(job.get(field, ""))
        for field in ["region", "city", "district", "work_location", "department", "unit", "position", "notes"]
    )
    return text in value


def payload_region_text(preference: dict) -> str:
    return preference.get("province") or preference.get("region") or "同省"


def _is_computer_related_major(major: str) -> bool:
    """判断专业是否偏计算机方向。"""
    computer_keywords = ["软件", "计算机", "网络", "信息安全", "数据", "人工智能"]
    return any(keyword in major for keyword in computer_keywords)


def build_rule_summary(
    payload: AgentAnalyzeRequest,
    intent: str,
    matched_jobs: list[dict],
    score_references: list[dict],
    policy_result: dict,
) -> str:
    """生成规则版总结，作为大模型不可用时的兜底结果。"""
    score_text = (
        f"找到 {len(score_references)} 条历年分数线/进面参考。"
        if score_references
        else _score_unavailable_notice(payload)
    )
    policy_text = (
        "当前未检索到匹配的政策依据，正式报名仍需以"
        f"{payload.region}{payload.target}公告、职位表和专业分类目录为准"
    )
    if policy_result.get("sources"):
        policy_text = "已获取到政策来源，可结合来源进一步核对"
    elif policy_result.get("error"):
        policy_text = "暂未获取到政策来源，原因是政策文件服务不可用或请求失败"

    condition_text = "、".join(
        item
        for item in [
            payload.region,
            payload.target,
            _format_exam_type(payload),
            payload.education,
            payload.major,
            payload.identity,
        ]
        if item
    )

    return (
        f"根据你提供的条件：{condition_text}，"
        f"当前问题被识别为 {intent}。"
        f"本次通过硬性条件过滤并按基础匹配度排序后返回 {len(matched_jobs)} 个可报备选岗位，"
        f"{score_text}"
        f"{policy_text}。基础匹配度只用于初筛排序，不代表考试分数线，也不代表稳妥程度。"
        "正式报名前仍需核对公告、职位表和资格审核要求。"
    )


def build_rule_analysis_report(
    payload: AgentAnalyzeRequest,
    intent: str,
    recommended_directions: list[str],
    matched_jobs: list[dict],
    score_references: list[dict],
    risks: list[str],
    policy_result: dict,
) -> str:
    """生成简洁、自然的规则版兜底分析报告。"""
    requested_position_code = _extract_requested_position_code(payload.question)

    if _should_use_single_job_query(payload, requested_position_code):
        conclusion = build_quick_conclusion(
            payload=payload,
            matched_jobs=matched_jobs,
            score_references=score_references,
        )
        competition_text = (
            _format_score_report(payload, score_references)
            if score_references
            else "暂无该岗位精确进面分，无法据此判断分数压力。"
        )
        return "\n\n".join(
            [
                "## 直接结论\n" + conclusion,
                "## 查询结果\n" + _format_recommended_jobs(matched_jobs[:1]),
                "## 数据依据\n" + competition_text,
                "## 下一步\n" + _format_verify_checklist(matched_jobs[:1]),
            ]
        )

    real_jobs = [job for job in matched_jobs if not job.get("data_error")]
    return _build_minimal_recommendation_fallback(payload, real_jobs)


def _build_minimal_recommendation_fallback(
    payload: AgentAnalyzeRequest,
    jobs: list[dict],
) -> str:
    """Return a concrete page-shaped report when the LLM is unavailable."""
    if not jobs:
        return (
            "直接结论：\n现在没有值得硬塞进备选的岗位。与其为了凑数量放宽硬门槛，不如先把条件核准。\n\n"
            "一、先看能不能报：资格关\n先把学历、专业和身份对清楚。没有具体岗位时，任何一项都不能靠猜。\n\n"
            "二、限制条件怎么看\n现在还看不到哪条限制真正卡人。等有具体岗位，再判断限制是在帮你缩小竞争人群，还是直接把你挡在门外。\n\n"
            "三、招录人数怎么看\n没有岗位记录，名额多少也无从判断。更不能拿不存在的名额去推测容错空间。\n\n"
            "四、历史分数怎么看\n分数先别硬套。没有具体岗位和匹配记录，就不能拿同类分数冒充这个岗位的门槛。\n\n"
            "五、报名人数和竞争比怎么看\n热不热，现在没有依据。暂无可核验的报名人数和竞争比，不能判断竞争强弱。\n\n"
            "六、单位性质、薪资稳定性和成长价值\n没有具体单位、岗位名称和职位简介，就不要猜工作内容、"
            "具体收入、晋升或未来 3-5 年的能力积累。\n\n"
            "七、适合什么人 / 不适合什么人\n适合：愿意先补齐条件、再把未来工作地点和职业目标想清楚的人。\n"
            "不适合：只为了尽快上岸就忽略资格审查和长期工作内容的人。\n\n"
            "八、我的建议\n定性：排除。先检查学历、专业、身份和目标地区是否填写准确，再重新筛选。"
            "最终以官方公告、职位表和资格审查为准。"
        )

    job = jobs[0]
    count = len(jobs)
    position_name = str(job.get("position_name") or job.get("position") or "该岗位")
    department = str(job.get("department") or job.get("unit") or "该单位")
    region = _job_analysis_location(job, payload)
    education = str(job.get("education_requirement") or job.get("education_required") or "未注明")
    major = str(job.get("major_requirement") or job.get("major_required") or "未注明")
    identity = str(job.get("identity_requirement") or job.get("identity_required") or "不限")
    recruit_count = _safe_int(job.get("recruit_count") or job.get("headcount"))
    min_score = job.get("min_score")
    applicant_count = (
        job.get("applicant_count")
        if job.get("applicant_count") is not None
        else job.get("applicants_count")
    )
    competition_ratio = job.get("competition_ratio")
    profile_gaps = [
        label
        for value, label in [
            (payload.education, "学历"),
            (payload.major, "专业"),
            (payload.identity, "身份"),
        ]
        if str(value or "").strip() in {"", "不限", "未设置", "未填写", "请选择"}
    ]
    identity_match = _profile_matches_identity_requirement(payload.identity, identity)
    identity_restricted = not _is_unrestricted_requirement(identity)
    major_unrestricted = _is_unrestricted_requirement(major)
    description = str(job.get("job_description") or "").strip()
    description_text = _summarize_long_field(description, max_length=80) if description else ""
    notes = str(job.get("remark") or job.get("notes") or "").strip()
    additional_restrictions = [
        str(value).strip()
        for value in [
            job.get("degree") or job.get("degree_requirement"),
            job.get("political_requirement"),
            job.get("age_requirement"),
            job.get("service_period_requirement"),
        ]
        if str(value or "").strip() and not _is_unrestricted_requirement(value)
    ]
    if "中共党员" in notes and "中共党员" not in additional_restrictions:
        additional_restrictions.append("中共党员")

    if identity_match is False:
        conclusion = (
            f"这个“{position_name}”先排除。它在{region}，招录单位是{department}；"
            f"真正卡你的不是分数，而是“{identity}”这个身份门槛。"
        )
    elif count == 1:
        conclusion = (
            f"这个“{position_name}”可以先放进备选，但别急着当主报。"
            f"它在{region}，招录单位是{department}，先把资格和竞争数据核清再决定。"
        )
    else:
        conclusion = (
            f"这几个岗位里，可以先拿“{position_name}”做重点备选。"
            f"它在{region}，招录单位是{department}，但还不能只凭筛选顺序定主报。"
        )

    if identity_restricted:
        if identity_match is False:
            qualification = (
                f"这个岗第一关就过不了。你填写的身份是“{payload.identity}”，"
                f"岗位只面向“{identity}”；即使学历是“{education}”、专业是“{major}”，"
                "身份不符合也应直接排除。最终仍以身份材料和资格审查为准。"
            )
        else:
            profile_boundary = (
                "你填写的身份方向与岗位限制有交集，但仍要拿材料核验。"
                if identity_match is True
                else f"你还没有把身份说清楚；如果你不属于“{identity}”，这个岗直接排除。"
            )
            qualification = (
                f"这个岗别先看分数，先看身份。学历“{education}”、专业“{major}”"
                f"{'都不是最卡人的' if major_unrestricted else '也要核对'}，"
                f"真正要命的是“{identity}”这个身份门槛。{profile_boundary}"
            )
    else:
        qualification = (
            f"这个岗资格上先看学历和专业。学历要求“{education}”，专业要求“{major}”，"
            f"身份是“{identity}”；任何一项和证书、专业目录对不上，都不能报。"
        )

    restriction_focus = "、".join(additional_restrictions[:3])
    restrictions = (
        (
            f"别被“{major}”这几个字带偏，真正有筛选力的是“{identity}”"
            f"{f'以及“{restriction_focus}”' if restriction_focus else ''}。"
            "这些条件如果刚好是你的优势，才有继续比较的价值；少一项材料都可能过不了资格审查。"
        )
        if identity_restricted
        else (
            f"这个岗没有明显身份门槛，重点落在“{major}”"
            f"{f'和“{restriction_focus}”' if restriction_focus else ''}。"
            "限制少不等于竞争小，只表示能进入比较的人可能更宽。"
        )
    )
    recruit = (
        (
            f"只招 {recruit_count} 人是这个岗的明显风险，容错空间很小。"
            "一次发挥波动就可能拉开结果，但仍不能在没有报名人数和竞争比时判断竞争强弱。"
        )
        if recruit_count == 1
        else (
            f"招 {recruit_count} 人是这个岗的一个优点，至少比只招 1 人的岗位容错空间更大。"
            "但别因为名额多就觉得稳，报名人数和竞争比没出来前，热不热还不知道。"
        )
        if recruit_count > 1
        else (
            "名额这块暂时不能下判断，因为招录人数没有明确记录。"
            "没有真实名额，就不能推测容错空间或竞争强弱。"
        )
    )
    score = _build_minimal_score_fallback(job)
    competition = (
        (
            f"这个岗的热度终于有一点依据：报名人数为 {applicant_count}，竞争比为 {competition_ratio}。"
            "但还要确认统计时间和口径，阶段数据不能当最终结果。"
        )
        if applicant_count is not None and competition_ratio
        else (
            "热不热，现在还不能下结论。"
            f"{'暂无报名人数数据' if applicant_count is None else f'报名人数为 {applicant_count}'}；"
            f"{'暂无竞争比数据' if not competition_ratio else f'竞争比为 {competition_ratio}'}。"
            "现阶段不能判断报名热度或竞争强弱。"
        )
    )
    development = _build_development_value_fallback(
        payload=payload,
        job=job,
        department=department,
        position_name=position_name,
        region=region,
        description_text=description_text,
    )
    suitability_identity = (
        f"身份明确符合“{identity}”"
        if identity_restricted
        else f"能按要求核对“{identity}”身份条件"
    )
    suitability_direction = (
        f"能接受“{description_text}”这类工作"
        if description_text
        else f"愿意进一步了解“{position_name}”实际职责"
    )
    suitability = (
        f"适合：{suitability_identity}、想在{region}工作、{suitability_direction}，"
        "并愿意把未来 3-5 年的工作内容、家庭安排和地点稳定性一起考虑的人。\n"
        f"不适合：身份不符合、只想靠“{major}”捡漏，"
        f"只追求轻松办公室岗，或者没弄清“{position_name}”的长期工作方向就想直接报的人。"
    )
    surface_signals = [f"专业“{major}”"]
    if recruit_count > 0:
        surface_signals.append(f"招 {recruit_count} 人")
    if min_score is not None:
        surface_signals.append("历史分数")
    surface_signal_text = "、".join(surface_signals)
    gap_text = f"先补充{'、'.join(profile_gaps)}；" if profile_gaps else ""
    if identity_match is False:
        advice = (
            "定性：排除。不要再用分数和名额给这个岗位找补，先把精力放到身份条件真正符合的岗位上。"
            "只为了上岸也不能绕过身份硬门槛，更没有必要继续推演这个岗位的长期价值。"
            "最终以官方公告、职位表、专业目录和资格审查为准。"
        )
    else:
        advice = (
            f"定性：备选。{gap_text}先核对“{identity}”身份材料、专业目录和岗位备注。"
            "等报名人数或竞争比有可靠记录后，再决定它是主报、备选还是冲一冲。"
            f"如果只是为了上岸就盯着{surface_signal_text}，这个判断还不够；"
            f"岗位不是考上就结束，还要确认自己能否接受未来几年在{region}"
            f"{f'围绕“{description_text}”工作' if description_text else f'从事“{position_name}”相关工作'}。"
            "最终以官方公告、职位表、专业目录和资格审查为准。"
        )
    return "\n\n".join(
        [
            "直接结论：\n" + conclusion,
            "一、先看能不能报：资格关\n" + qualification,
            "二、限制条件怎么看\n" + restrictions,
            "三、招录人数怎么看\n" + recruit,
            "四、历史分数怎么看\n" + score,
            "五、报名人数和竞争比怎么看\n" + competition,
            "六、单位性质、薪资稳定性和成长价值\n" + development,
            "七、适合什么人 / 不适合什么人\n" + suitability,
            "八、我的建议\n" + advice,
        ]
    )


def _build_minimal_score_fallback(job: dict) -> str:
    min_score = job.get("min_score")
    match_type = str(job.get("score_match_type") or "no_match")
    score_year = job.get("score_source_year") or job.get("year")
    year_text = f"{score_year} 年" if score_year else "历史"
    if min_score is None or match_type == "no_match":
        return "分数这块先别硬猜。暂无该岗位精确进面分记录，不能据此判断分数压力。"
    if match_type == "exact_position_code":
        return (
            f"{min_score} 可以看，但别迷信。它是这个职位代码在 {year_text}的最低进面分，"
            "只能说明往年门槛，不能直接推出今年还是这个难度。"
        )
    return (
        f"{min_score} 只能拿来找感觉，不能当这个岗位的门槛。"
        f"它是{year_text}同类岗位历史分数参考，不是该岗位精确进面分，更不能用来预测今年分数。"
    )


def _build_development_value_fallback(
    payload: AgentAnalyzeRequest,
    job: dict,
    department: str,
    position_name: str,
    region: str,
    description_text: str,
) -> str:
    if description_text:
        direction_text = (
            f"这个岗不能只看“{department}”的单位名称。职位是“{position_name}”，"
            f"职位简介写明“{description_text}”，所以未来工作价值应先围绕这条职责判断。"
        )
    else:
        direction_text = (
            f"这个岗目前只能确认是{department}的“{position_name}”，工作地点在{region}。"
            "缺少具体职位简介时，不能因为单位名称就推测日常职责。"
        )

    stability_subject = "公务员身份" if payload.target == "公务员" else "相应招录身份"
    salary_text = (
        f"薪资不能凭岗位名称判断。实际收入还要看{region}的地区财政、单位层级、编制类型和当地政策；"
        f"当前数据没有具体工资。稳定性更多来自{stability_subject}和制度安排，"
        "但稳定不等于轻松，也不等于收入一定高。"
    )

    ability_text = _development_ability_text(job, description_text)
    growth_text = (
        f"成长方面，普通人前 3-5 年更可能先积累{ability_text}。"
        "这些能力是否有利于后续发展，要看真实岗位分工和个人表现；"
        "晋升还取决于单位层级、岗位空缺、个人能力和组织安排，不能只看单位名称下结论。"
    )
    return direction_text + salary_text + growth_text


def _development_ability_text(job: dict, description_text: str) -> str:
    fact_text = " ".join(
        str(value or "")
        for value in [
            job.get("position_name"),
            job.get("position"),
            job.get("unit"),
            description_text,
        ]
    )
    if any(keyword in fact_text for keyword in ["人民武装", "国防动员", "武装"]):
        return "基层事务处理、武装相关事务对接、材料报送和上下级沟通经验"
    if any(keyword in fact_text for keyword in ["乡镇", "街道", "基层", "乡村振兴"]):
        return "基层事务处理、政策落实、群众沟通和上下级协调经验"
    return (
        f"与“{description_text}”直接相关的业务经验，以及实际分工中的沟通、执行和协作能力"
        if description_text
        else "与岗位实际分工相关的业务经验"
    )


def _job_analysis_location(job: dict, payload: AgentAnalyzeRequest) -> str:
    locations = []
    for value in [job.get("city"), job.get("district")]:
        text = str(value or "").strip()
        if text and text not in locations:
            locations.append(text)
    if not locations:
        fallback = str(
            job.get("work_location")
            or job.get("region")
            or payload.city
            or payload.region
            or "目标地区"
        ).strip()
        locations.append(fallback)
    return " / ".join(locations)


def _is_unrestricted_requirement(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or text in {"不限", "不限专业", "无要求", "无", "否"}


def _profile_matches_identity_requirement(
    user_identity: Any,
    identity_requirement: Any,
) -> bool | None:
    user_text = re.sub(r"[\s、，,；;/或]+", "", str(user_identity or ""))
    requirement_text = re.sub(r"[\s、，,；;/或]+", "", str(identity_requirement or ""))
    if not user_text or user_text in {"不限", "未设置", "未填写", "请选择"}:
        return None
    if _is_unrestricted_requirement(identity_requirement):
        return True
    if user_text in requirement_text or requirement_text in user_text:
        return True
    identity_markers = ["应届", "退役", "人武学院", "服务基层", "党员", "村干部"]
    if any(marker in user_text and marker in requirement_text for marker in identity_markers):
        return True
    return False


def _format_recommendation_reasons(jobs: list[dict]) -> str:
    if not jobs:
        return "* 当前没有岗位通过全部硬性条件筛选。"

    reasons: list[str] = []
    for job in jobs:
        reason = str(
            job.get("recommendation_reason")
            or job.get("short_reason")
            or ""
        ).strip()
        if reason and reason not in reasons:
            reasons.append(reason)

    lines = [
        (
            f"* 本次 {len(jobs)} 个岗位通过当前地区、学历、专业和身份条件初筛，"
            "可以先放进备选，但仍须核对官方职位表。"
        )
    ]
    lines.extend(f"* {reason}" for reason in reasons[:2])
    if len(lines) == 1:
        lines.append("* 现有卡片只支持宽口径初筛，不能据此确认完全符合资格条件。")
    return "\n".join(lines)


def _format_recommendation_risks(jobs: list[dict]) -> str:
    if not jobs:
        return "* 当前没有结构化岗位结果，无法判断具体岗位风险。"

    risks: list[str] = []
    for job in jobs:
        risk = str(job.get("risk_summary") or "").strip()
        if risk and risk not in risks:
            risks.append(risk)

    exact_scores = sum(
        1
        for job in jobs
        if job.get("min_score") is not None
        and job.get("score_match_type") == "exact_position_code"
    )
    reference_scores = sum(
        1
        for job in jobs
        if job.get("min_score") is not None
        and job.get("score_match_type") != "exact_position_code"
    )
    missing_scores = len(jobs) - exact_scores - reference_scores
    score_parts = []
    if exact_scores:
        if len(jobs) == 1:
            min_score = jobs[0].get("min_score")
            score_parts.append(
                f"该岗位有职位代码精确匹配的历史最低进面分 {min_score}，"
                "可以作为往年门槛参考，但不代表今年难度"
            )
        else:
            score_parts.append(f"{exact_scores} 个岗位有职位代码精确匹配的历史进面分")
    if reference_scores:
        score_parts.append(f"{reference_scores} 个岗位只有历史参考分，不是该岗位精确进面分")
    if missing_scores:
        score_parts.append(f"{missing_scores} 个岗位暂无精确进面分")

    lines = [
        f"* {'；'.join(risks[:2]) or '当前数据不足以判断竞争压力。'}",
        f"* 分数参考：{'；'.join(score_parts) or '暂无精确进面分。'}",
        f"* 报名前核对：{_build_job_verify_summary(jobs[0])}",
    ]
    return "\n".join(lines)


def _build_job_verify_summary(job: dict) -> str:
    checks = ["官方公告和职位表", "学历学位要求", "官方专业目录"]
    identity = str(job.get("identity_requirement") or job.get("identity_required") or "")
    if identity and identity != "不限":
        checks.append("身份认定材料")
    notes = str(job.get("notes") or "")
    if any(keyword in notes for keyword in ["公安", "人民警察", "司法", "体测", "政审"]):
        checks.append("体检、体测、政审等额外要求")
    return "、".join(checks) + "，最终以资格审查为准。"


def _build_recommendation_data_gap_text(
    payload: AgentAnalyzeRequest,
    jobs: list[dict],
) -> str:
    if not jobs:
        return "当前没有结构化岗位结果，因此没有可核对的竞争数据。"

    applicant_missing = sum(
        1
        for job in jobs
        if job.get("applicant_count") is None and job.get("applicants_count") is None
    )
    competition_missing = sum(1 for job in jobs if not job.get("competition_ratio"))
    exact_score_count = sum(
        1
        for job in jobs
        if job.get("min_score") is not None
        and job.get("score_match_type") == "exact_position_code"
    )
    reference_score_count = sum(
        1
        for job in jobs
        if job.get("min_score") is not None
        and job.get("score_match_type") in {
            "similar_reference",
            "partial_position_code",
            "fuzzy_high_confidence",
        }
    )
    no_score_count = len(jobs) - exact_score_count - reference_score_count
    lines = [
        (
            f"- 报名人数：{applicant_missing} 个岗位暂无报名人数数据，不能据此判断竞争压力。"
            if applicant_missing
            else "- 报名人数：结构化数据中已有记录。"
        ),
        (
            f"- 竞争比：{competition_missing} 个岗位暂无竞争比数据，不能判断竞争大或小。"
            if competition_missing
            else "- 竞争比：结构化数据中已有记录。"
        ),
    ]
    if exact_score_count:
        lines.append(
            f"- 分数匹配：{exact_score_count} 个岗位为职位代码精确匹配的历史分数，"
            "可作往年门槛参考，但不代表今年难度。"
        )
    if reference_score_count:
        lines.append(
            f"- 分数匹配：{reference_score_count} 个岗位只有同类或历史参考，"
            "不是该岗位精确分数。"
        )
    if no_score_count:
        lines.append(f"- 分数匹配：{no_score_count} 个岗位暂无该岗位历史分数。")

    profile_missing = [
        label
        for value, label in [
            (payload.education, "学历"),
            (payload.major, "专业"),
            (payload.identity, "身份"),
        ]
        if str(value or "").strip() in {"", "不限", "未设置", "未填写", "请选择"}
    ]
    if profile_missing:
        lines.append(
            f"- 当前画像中的{'、'.join(profile_missing)}仍是空值或“不限”，"
            "本次属于宽口径筛选，不代表一定符合所有岗位条件。"
        )
    return "\n".join(lines) if lines else "本次卡片所需字段均有结构化记录，但历史数据仍只能用于风险参考。"


def _build_recommendation_next_step(
    payload: AgentAnalyzeRequest,
    jobs: list[dict],
) -> str:
    if not jobs:
        return "补充或放宽城市、学历、专业和身份条件后重新筛选，并核对官方职位表。"
    if any(
        str(value or "").strip() in {"", "不限", "未设置", "未填写", "请选择"}
        for value in [payload.education, payload.major, payload.identity]
    ):
        return "先补充学历、专业和身份画像，再把资格条件明确的岗位加入备选并核对公告。"
    if len(jobs) == 1:
        return (
            "可先加入备选，后续再补充条件相近岗位，对比招录人数、限制条件和数据缺口。"
            "最终以官方公告、职位表和资格审查为准。"
        )
    return "先把最关注的岗位加入备选，再对比招录人数、限制条件和数据缺口，并逐条核对官方公告。"


def _format_report_list(items: list[str]) -> str:
    """把字符串列表整理为报告段落。"""
    if not items:
        return "- 暂无。"

    return "\n".join(f"- {item}" for item in items)


def _format_score_report(
    payload: AgentAnalyzeRequest,
    score_references: list[dict],
) -> str:
    """把分数线结果整理为报告段落。"""
    if not score_references:
        return f"- {_score_unavailable_notice(payload)}"

    lines = []
    for score in score_references[:5]:
        if score.get("is_min_score_reference") is False:
            score_parts = []
            if score.get("written_score") is not None:
                score_parts.append(f"笔试成绩 {score.get('written_score')}")
            if score.get("interview_score") is not None:
                score_parts.append(f"面试成绩 {score.get('interview_score')}")
            if score.get("total_score") is not None:
                score_parts.append(f"总成绩 {score.get('total_score')}")
            if score.get("rank") is not None:
                score_parts.append(f"排名 {score.get('rank')}")
            lines.append(
                "- "
                f"{score.get('year')} 年，"
                f"{score.get('region')}{score.get('position_name') or score.get('position_type')}，"
                f"{'，'.join(score_parts) if score_parts else '候选人成绩字段暂无'}。"
                "这是候选人成绩样本，不是岗位最低进面线。"
            )
            continue
        min_score = score.get("min_interview_score") or score.get("min_score")
        avg_score = score.get("avg_score")
        max_score = score.get("max_score")
        score_parts = [
            f"最低进面分 {min_score}"
            if min_score is not None
            else "最低进面分 暂无"
        ]
        if avg_score is not None:
            score_parts.append(f"平均分 {avg_score}")
        if max_score is not None:
            score_parts.append(f"最高分 {max_score}")
        source_text = "，".join(
            part
            for part in [
                score.get("source_type"),
                score.get("data_status"),
            ]
            if part
        )
        lines.append(
            "- "
            f"{score.get('year')} 年，"
            f"{score.get('region')}{score.get('target')}{score.get('exam_type', '')}"
            f"{score.get('position_name') or score.get('position_type')}，"
            f"{'，'.join(score_parts)}。"
            f"{source_text + '。' if source_text else ''}"
            f"{score.get('notes', '')}"
        )
    return "\n".join(lines)


def _format_recommended_jobs(jobs: list[dict]) -> str:
    """把评分后的岗位推荐整理为报告段落。"""
    if not jobs:
        return "- 暂无。"

    lines = []
    for job in jobs:
        recruit_text = _format_recruit_count(job)
        lines.append(
            "- "
            f"**{job.get('department')} - {job.get('position')}**："
            f"{job.get('short_reason', '')}"
            f"{recruit_text}，"
            f"基础匹配度 {job.get('match_score', 0)}。"
            f"需要注意：{job.get('risk_summary', '')}"
        )
    return "\n".join(lines)


def _format_recruit_count(job: dict) -> str:
    recruit_count = job.get("recruit_count") or job.get("headcount")
    try:
        count = int(recruit_count)
    except (TypeError, ValueError):
        count = 0
    return f"招录 {count} 人" if count > 0 else "招录人数暂无"


def _format_verify_checklist(matched_jobs: list[dict]) -> str:
    """汇总 Top 推荐岗位的报考核验事项。"""
    items: list[str] = []
    for job in matched_jobs[:5]:
        for note in job.get("verify_notes", []):
            if note not in items:
                items.append(note)

    if not items:
        items = [
            "核对最新官方公告和职位表。",
            "核对专业目录、学历学位、身份限制及岗位备注。",
        ]

    return _format_report_list(items[:8])


def _format_policy_report(
    payload: AgentAnalyzeRequest,
    policy_result: dict,
) -> str:
    """把政策来源结果整理为报告段落。"""
    sources = policy_result.get("sources", [])
    if not sources:
        return (
            "当前未检索到匹配的政策依据，正式报名仍需以"
            f"{payload.region}{payload.target}公告、职位表和专业分类目录为准。"
        )

    lines = [f"本次检索到 {len(sources)} 条政策来源，仍需以官方原文为准。"]
    for source in sources[:5]:
        title = source.get("title") or "政策来源"
        url = source.get("url") or "无链接"
        snippet = source.get("snippet") or "无摘要"
        lines.append(f"- {title}；链接：{url}；摘要：{snippet}")

    return "\n".join(lines)


def _score_unavailable_notice(payload: AgentAnalyzeRequest) -> str:
    return "暂无该省进面分数据，岗位推荐仍按已导入职位表进行。"


def _format_exam_type(payload: AgentAnalyzeRequest) -> str:
    if payload.target == "公务员" and payload.exam_type:
        return payload.exam_type
    return ""


def _apply_report_data_semantics(
    report: str,
    payload: AgentAnalyzeRequest,
    score_references: list[dict],
    sources: list[dict],
) -> str:
    """确保 LLM 报告也遵守分数线和政策来源的数据语义。"""
    result = report.strip()

    if not score_references:
        result = result.replace(
            "找到 0 条分数线参考。",
            "当前没有能对应到具体岗位的真实分数线数据。",
        )
        result = result.replace(
            "暂无分数线参考。",
            "当前没有能对应到具体岗位的真实分数线数据。",
        )

    if not sources:
        result = result.replace(
            "当前没有检索到政策来源，建议以官方公告、岗位表和专业目录为准。",
            "正式报名仍需以最新公告、职位表和专业目录为准。",
        )

    return result


def _enforce_recommendation_report_accuracy(
    report: str,
    payload: AgentAnalyzeRequest,
    matched_jobs: list[dict],
    recommendation_count: int,
    fallback_report: str,
) -> str:
    """Fall back to deterministic copy when the LLM contradicts structured facts."""
    result = str(report or "").strip()
    if not result:
        return fallback_report

    required_sections = [
        "直接结论",
        "一、先看能不能报",
        "二、限制条件怎么看",
        "三、招录人数怎么看",
        "四、历史分数怎么看",
        "五、报名人数和竞争比怎么看",
        "六、单位性质、薪资稳定性和成长价值",
        "七、适合什么人 / 不适合什么人",
        "八、我的建议",
    ]
    if any(section not in result for section in required_sections):
        return fallback_report
    if len(result) < 800 or len(result) > 1700:
        return fallback_report
    if any(
        old_section in result
        for old_section in ["为什么值得看：", "最大风险：", "数据缺口：", "下一步："]
    ):
        return fallback_report

    forbidden_claims = [
        "稳上",
        "保过",
        "必进面",
        "一定适合",
        "高度稳妥",
        "录取概率高",
        "专业条件可以满足",
        "你的专业符合",
        "学历专业身份都满足",
        "筛掉绝大多数人",
        "竞争一定小",
        "分数很低",
        "分数很高",
        "一定轻松",
        "一定很累",
        "工资高",
        "待遇好",
        "待遇低",
        "晋升快",
        "前途好",
        "神仙单位",
        "劝退级",
        "稳定舒服",
        "一定能调动",
        "一定能遴选",
        "一定好",
        "一定差",
    ]
    if any(claim in result for claim in forbidden_claims):
        return fallback_report

    system_flavor_phrases = [
        "本次推荐",
        "排序第一",
        "宽口径初筛",
        "卡片说明",
        "本轮",
        "当前画像仍有缺项",
        "过滤后的结构化事实",
        "结构化样本",
        "兜底报告",
        "校验链路",
        "Prompt",
        "Skill",
        "runtime",
        "内部规则",
    ]
    if any(phrase in result for phrase in system_flavor_phrases):
        return fallback_report

    if re.search(r"(?m)^\s*\|.*\|\s*$", result) or re.search(
        r"(?m)^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$",
        result,
    ):
        return fallback_report

    mentioned_codes = set(re.findall(r"(?<!\d)(\d{6,20})(?!\d)", result))
    if mentioned_codes:
        return fallback_report

    real_jobs = [job for job in matched_jobs if not job.get("data_error")]
    if recommendation_count != len(real_jobs):
        return fallback_report

    first_paragraph = result.split("一、先看能不能报", maxsplit=1)[0]
    job_identifiers = {
        str(value).strip()
        for job in real_jobs[:1]
        for value in [
            job.get("position_name"),
            job.get("position"),
            job.get("department"),
            job.get("unit"),
        ]
        if str(value or "").strip()
    }
    if job_identifiers and not any(value in first_paragraph for value in job_identifiers):
        return fallback_report
    if re.search(
        r"一、先看能不能报：?资格关\s*(?:\r?\n|\s)*(?:该岗位|岗位)?学历要求(?:是|为)",
        result,
    ):
        return fallback_report
    if re.search(
        r"三、招录人数怎么看\s*(?:\r?\n|\s)*该岗位招",
        result,
    ):
        return fallback_report
    if re.search(
        r"四、历史分数怎么看\s*(?:\r?\n|\s)*(?:\d{4}\s*年|历史)(?:最低)?进面分",
        result,
    ):
        return fallback_report
    if not re.search(r"(?:3\s*[-—至到]\s*5|三到五|三至五)\s*年", result):
        return fallback_report
    if "晋升" not in result:
        return fallback_report
    if not any(phrase in result for phrase in ["只为上岸", "只是为了上岸", "只为了上岸"]):
        return fallback_report

    visible_regions = {
        str(value).strip()
        for job in real_jobs
        for value in [
            job.get("city"),
            job.get("district"),
            job.get("province"),
            job.get("region"),
        ]
        if str(value or "").strip()
    }
    if visible_regions and not any(value in result for value in visible_regions):
        return fallback_report

    if len(real_jobs) == 1:
        identity_requirement = str(
            real_jobs[0].get("identity_requirement")
            or real_jobs[0].get("identity_required")
            or ""
        ).strip()
        if identity_requirement and identity_requirement not in result:
            return fallback_report

    exact_jobs = [
        job
        for job in real_jobs
        if job.get("score_match_type") == "exact_position_code"
        and job.get("min_score") is not None
    ]
    reference_jobs = [
        job
        for job in real_jobs
        if job.get("score_match_type") in {
            "similar_reference",
            "partial_position_code",
            "fuzzy_high_confidence",
        }
    ]
    if exact_jobs and not reference_jobs and re.search(r"同类岗位(?:分数)?参考|同类参考", result):
        return fallback_report
    if reference_jobs and not exact_jobs and re.search(
        r"该岗位.*精确匹配.*历史.*分|该岗位历史精确匹配",
        result,
    ):
        return fallback_report

    if real_jobs and all(
        _safe_int(job.get("recruit_count") or job.get("headcount")) != 1
        for job in real_jobs
    ):
        if re.search(
            r"(?:该岗位|这个岗|此岗位|当前岗位).{0,8}"
            r"(?:只招\s*1\s*人|是\s*1\s*人岗|属于\s*1\s*人岗|是一人岗|属于一人岗)",
            result,
        ):
            return fallback_report

    count_words = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5}
    reported_counts = [
        int(value) if value.isdigit() else count_words.get(value, 0)
        for value in re.findall(
            r"(?:本次|此次|这次|筛选出|推荐|返回|共)[^。\n]{0,12}?([1-5一二两三四五])\s*个(?:岗位|职位)",
            result,
        )
    ]
    if any(value != recommendation_count for value in reported_counts):
        return fallback_report

    known_recruit_counts = {
        _safe_int(job.get("recruit_count") or job.get("headcount"))
        for job in real_jobs
    }
    stated_recruit_counts = [
        int(value)
        for value in re.findall(r"招录(?:人数)?\D{0,4}(\d+)\s*人", result)
    ]
    if any(value not in known_recruit_counts for value in stated_recruit_counts):
        return fallback_report
    if len(real_jobs) == 1:
        expected_count = _safe_int(
            real_jobs[0].get("recruit_count") or real_jobs[0].get("headcount")
        )
        if expected_count and not re.search(
            rf"(?:招录?|招考)(?:人数)?\D{{0,4}}{expected_count}\s*人",
            result,
        ):
            return fallback_report

    if real_jobs and all(
        job.get("applicant_count") is None and job.get("applicants_count") is None
        for job in real_jobs
    ):
        if re.search(r"报名人数\s*(?:为|约|达到|只有)?\s*\d", result):
            return fallback_report

    if real_jobs and all(not job.get("competition_ratio") for job in real_jobs):
        if re.search(r"(竞争较小|竞争较大|竞争激烈|竞争不激烈|竞争压力(?:小|大|低|高))", result):
            return fallback_report

    if real_jobs and not any(
        job.get("score_match_type") == "exact_position_code"
        and job.get("min_score") is not None
        for job in real_jobs
    ):
        if re.search(r"(?:该岗位|岗位的)?(?:最低)?进面分\s*(?:为|是|约)?\s*\d", result):
            return fallback_report
    if len(real_jobs) == 1:
        min_score = real_jobs[0].get("min_score")
        score_match_type = str(real_jobs[0].get("score_match_type") or "no_match")
        if (
            min_score is not None
            and score_match_type == "exact_position_code"
            and str(min_score) not in result
        ):
            return fallback_report
        if (min_score is None or score_match_type == "no_match") and "暂无" not in result:
            return fallback_report

    profile_missing = any(
        str(value or "").strip() in {"", "不限", "未设置", "未填写", "请选择"}
        for value in [payload.education, payload.major, payload.identity]
    )
    if profile_missing and "补充" not in result and "排除" not in result:
        return fallback_report
    return result
