from typing import Any, Optional

from pydantic import BaseModel, Field


class DevLoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    nickname: str = Field("", max_length=80)


class AuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    email: str = Field("", max_length=200)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field("", max_length=80)


class AuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class UserProfilePayload(BaseModel):
    education_level: Optional[str] = Field(None, max_length=80)
    degree: Optional[str] = Field(None, max_length=80)
    major: Optional[str] = Field(None, max_length=200)
    graduation_year: Optional[int] = Field(None, ge=1950, le=2100)
    is_fresh_graduate: Optional[bool] = None
    political_status: Optional[str] = Field(None, max_length=80)
    target_region: Optional[str] = Field(None, max_length=160)
    target_exam_type: Optional[str] = Field(None, max_length=80)
    target_job_type: Optional[str] = Field(None, max_length=120)
    score_estimate: Optional[float] = Field(None, ge=0, le=1000)
    work_preference: Optional[str] = Field(None, max_length=500)
    risk_preference: Optional[str] = Field(None, max_length=80)
    raw_profile_json: dict[str, Any] = Field(default_factory=dict)

    # Web 工作台兼容字段，统一保存到 raw_profile_json。
    province: Optional[str] = Field(None, max_length=80)
    city: Optional[str] = Field(None, max_length=80)
    exam_type: Optional[str] = Field(None, max_length=80)
    education: Optional[str] = Field(None, max_length=80)
    identity: Optional[str] = Field(None, max_length=120)
    accept_relocation: Optional[str] = Field(None, max_length=80)
    preferences: list[str] = Field(default_factory=list)
    filled_fields: list[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    title: str = Field("新会话", max_length=120)
    scene: str = Field("general_chat", max_length=40)


class SessionMessageCreateRequest(BaseModel):
    role: str = Field("user", max_length=20)
    content: str = Field(..., min_length=1, max_length=100000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class FavoriteJobRequest(BaseModel):
    job_id: str = Field(..., min_length=1, max_length=160)
    job_name: str = Field("", max_length=300)
    department_name: str = Field("", max_length=300)
    region: str = Field("", max_length=160)
    exam_type: str = Field("", max_length=80)
    raw_job_json: dict[str, Any] = Field(default_factory=dict)
    note: str = Field("", max_length=1000)


class ReportCreateRequest(BaseModel):
    agent_run_id: Optional[int] = Field(None, ge=1)
    session_id: Optional[int] = Field(None, ge=1)
    title: str = Field("", max_length=200)
    report_type: str = Field("job_analysis", max_length=80)
    content: str = Field("", max_length=100000)
    summary: str = Field("", max_length=5000)
    related_jobs_json: list[dict[str, Any]] = Field(default_factory=list)
    citations_json: list[dict[str, Any]] = Field(default_factory=list)
