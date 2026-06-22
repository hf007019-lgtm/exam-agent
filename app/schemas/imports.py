"""Pydantic schemas for structured data import APIs."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ImportWarningItem(BaseModel):
    row_index: Optional[int] = None
    level: str = "warning"
    message: str
    count: Optional[int] = None
    raw_value: Any = None
    field: str = ""
    source_column: str = ""


class ImportPreviewResponse(BaseModel):
    task_id: str
    file_name: str
    detected_type: str
    detected_type_label: str
    confidence: float
    total_rows: int
    valid_rows: int
    warning_rows: int
    warning_count: int = 0
    province: str = ""
    exam_type: str = ""
    year: Optional[int] = None
    importable: bool = True
    requires_type_confirmation: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    field_status: list[dict[str, Any]] = Field(default_factory=list)
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)
    field_mapping: dict[str, str] = Field(default_factory=dict)
    field_mapping_by_source: dict[str, str] = Field(default_factory=dict)
    source_headers: list[str] = Field(default_factory=list)
    standard_fields: list[str] = Field(default_factory=list)
    field_labels: dict[str, str] = Field(default_factory=dict)
    data_granularity: str = "unknown"
    required_fields: list[str] = Field(default_factory=list)
    required_any_fields: list[str] = Field(default_factory=list)
    required_any_groups: list[list[str]] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    available_types: list[dict[str, Any]] = Field(default_factory=list)
    template_applied: bool = False
    template_id: Optional[int] = None
    template_name: str = ""
    template_message: str = ""
    warnings: list[ImportWarningItem] = Field(default_factory=list)
    warning_summary: list[ImportWarningItem] = Field(default_factory=list)
    import_report: dict[str, Any] = Field(default_factory=dict)
    sheet_summary: str = ""
    sheet_options: list[str] = Field(default_factory=list)
    selected_sheet: str = ""
    header_row: Optional[int] = None
    sub_header_row: Optional[int] = None
    data_start_row: Optional[int] = None
    type_candidates: list[dict[str, Any]] = Field(default_factory=list)
    type_conflict_reasons: list[str] = Field(default_factory=list)
    type_confirmed: bool = False
    multi_output: bool = False
    mixed_output_label: str = ""
    requires_output_confirmation: bool = False
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    status: str


class ImportConfirmResponse(BaseModel):
    task_id: str
    status: str
    target: str = ""
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    warning_count: int = 0
    valid_rows: int = 0
    warning_rows: int = 0
    dataset_id: str = ""
    inserted_rows: int = 0
    skipped_rows: int = 0
    storage: str = "database"
    message: str = ""
    output_results: list[dict[str, Any]] = Field(default_factory=list)


class ImportDeleteResponse(BaseModel):
    dataset_id: str = ""
    task_id: str = ""
    status: str
    deleted_rows: int
    message: str = ""


class DatasetColumn(BaseModel):
    key: str
    label: str


class DatasetRowsResponse(BaseModel):
    dataset_id: str
    title: str
    data_type: str
    data_type_label: str
    province: str = ""
    year: Optional[int] = None
    exam_type: str = ""
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    columns: list[DatasetColumn] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    privacy_notice: str = ""
    message: str = ""


class ImportRemapRequest(BaseModel):
    field_mapping: dict[str, str] = Field(default_factory=dict)
    detected_type: str = ""
    selected_sheet: str = ""
    header_row: Optional[int] = Field(default=None, ge=1)
    sub_header_row: Optional[int] = Field(default=None, ge=1)
    data_start_row: Optional[int] = Field(default=None, ge=1)
    outputs: list[dict[str, Any]] = Field(default_factory=list)


class ImportTemplateSaveRequest(BaseModel):
    template_name: str
    province: str = ""
    data_type: str = ""
    exam_type: str = ""
    source_keyword: str = ""
    sheet_keyword: str = ""
    field_mapping: dict[str, str] = Field(default_factory=dict)
    header_row: Optional[int] = Field(default=None, ge=1)
    sub_header_row: Optional[int] = Field(default=None, ge=1)
    data_start_row: Optional[int] = Field(default=None, ge=1)
    outputs: list[dict[str, Any]] = Field(default_factory=list)


class ImportTemplateSaveResponse(BaseModel):
    status: str
    message: str
    template: dict[str, Any] = Field(default_factory=dict)


class ImportTemplateListResponse(BaseModel):
    total: int
    items: list[dict[str, Any]] = Field(default_factory=list)
