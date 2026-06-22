import re


def route_intent(question: str, has_current_job: bool = False) -> str:
    """根据用户问题识别意图。

    第一版只用关键词规则，方便初学者理解，也方便后续替换成更强的模型。
    """
    text = (question or "").strip()
    compact_text = "".join(text.split())

    if not compact_text:
        return "needs_clarification"

    greeting_keywords = [
        "你好",
        "您好",
        "在吗",
        "你是谁",
        "你能做什么",
        "你可以干嘛",
        "你可以做什么",
        "你有什么功能",
        "我能问你什么",
        "能问你什么",
        "怎么用",
        "如何使用",
    ]
    incomplete_questions = [
        "帮我看看",
        "我想考公",
        "想考公",
        "我要考公",
        "看看",
    ]
    if compact_text in greeting_keywords or (
        len(compact_text) <= 8 and _contains_any_keyword(compact_text, greeting_keywords)
    ):
        return "greeting"

    if compact_text in incomplete_questions:
        return "needs_clarification"

    if has_current_job and _references_current_job(compact_text):
        return "single_job_query"

    if (
        _references_current_job(compact_text)
        and not _looks_like_position_code(compact_text)
        and not _contains_any_keyword(compact_text, ["进面分", "分数", "风险", "竞争", "报名人数"])
    ):
        return "needs_clarification"

    if _looks_like_position_code(compact_text):
        return "single_job_query"

    if _is_selection_strategy_question(compact_text):
        return "selection_strategy"

    if _is_policy_question(compact_text):
        return "policy_qa"

    if re.search(
        r"(为什么不能只看最低进面分|没有竞争比还能不能报|进面分数线能代表今年难度吗|"
        r"进面分|最低进面分|最低分|分数线|竞争比|报名人数|缴费人数|竞争风险|分数风险)",
        compact_text,
    ):
        return "score_or_risk_query"

    if re.search(
        r"(推荐(?:一个|[1-5一二三四五两]个)?(?:南宁|南宁市|广西南宁|按我的画像|附近|周边)?.*岗位|"
        r"推荐.*可报岗位|按我的画像推荐|岗位推荐|找岗位|帮我筛岗位|筛岗位|"
        r"能报什么|能报哪些|可以报哪些|报哪些岗位|可报岗位|能报的岗位|附近.*岗位|岗位.*推荐)",
        compact_text,
    ):
        return "job_recommendation"

    return "general"


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    """判断文本中是否包含任意关键词。"""
    return any(keyword in text for keyword in keywords)


def _looks_like_position_code(text: str) -> bool:
    """判断文本中是否有明显职位代码。"""
    return any(char.isdigit() for char in text) and any(
        len(part) >= 6
        for part in "".join(char if char.isdigit() else " " for char in text).split()
    )


def _references_current_job(text: str) -> bool:
    """Return whether the question points to the current or previous job card."""
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


def _is_selection_strategy_question(text: str) -> bool:
    """Identify job-selection method and category-risk questions."""
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


def _is_policy_question(text: str) -> bool:
    policy_terms = [
        "应届生身份",
        "应届毕业生",
        "服务基层项目人员",
        "服务基层",
        "专业目录",
        "专业不限",
        "学历学位",
        "学位要求",
        "资格审查",
        "资格复审",
        "基层工作经历",
        "最低服务年限",
        "服务年限",
        "户籍限制",
        "资格证书",
        "政治面貌",
        "退役军人",
        "人民武装",
        "岗位备注",
        "报考条件",
        "政策",
        "公告",
    ]
    explanation_cues = [
        "怎么算",
        "是什么",
        "意思",
        "怎么看",
        "怎么认定",
        "如何认定",
        "怎么理解",
        "能不能报",
        "都能报",
        "所有人",
        "怎么界定",
        "有什么要求",
        "主要查什么",
        "限制",
    ]
    if not any(term in text for term in policy_terms):
        return False
    return (
        any(cue in text for cue in explanation_cues)
        or any(term in text for term in ["政策", "公告", "报考条件", "资格审查", "资格复审"])
    )
