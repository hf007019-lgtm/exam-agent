from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Recent chat message passed by the frontend for multi-turn context."""

    role: str
    content: str


class CurrentJobContext(BaseModel):
    """Most recent job card passed by the frontend for contextual follow-up."""

    position_code: str = ""
    job_title: str = ""
    department: str = ""
    unit_name: str = ""
    province: str = ""
    region: str = ""
    city: str = ""
    year: int = 0
    exam_type: str = ""
    recruit_count: Optional[int] = None
    education_requirement: str = ""
    degree_requirement: str = ""
    major_requirement: str = ""
    identity_requirement: str = ""
    political_requirement: str = ""
    grassroots_requirement: str = ""
    qualification_requirement: str = ""
    agency_level: str = ""
    is_public_service: str = ""
    is_law_enforcement: str = ""
    job_description: str = ""
    contact_phone: str = ""
    work_address: str = ""
    remark: str = ""
    min_score: Optional[float] = None
    avg_score: Optional[float] = None
    max_score: Optional[float] = None
    score_match_type: str = "no_match"
    score_match_confidence: Optional[float] = None
    score_match_reason: str = ""
    registration_count: Optional[int] = None
    competition_ratio: Optional[str] = None
    interview_count: Optional[int] = None
    notes: str = ""
    data_source_label: str = ""
    score_data_source_label: str = ""
    score_source_type: str = ""
    score_sample_count: int = 0
    review_score_sample: dict[str, Any] = Field(default_factory=dict)
    candidate_score_sample: dict[str, Any] = Field(default_factory=dict)
    candidate_score_sample_count: int = 0
    review_written_score_min: Optional[float] = None
    review_written_score_max: Optional[float] = None
    review_written_score_avg: Optional[float] = None
    review_xingce_score_min: Optional[float] = None
    review_xingce_score_max: Optional[float] = None
    review_xingce_score_avg: Optional[float] = None
    review_shenlun_score_min: Optional[float] = None
    review_shenlun_score_max: Optional[float] = None
    review_shenlun_score_avg: Optional[float] = None
    review_professional_score_min: Optional[float] = None
    review_professional_score_max: Optional[float] = None
    review_professional_score_avg: Optional[float] = None
    review_total_score_min: Optional[float] = None
    review_total_score_max: Optional[float] = None
    review_total_score_avg: Optional[float] = None
    review_rank_min: Optional[float] = None
    review_rank_max: Optional[float] = None
    candidate_written_score_min: Optional[float] = None
    candidate_written_score_max: Optional[float] = None
    candidate_written_score_avg: Optional[float] = None
    candidate_interview_score_min: Optional[float] = None
    candidate_interview_score_max: Optional[float] = None
    candidate_interview_score_avg: Optional[float] = None
    candidate_total_score_min: Optional[float] = None
    candidate_total_score_max: Optional[float] = None
    candidate_total_score_avg: Optional[float] = None
    candidate_rank_min: Optional[float] = None
    candidate_rank_max: Optional[float] = None


class AgentAnalyzeRequest(BaseModel):
    """用户提交的报考条件。"""

    mode: str = Field("", example="job_recommendation")
    target: str = Field("公务员", example="事业编")
    exam_type: str = Field("省考", example="省考")
    region: str = Field("不限", example="广东")
    city: str = Field("不限", example="广州")
    education: str = Field("不限", example="本科")
    major: str = Field("", example="软件工程")
    identity: str = Field("不限", example="应届生")
    question: str = Field(..., example="我适合报哪些岗位方向？有什么风险？")
    result_limit: Optional[int] = Field(None, ge=1, le=5)
    messages: List[ChatMessage] = Field(default_factory=list)
    current_job: Optional[CurrentJobContext] = None
    last_recommendations: List[CurrentJobContext] = Field(default_factory=list)
    session_id: Optional[int] = Field(None, ge=1)
    profile: dict[str, Any] = Field(default_factory=dict)
    save_history: bool = False


class PolicySource(BaseModel):
    """政策来源信息。"""

    doc_id: Any = None
    chunk_id: str = ""
    document_name: str = ""
    score: Any = None
    text_preview: str = ""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source_type: str = ""
    page: str = ""
    confidence: Any = None


class JobAIAnalysis(BaseModel):
    """岗位卡片展开后展示的自然语言分析。"""

    why_recommended: str = ""
    qualification_match: str = ""
    major_match: str = ""
    direction_fit: str = ""
    recruit_risk: str = ""
    competition_data: str = ""
    verify_before_apply: str = ""


class MatchedJob(BaseModel):
    """经过硬性过滤和规则评分后推荐的岗位信息。"""

    job_id: str
    year: int = 0
    target: str
    exam_type: str = ""
    region: str
    province: str = ""
    city: str = ""
    district: str = ""
    position_code: str = ""
    display_position_code: str = ""
    full_position_code: str = ""
    raw_position_code: str = ""
    source_position_code: str = ""
    score_match_position_code: str = ""
    matched_position_code: str = ""
    source_type: str = ""
    data_status: str = ""
    job_source_file: str = ""
    job_source_year: int = 0
    department: str
    unit: str = ""
    unit_name: str = ""
    position: str
    position_name: str = ""
    education_required: str
    education_requirement: str = ""
    degree_requirement: str = ""
    major_required: str
    major_requirement: str = ""
    identity_required: str
    identity_requirement: str = ""
    political_requirement: str = ""
    grassroots_requirement: str = ""
    qualification_requirement: str = ""
    agency_level: str = ""
    is_public_service: str = ""
    is_law_enforcement: str = ""
    job_description: str = ""
    contact_phone: str = ""
    work_address: str = ""
    remark: str = ""
    headcount: int
    recruit_count: int = 0
    applicants_count: Optional[int] = None
    applicant_count: Optional[int] = None
    interview_count: Optional[int] = None
    min_interview_score: Optional[float] = None
    min_score: Optional[float] = None
    max_interview_score: Optional[float] = None
    avg_score: Optional[float] = None
    max_score: Optional[float] = None
    competition_ratio: Optional[str] = None
    competition_score: Optional[int] = None
    competition_level: str = "未知"
    work_location: str = ""
    notes: str = ""
    qualification_score: int = 0
    suitability_score: int = 0
    match_score: int = 0
    match_level: str = ""
    short_reason: str = ""
    recommendation_reason: str = ""
    risk_summary: str = ""
    match_reason: str = ""
    risk_notes: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    verify_notes: List[str] = Field(default_factory=list)
    ai_analysis: JobAIAnalysis = Field(default_factory=JobAIAnalysis)
    score_match_type: str = "no_match"
    score_source_file: str = ""
    score_source_year: int = 0
    score_match_confidence: Optional[float] = None
    score_confidence: Optional[float] = None
    score_match_reason: str = ""
    data_source_label: str = ""
    score_data_source_label: str = ""
    score_source_type: str = ""
    score_sample_count: int = 0
    review_score_sample: dict[str, Any] = Field(default_factory=dict)
    candidate_score_sample: dict[str, Any] = Field(default_factory=dict)
    candidate_score_sample_count: int = 0
    review_written_score_min: Optional[float] = None
    review_written_score_max: Optional[float] = None
    review_written_score_avg: Optional[float] = None
    review_xingce_score_min: Optional[float] = None
    review_xingce_score_max: Optional[float] = None
    review_xingce_score_avg: Optional[float] = None
    review_shenlun_score_min: Optional[float] = None
    review_shenlun_score_max: Optional[float] = None
    review_shenlun_score_avg: Optional[float] = None
    review_professional_score_min: Optional[float] = None
    review_professional_score_max: Optional[float] = None
    review_professional_score_avg: Optional[float] = None
    review_total_score_min: Optional[float] = None
    review_total_score_max: Optional[float] = None
    review_total_score_avg: Optional[float] = None
    review_rank_min: Optional[float] = None
    review_rank_max: Optional[float] = None
    candidate_written_score_min: Optional[float] = None
    candidate_written_score_max: Optional[float] = None
    candidate_written_score_avg: Optional[float] = None
    candidate_interview_score_min: Optional[float] = None
    candidate_interview_score_max: Optional[float] = None
    candidate_interview_score_avg: Optional[float] = None
    candidate_xingce_score_min: Optional[float] = None
    candidate_xingce_score_max: Optional[float] = None
    candidate_xingce_score_avg: Optional[float] = None
    candidate_shenlun_score_min: Optional[float] = None
    candidate_shenlun_score_max: Optional[float] = None
    candidate_shenlun_score_avg: Optional[float] = None
    candidate_professional_score_min: Optional[float] = None
    candidate_professional_score_max: Optional[float] = None
    candidate_professional_score_avg: Optional[float] = None
    candidate_total_score_min: Optional[float] = None
    candidate_total_score_max: Optional[float] = None
    candidate_total_score_avg: Optional[float] = None
    candidate_rank_min: Optional[float] = None
    candidate_rank_max: Optional[float] = None
    job_analysis_llm_used: bool = False
    job_analysis_model: str = ""
    job_analysis_error: str = ""


class ScoreReference(BaseModel):
    """真实历年分数线或进面参考信息。"""

    score_id: str = ""
    year: int = 0
    target: str = ""
    exam_type: str = ""
    region: str = ""
    city: str = ""
    position_code: str = ""
    display_position_code: str = ""
    full_position_code: str = ""
    raw_position_code: str = ""
    matched_position_code: str = ""
    department: str = ""
    unit: str = ""
    position_name: str = ""
    position_type: str = ""
    data_type: str = ""
    score_record_type: str = "score_line"
    score_label: str = ""
    is_min_score_reference: bool = True
    written_score: Optional[float] = None
    interview_score: Optional[float] = None
    total_score: Optional[float] = None
    rank: Optional[int] = None
    recruit_count: Optional[int] = None
    interview_count: Optional[int] = None
    min_interview_score: Optional[float] = None
    max_interview_score: Optional[float] = None
    min_score: Optional[float] = None
    avg_score: Optional[float] = None
    max_score: Optional[float] = None
    source_type: str = ""
    data_status: str = ""
    notes: str = ""


class AgentTraceStep(BaseModel):
    """Agent 执行过程中的单步记录。"""

    step: int
    name: str
    tool: str
    status: str
    input: dict[str, Any] = Field(default_factory=dict)
    output_summary: str = ""


class AgentAnalyzeResponse(BaseModel):
    """Agent 分析响应。"""

    intent: str
    summary: str
    analysis_report: str
    recommended_directions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    sources: List[PolicySource] = Field(default_factory=list)
    citations: List[PolicySource] = Field(default_factory=list)
    rag_used: bool = False
    rag_answer: str = ""
    matched_jobs: List[MatchedJob] = Field(default_factory=list)
    score_references: List[ScoreReference] = Field(default_factory=list)
    resolved_region: str = ""
    selected_province_slug: str = ""
    data_source_file: str = ""
    recommendation_count: int = 0
    fallback_reason: str = ""
    debug_request_raw_text: str = ""
    debug_request_payload: Any = None
    debug_agent_input: Any = None
    llm_used: bool = False
    tool_used: bool = False
    used_tools: List[str] = Field(default_factory=list)
    need_follow_up: bool = False
    missing_fields: List[str] = Field(default_factory=list)
    recommendations: List[MatchedJob] = Field(default_factory=list)
    trace: List[AgentTraceStep] = Field(default_factory=list)
    prompt_profile: str = "gongkao_selection_coach_v1"
    prompt_scene: str = ""
    is_context_followup: bool = False
    request_id: str = ""
    session_id: Optional[int] = None
    message_id: Optional[int] = None
    agent_run_id: Optional[int] = None
    persistence_warnings: List[str] = Field(default_factory=list)
