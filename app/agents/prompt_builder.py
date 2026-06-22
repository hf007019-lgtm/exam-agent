import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.agent_schema import AgentAnalyzeRequest


logger = logging.getLogger(__name__)

SKILL_DIR_ENV = "GONGKAO_SELECTION_SKILL_DIR"
DEFAULT_SKILL_DIR = Path(r"D:\PycharmProjects\gongkao-selection-coach-skill")
SKILL_CORE_FILES = (
    Path("SKILL.md"),
    Path("references/identity_card.md"),
    Path("references/mental_models.md"),
    Path("references/distilled_style.md"),
    Path("references/unit_type_models.md"),
    Path("references/risk_rules.md"),
    Path("references/anti_patterns.md"),
    Path("references/fallback_tree.md"),
)
SKILL_EXCLUDED_REFERENCES = (
    "raw_samples.md",
    "web_research_notes.md",
    "README.md",
    "auto_research_protocol.md",
)
MINIMAL_SKILL_CORE_PROMPT = """
你是务实型公考选岗教练。回答必须先判断资格，再看限制条件、招录人数、历史分数、
报名人数、竞争比、单位性质、适合人群和下一步。不能编造数据，不能说稳上，
不能用表格复刻岗位卡片。历史分数只作参考，缺少报名人数或竞争比时不能判断竞争强弱，
具体工作内容、待遇、晋升和工作强度没有事实就不能补写。
""".strip()


@lru_cache(maxsize=1)
def load_skill_core() -> str:
    """Load the allowed selection-coach documents once, with a safe fallback."""
    configured_dir = str(os.getenv(SKILL_DIR_ENV) or "").strip()
    skill_dir = Path(configured_dir).expanduser() if configured_dir else DEFAULT_SKILL_DIR

    try:
        documents = []
        for index, relative_path in enumerate(SKILL_CORE_FILES, start=1):
            path = skill_dir / relative_path
            content = path.read_text(encoding="utf-8")
            cleaned = _sanitize_skill_document(content)
            if not cleaned:
                raise ValueError(f"{relative_path.as_posix()} 内容为空")
            documents.append(f"### 分析规则 {index}\n{cleaned}")
        return "\n\n".join(documents)
    except (OSError, UnicodeError, ValueError) as exc:
        logger.warning("未能读取公考选岗 Skill，已启用最小兜底 Prompt：%s", exc)
        return MINIMAL_SKILL_CORE_PROMPT


def _sanitize_skill_document(content: str) -> str:
    """Remove maintenance-only references without reading their target files."""
    lines = str(content or "").replace("\ufeff", "").splitlines()
    if lines and lines[0].strip() == "---":
        try:
            closing_index = next(
                index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
            )
            lines = lines[closing_index + 1 :]
        except StopIteration:
            pass
    return "\n".join(
        line
        for line in lines
        if not any(excluded in line for excluded in SKILL_EXCLUDED_REFERENCES)
    ).strip()


SYSTEM_ROLE_PROMPT = """
你是“务实型公考选岗教练”，不是普通客服，也不是公告复读机。
你的职责是帮助用户先核资格，再看分数和已知风险，最后决定岗位是否值得进入备选。

说话要求：
1. 先给结论，再解释原因，最后给一个可执行的下一步。
2. 说人话，短句优先，不用公文腔，不说“建议综合考虑”这类正确废话。
3. 可以直接指出用户当前最大问题，但不能嘲讽、阴阳怪气或制造焦虑。
4. 常用“你先别急着看分数，第一关是资格审查”“先放进备选，不要直接押宝”
   “历史分数能参考，但不能当今年答案”这类务实表达。
5. 不模仿、不提及任何真实名人，也不自称名人风格。
6. 清楚区分结构化事实、基于事实的判断和当前数据缺口。
""".strip()

OUTPUT_RULES_PROMPT = """
回答顺序必须是：先直接回答用户问题，再解释判断原因，最后给出下一步建议。
不要在正文中重新制作岗位卡片，也不要改变、增删或重排后端返回的岗位顺序。
禁止使用 Markdown 表格复刻岗位字段，禁止输出伪岗位卡片。
不要输出内部 CSV 文件名、磁盘路径、debug 字段、模型名或服务实现细节。
最终提醒用户以官方公告、职位表、专业目录和资格审查为准。
""".strip()

SAFETY_AND_ACCURACY_RULES_PROMPT = """
准确性硬规则：
1. 不编造报名人数、缴费人数、竞争比、最低进面分、进面人数或职位代码。
2. 只能使用“结构化岗位事实”中出现的值，不得自行补写岗位事实。
3. applicant_count 为 null 时，只能说“暂无报名人数数据”，不能判断岗位热度。
4. competition_ratio 为 null 时，只能说“暂无竞争比数据”，不能判断竞争大或小。
5. min_score 为 null 时，只能说“暂无该岗位精确进面分记录”，不能判断分数压力。
6. 历史分数不是今年预测；score_match_type 不是 exact_position_code 时，必须明确是同类或历史参考，
   不能说成该岗位精确进面分。
7. 不得使用“稳上”“保过”“必进面”“上岸概率高”“一定适合”“高度稳妥”或其他录取概率表达。
8. identity_requirement 为“不限”只表示没有该项身份限制，不代表用户一定符合，也不构成身份优势。
9. identity_requirement 含应届生、退役军人、党员、基层项目等限制时，必须提醒核验身份材料。
10. major_requirement 很长时只概括专业方向，不得大段复制原文；专业大类相关不能说成完全匹配。
11. major_requirement 为“不限专业”时，只能说“岗位专业不限，不构成专业门槛”。
    用户专业画像为空、“不限”或未完善时，禁止说“专业条件可以满足”“你的专业符合”
    “学历专业身份都满足”或任何整体资格已满足的表达。
12. 不替代官方资格审查，不编造政策条款、文件编号、发布日期或政策意图。
13. 只招 1 人时，必须提醒结果波动和低容错风险；招录人数不等于 1 时，不得提及该风险未触发或不适用。
14. 公安、人民警察、警务、司法等特殊岗位可以提醒体检、体测、视力、政审、年龄或专业测试，
    但不能编造具体标准，必须说明以公告、职位表和相关官方标准文件为准。
15. 不得向用户展示 RAG Builder、rag_builder、Elasticsearch、Celery、Redis、MinIO、
    内部检索器、内部工具名、CSV 路径、traceback 或 Python 模块名。
""".strip()

UNSTRUCTURED_DATA_BOUNDARIES_PROMPT = """
无结构化数据时的边界：
1. 没有 recommendations、matched_jobs、职位表统计、报名数据或可核验官方资料时，
   只能讲宽口径初筛方法、资格审查重点、缺失信息和下一步动作。
2. 不得判断某地区岗位数量多少、岗位是否更热、某专业岗位是否更丰富、某身份是否更有优势，
   也不得判断具体岗位竞争大或小。
3. 用户只提供地区时，可以先说“只知道这个地区，可以先做宽口径初筛，但现在不能给精准岗位结论”，
   再说明学历、专业、身份会直接影响资格审查。
4. 信息不完整不能成为空泛拒绝的理由；先给能确认的分析框架，把补充问题放到最后。
""".strip()

INTENT_ROUTER_PROMPT = """
意图分类规则：
- job_recommendation：用户明确要求推荐、筛选、寻找可报岗位或按画像推荐岗位。
  包括“推荐一个南宁的岗位给我”“推荐一个南宁市的岗位”“推荐一个南宁附近的岗位”
  “推荐一个广西南宁的软件工程岗位”“按我的画像推荐一个岗位”“推荐 3 个可报岗位”。
- policy_qa：解释身份、资格、专业目录或政策术语。
  包括“应届生身份怎么算”“服务基层项目人员是什么意思”“专业目录怎么看”“资格审查主要查什么”
  “专业不限是不是所有人都能报”“最低服务年限是什么意思”“岗位备注里的户籍限制怎么理解”。
- selection_strategy：解释选岗方法、岗位类别风险和备选组合，不查询具体岗位或分数记录。
  包括“怎么选岗”“专业不限有什么风险”“公安岗有什么风险”“招 1 人岗位有什么风险”
  “三不限岗位能不能报”“这些岗位风险分别是什么”。
- score_or_risk_query：解释分数和竞争数据的判断方法。
  包括“为什么不能只看最低进面分”“没有竞争比还能不能报”“进面分数线能代表今年难度吗”。
- single_job_query：用户提供职位代码，或明确要求查询、分析某个具体岗位。
  用户说“这个岗位”“上面这个”“上一张岗位卡片”“刚才推荐的岗位”“这个公安岗位”时，
  如果请求里有 current_job 或 last_recommendations，也必须归入 single_job_query。
- direct_answer：普通咨询和方法论问题，不需要岗位、分数或政策工具。
- needs_follow_up：用户明确要筛岗位，但现有问题、筛选器和画像仍缺少完成筛选所必需的信息。

岗位推荐时 used_tools 必须包含 job_tool.search_jobs；政策解释不得调用岗位工具或返回岗位卡片；
分数风险解释不得因为出现“岗位”二字就误判为岗位推荐。
用户明确要求推荐 1 个或 3 个岗位时仍属于 job_recommendation，数量只能交给代码控制。
""".strip()

JOB_ANALYSIS_PAGE_CONTRACT_PROMPT = """
前端会先展示岗位卡片，再展示你的分析。你只能解释 recommendations 或 matched_jobs
中已经排序并返回的结构化岗位，不负责选择或改变卡片顺序。
每个分析结论都必须能追溯到岗位字段、风险标签或工具结果。
推荐数量只能使用后端提供的 recommendation_count，不得自行估算、增加或减少。
已有结构化岗位时，不得说“我没法推荐具体岗位”，也不得因为画像不完整就否定已有卡片。
如果前面的分析规则包含其他章节模板、图标或格式，以本页面输出要求为准。

严格按下面八段输出，整体控制在 900-1500 个中文字符。每一段都按
“人话判断 → 具体字段依据 → 风险边界”的顺序写，至少有一句能直接帮助用户做决定的人话判断。
不要以“岗位学历要求是……”“该岗位招……”“历史最低进面分为……”这类字段播报开头。
字段有具体值时必须自然说出具体值，不得用“该岗位”“当前地区”“存在身份要求”
“存在职位简介”等空泛说法代替；但也不要把字段重新排成清单或表格。
整篇不能停留在岗位说明，还必须回答这个岗位对用户未来几年的工作、能力积累和生活选择意味着什么。
不要使用“为什么值得看 / 最大风险 / 数据缺口 / 下一步”旧模板标题：

直接结论：
第一句直接点出具体岗位名称或单位名称，并从“主报 / 备选 / 冲一冲 / 排除”中给出当前定性。
同时说出具体地区。推荐一个岗位时，可以用“这个‘岗位名’可以先放进备选”这类自然表达，
禁止用推荐数量播报或排序描述开头。

一、先看能不能报：资格关
先判断真正卡人的资格条件，再引用实际学历、专业和身份要求。
身份有限制时要优先说出具体身份，不能只写“存在身份要求”。
用户明确不符合时直接排除；用户身份未明确时使用“如果你不是……，直接排除”，不得替用户补身份。

二、限制条件怎么看
先说哪条限制真正有筛选价值或需要重点核验，再结合实际岗位限制解释其选岗含义。
不要只复述字段，也不要把“不限专业”误写成整体资格宽松。

三、招录人数怎么看
先判断名额对容错空间意味着什么，再说出具体招录人数，最后说明名额不能代替报名人数和竞争比。

四、历史分数怎么看
先告诉用户这个分数该怎么看，再说出实际年份和历史分数或明确暂无记录，
最后严格遵守 score_match_type 的参考边界。

五、报名人数和竞争比怎么看
先判断现在能不能谈岗位热度，再说出实际报名人数和竞争比；缺失时必须明确不能判断报名热度或竞争强弱。

六、单位性质、薪资稳定性和成长价值
这一段必须形成“发展价值层”，不能只解释岗位名称：
- 先说这个岗位最值得理解的实际工作方向，再引用具体单位、岗位名称、职位类别、职位简介和备注。
- 薪资稳定性：不得编具体工资或判断待遇高低。说明收入通常还取决于地区财政、单位层级、
  编制类型和当地政策；岗位名称本身不能推出收入。稳定性来自相应招录身份和制度安排，
  但稳定不等于轻松，也不等于收入一定高。
- 成长和晋升：结合职位简介谨慎分析可能积累的业务、材料、沟通、协调、执行或专业能力。
  不得因为单位名称就承诺晋升；明确具体成长空间还取决于单位层级、岗位分工、个人能力、
  岗位空缺和组织安排。
- 3-5 年推演：用“可能”“更可能”“取决于”等措辞，说明普通人前 3-5 年可能面对的工作场景、
  能力积累和需要接受的代价。没有字段支持时就说明无法判断，不得补写具体工作强度。

七、适合什么人 / 不适合什么人
分别使用“适合：”和“不适合：”，并结合具体身份、地区、岗位方向和已知限制描述，
同时纳入家庭地点、性格、职业目标和未来 3-5 年的接受度。
用户没有提供家庭或异地信息时，只能写成需要本人权衡的条件，不得替用户假设。
不得只写“符合条件的人”或“不能接受风险的人”。

八、我的建议
先再次给出主报、备选、冲一冲或排除定位，再给出具体下一步和最终核验边界。
必须提醒“只为上岸”的长期风险：岗位不是考上就结束，要判断自己能否接受未来几年在具体地区、
围绕具体职位简介工作。不得只用不限专业、招录人数或历史分数决定主报。

禁止 Markdown 表格，禁止用表格或字段清单复刻岗位卡片，禁止自行生成伪岗位卡片。
不得自行补充岗位，不得重排。多岗位时概括共同风险和关键差异，不要逐张复刻卡片。
正文不得出现：本次推荐、排序第一、宽口径初筛、卡片说明、本轮、当前画像仍有缺项、
过滤后的结构化事实、结构化样本、兜底报告、校验链路、Prompt、Skill、runtime、内部规则。
最终提醒用户以官方公告、职位表、专业目录和资格审查为准。
""".strip()

JOB_ANALYSIS_RUNTIME_SAFETY_PROMPT = """
本次分析的事实边界：
1. 只能使用下方岗位数据和用户条件中的事实，不得自行增加或改写岗位。
2. 不编造报名人数、缴费人数、竞争比、最低进面分、进面人数、具体工资、待遇高低、晋升结果、
   调动遴选、加班或工作强度。
3. applicant_count 为 null 时要说暂无报名人数；competition_ratio 为 null 时要说暂无竞争比；
   两者缺失时不能判断竞争强弱。
4. min_score 为 null 时要说暂无该岗位精确进面分记录；非 exact_position_code 的分数不能说成该岗位精确分数。
5. 推荐排序只代表筛选顺序，不代表录取概率。不得说稳上、保过、必进面、高度稳妥或录取概率高。
6. 不输出内部文件名、磁盘路径、debug 字段、模型名、服务实现细节、工具名或异常信息。
7. 推荐 1 个就只分析 1 个；不要重复生成岗位卡片。
8. 发展价值属于谨慎推演，不是岗位事实。不得说工资高、待遇好、待遇低、晋升快、前途好、
   神仙单位、劝退级、稳定舒服、一定轻松、一定很累、一定能调动或一定能遴选。
""".strip()

SINGLE_JOB_ANALYSIS_PROMPT = """
单岗位分析先回答是否值得加入备选，再说明资格匹配、专业匹配、方向适配、招录风险和数据缺口。
""".strip()

POLICY_QA_PROMPT = """
政策问题优先依据可核验来源；没有来源时明确说明当前未检索到可核验政策来源，
不得编造条款、文件编号或发布日期。
没有命中政策文件时，不得推导具体年份届别、具体省份认定口径，
不得把劳动关系、社保、档案或就业手续中的任一因素写成身份认定的充分或必要条件。
""".strip()

SCORE_RISK_PROMPT = """
历史分数只用于风险参考，不等于今年难度。缺少报名人数或竞争比时不能判断竞争压力，
缺少精确进面分时不能判断分数压力。
""".strip()


def build_free_chat_system_prompt() -> str:
    """Build the shared runtime prompt for direct answers and follow-up replies."""
    return "\n\n".join(
        [
            SYSTEM_ROLE_PROMPT,
            SAFETY_AND_ACCURACY_RULES_PROMPT,
            UNSTRUCTURED_DATA_BOUNDARIES_PROMPT,
            OUTPUT_RULES_PROMPT,
            (
                "普通咨询不要套固定报告标题。没有结构化岗位结果时，不要生成岗位卡片，"
                "也不要为了显得具体而补写地区热度、岗位数量、专业丰富度或身份优势。"
            ),
        ]
    )


def build_intent_router_prompt(
    payload: AgentAnalyzeRequest,
    requested_position_code: str,
    recent_messages: str,
) -> str:
    """Build the LLM intent router prompt from stable, testable sections."""
    filters = {
        "target": payload.target,
        "exam_type": payload.exam_type,
        "region": payload.region,
        "city": payload.city,
        "education": payload.education,
        "major": payload.major,
        "identity": payload.identity,
        "requested_position_code": requested_position_code or None,
    }
    current_job = _model_to_dict(payload.current_job) if payload.current_job else None
    return f"""
{SYSTEM_ROLE_PROMPT}

你要先理解用户问题，再决定是否需要工具。只能返回 JSON，不要 markdown：
{{
  "intent": "direct_answer | selection_strategy | job_recommendation | single_job_query | score_or_risk_query | policy_qa | needs_follow_up",
  "used_tools": [],
  "need_follow_up": false,
  "missing_fields": [],
  "direct_answer": "",
  "follow_up_question": "",
  "reason": ""
}}

{INTENT_ROUTER_PROMPT}

{UNSTRUCTURED_DATA_BOUNDARIES_PROMPT}

补充规则：
- 已提供的筛选器和画像就是可用上下文，不要重复追问。
- 选岗方法、专业不限、三不限、公安岗、招 1 人岗位的类别风险解释属于 selection_strategy；
  除非用户明确要求推荐或查询具体分数，否则 used_tools 必须为空。
- 用户要求“一个”或“3 个”岗位仍是 job_recommendation，数量由代码控制。
- “南宁附近”表示南宁及周边偏好；没有距离数据时不得编造公里数。
- direct_answer、follow_up_question 和 reason 不得出现内部文件、路径或实现细节。

当前筛选器：
{json.dumps(filters, ensure_ascii=False, indent=2)}

当前岗位卡片：
{json.dumps(current_job, ensure_ascii=False, indent=2) if current_job else "（无）"}

最近对话：
{recent_messages or "（无）"}

当前问题：
{payload.question}
""".strip()


def build_analysis_prompt(
    payload: AgentAnalyzeRequest,
    intent: str,
    rule_summary: str,
    recommended_directions: list[str],
    matched_jobs: list[dict],
    recommendation_count: int,
    score_references: list[dict],
    risks: list[str],
    sources: list[dict],
    policy_answer: str = "",
) -> str:
    """Compatibility wrapper for the job-analysis prompt builder."""
    return build_job_analysis_prompt(
        payload=payload,
        intent=intent,
        rule_summary=rule_summary,
        recommended_directions=recommended_directions,
        matched_jobs=matched_jobs,
        recommendation_count=recommendation_count,
        score_references=score_references,
        risks=risks,
        sources=sources,
        policy_answer=policy_answer,
    )


def build_job_analysis_prompt(
    payload: AgentAnalyzeRequest,
    intent: str,
    rule_summary: str,
    recommended_directions: list[str],
    matched_jobs: list[dict],
    recommendation_count: int,
    score_references: list[dict],
    risks: list[str],
    sources: list[dict],
    policy_answer: str = "",
) -> str:
    """Combine cached skill guidance with request-specific runtime context."""
    del rule_summary, recommended_directions, score_references
    job_facts = [_build_job_fact(job) for job in matched_jobs if not job.get("data_error")]
    structured_count = len(job_facts)
    context = {
        "当前任务": "对岗位推荐结果进行 AI 分析",
        "用户问题": payload.question,
        "识别意图": intent,
        "推荐岗位数量": structured_count,
        "用户条件": {
            "目标类型": payload.target,
            "考试类型": payload.exam_type,
            "目标省份": payload.region,
            "目标城市": payload.city,
            "学历": payload.education,
            "专业": payload.major,
            "身份": payload.identity,
        },
        "用户尚未明确的信息": _profile_missing_fields(payload),
        "岗位数据": job_facts,
        "已知风险提醒": [str(item) for item in risks if str(item).strip()],
        "有可核验政策来源": bool(sources),
        "政策解释": str(policy_answer or "").strip() or None,
        "政策来源摘要": [
            {
                "document_name": source.get("document_name") or source.get("title") or "政策来源",
                "page": source.get("page") or None,
                "text_preview": _summarize_long_field(
                    source.get("text_preview") or source.get("snippet"),
                    max_length=220,
                ),
            }
            for source in sources[:5]
            if isinstance(source, dict)
        ],
    }
    return f"""
【分析规则】
{load_skill_core()}

【本次任务与数据】
实际返回 {structured_count} 个岗位，必须严格分析这 {structured_count} 个，不得增加、减少或重排。
调用方给出的数量为 {recommendation_count}；如两者不一致，以实际岗位数组长度 {structured_count} 为准。
{json.dumps(context, ensure_ascii=False, indent=2)}

【页面输出要求】
{JOB_ANALYSIS_PAGE_CONTRACT_PROMPT}

{JOB_ANALYSIS_RUNTIME_SAFETY_PROMPT}
""".strip()


def _build_job_fact(job: dict) -> dict[str, Any]:
    score_match_type = str(job.get("score_match_type") or "no_match")
    applicant_count = _optional_value(
        _first_non_empty(job, "applicant_count", "applicants_count", "registration_count")
    )
    competition_ratio = _optional_value(job.get("competition_ratio"))
    min_score = _optional_value(
        _first_non_empty(job, "min_score", "min_interview_score")
    )
    return {
        "position_name": job.get("position_name") or job.get("position") or None,
        "target": job.get("target") or None,
        "department": job.get("department") or job.get("unit") or None,
        "unit": job.get("unit") or None,
        "full_position_code": (
            job.get("full_position_code")
            or job.get("display_position_code")
            or job.get("position_code")
            or job.get("job_id")
            or None
        ),
        "province": job.get("province") or job.get("region") or None,
        "city": job.get("city") or job.get("district") or None,
        "district": job.get("district") or None,
        "work_location": job.get("work_location") or None,
        "location_summary": _job_location_summary(job),
        "year": job.get("year") or None,
        "exam_type": job.get("exam_type") or None,
        "position_category": job.get("position_category") or None,
        "job_description": _summarize_long_field(job.get("job_description"), max_length=180),
        "recruit_count": _optional_value(
            _first_non_empty(job, "recruit_count", "headcount")
        ),
        "education_requirement": (
            job.get("education_requirement")
            or job.get("education_required")
            or job.get("education")
            or None
        ),
        "degree_requirement": job.get("degree") or job.get("degree_requirement") or None,
        "major_requirement": _summarize_long_field(
            job.get("major_requirement") or job.get("major_required")
        ),
        "identity_requirement": job.get("identity_requirement") or job.get("identity_required") or None,
        "age_requirement": job.get("age_requirement") or None,
        "political_requirement": job.get("political_requirement") or None,
        "grassroots_requirement": job.get("grassroots_requirement") or None,
        "fresh_graduate_requirement": job.get("fresh_graduate_required") or None,
        "service_project_requirement": job.get("service_project_required") or None,
        "household_requirement": _first_non_empty(
            job,
            "household_requirement",
            "household_registration_requirement",
            "residence_requirement",
            "domicile_requirement",
        ),
        "certificate_requirement": _first_non_empty(
            job,
            "certificate_requirement",
            "qualification_certificate",
            "professional_certificate",
        ),
        "gender_requirement": job.get("gender_requirement") or job.get("gender") or None,
        "service_period_requirement": _first_non_empty(
            job,
            "service_period_requirement",
            "minimum_service_years",
            "min_service_years",
            "service_years",
            "service_period",
        ),
        "establishment_type": _first_non_empty(
            job,
            "establishment_type",
            "employment_type",
            "staffing_type",
        ),
        "police_position": job.get("police_position") or None,
        "professional_test": job.get("professional_test") or None,
        "position_notes": _summarize_long_field(
            job.get("notes") or job.get("remark") or job.get("remarks"),
            max_length=220,
        ),
        "remark": _summarize_long_field(
            job.get("remark") or job.get("remarks"),
            max_length=160,
        ),
        "min_score": min_score,
        "interview_count": _optional_value(job.get("interview_count")),
        "score_match_type": score_match_type,
        "score_confidence": _optional_value(
            job.get("score_confidence", job.get("score_match_confidence"))
        ),
        "score_match_reason": job.get("score_match_reason") or None,
        "score_source_year": job.get("score_source_year") or None,
        "applicant_count": applicant_count,
        "competition_ratio": competition_ratio,
        "missing_data": {
            "applicant_count": applicant_count is None,
            "competition_ratio": competition_ratio is None,
            "exact_min_score": not (
                score_match_type == "exact_position_code" and min_score is not None
            ),
        },
        "risk_flags": list(job.get("risk_flags") or []),
        "risk_notes": [
            str(item)
            for item in (job.get("risk_notes") or [])
            if str(item).strip()
        ][:5],
        "verify_notes": [
            str(item)
            for item in (job.get("verify_notes") or [])
            if str(item).strip()
        ][:5],
        "recommendation_reason": (
            job.get("recommendation_reason")
            or job.get("short_reason")
            or None
        ),
        "data_source_label": job.get("data_source_label") or None,
        "score_data_source_label": job.get("score_data_source_label") or None,
    }


def _job_location_summary(job: dict) -> str | None:
    locations = []
    for value in [job.get("city"), job.get("district")]:
        text = str(value or "").strip()
        if text and text not in locations:
            locations.append(text)
    if not locations:
        fallback = str(
            job.get("work_location")
            or job.get("province")
            or job.get("region")
            or ""
        ).strip()
        if fallback:
            locations.append(fallback)
    return " / ".join(locations) or None


def _profile_missing_fields(payload: AgentAnalyzeRequest) -> list[str]:
    fields = {
        "education": payload.education,
        "major": payload.major,
        "identity": payload.identity,
    }
    return [
        key
        for key, value in fields.items()
        if str(value or "").strip() in {"", "不限", "未设置", "未填写", "请选择"}
    ]


def _optional_value(value: Any) -> Any:
    if value is None or str(value).strip() == "":
        return None
    return value


def _first_non_empty(values: dict, *keys: str) -> Any:
    for key in keys:
        value = values.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value) if isinstance(value, dict) else {}


def _summarize_long_field(value: Any, max_length: int = 140) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."
