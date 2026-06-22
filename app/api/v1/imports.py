"""API endpoints for structured exam data import and cleaning V1."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.schemas.imports import (
    DatasetRowsResponse,
    ImportConfirmResponse,
    ImportDeleteResponse,
    ImportPreviewResponse,
    ImportRemapRequest,
    ImportTemplateListResponse,
    ImportTemplateSaveRequest,
    ImportTemplateSaveResponse,
)
from app.services.import_service import (
    confirm_import_task,
    delete_import_dataset,
    delete_import_task,
    get_import_preview,
    list_templates,
    process_uploaded_file,
    public_preview,
    remap_import_task,
    save_template_for_task,
    view_import_dataset_rows,
)


router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload", response_model=ImportPreviewResponse)
async def upload_import_file(
    file: UploadFile = File(...),
    province: str | None = Form(None),
    exam_type: str | None = Form(None),
    year: int | None = Form(None),
) -> dict:
    """Upload a CSV/Excel file and return a cleaned preview."""
    try:
        content = await file.read()
        task = process_uploaded_file(
            file_name=file.filename or "upload",
            content=content,
            province=province,
            exam_type=exam_type,
            year=year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return public_preview(task)


@router.get("/{task_id}/preview", response_model=ImportPreviewResponse)
def get_import_task_preview(task_id: str) -> dict:
    """Return the saved preview for an import task."""
    try:
        return public_preview(get_import_preview(task_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/remap", response_model=ImportPreviewResponse)
def remap_import_preview(task_id: str, request: ImportRemapRequest) -> dict:
    """Re-clean a saved upload using user-edited field mapping."""
    try:
        return public_preview(
            remap_import_task(
                task_id,
                request.field_mapping,
                request.detected_type,
                selected_sheet=request.selected_sheet,
                header_row=request.header_row,
                sub_header_row=request.sub_header_row,
                data_start_row=request.data_start_row,
                outputs=request.outputs or None,
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/save-template", response_model=ImportTemplateSaveResponse)
def save_import_template_endpoint(task_id: str, request: ImportTemplateSaveRequest) -> dict:
    """Save the current field mapping as a reusable import template."""
    try:
        return save_template_for_task(
            task_id,
            template_name=request.template_name,
            province=request.province,
            data_type=request.data_type,
            exam_type=request.exam_type,
            source_keyword=request.source_keyword,
            sheet_keyword=request.sheet_keyword,
            field_mapping=request.field_mapping,
            header_row=request.header_row,
            sub_header_row=request.sub_header_row,
            data_start_row=request.data_start_row,
            outputs=request.outputs or None,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/templates", response_model=ImportTemplateListResponse)
def list_import_template_endpoint(
    data_type: str = Query(""),
    province: str = Query(""),
) -> dict:
    """List saved reusable import templates."""
    return list_templates(data_type=data_type, province=province)


@router.post("/{task_id}/confirm", response_model=ImportConfirmResponse)
def confirm_import(task_id: str) -> dict:
    """Confirm a preview task and write valid rows to the structured database."""
    try:
        return confirm_import_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/datasets/{dataset_id}", response_model=ImportDeleteResponse)
def delete_dataset(dataset_id: str) -> dict:
    """Delete one database dataset by stable catalog id."""
    try:
        return delete_import_dataset(dataset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}/rows", response_model=DatasetRowsResponse)
def get_dataset_rows(
    dataset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: str = Query("", max_length=200),
    sort_by: str = Query("", max_length=64),
    sort_order: str = Query("asc", max_length=4),
) -> dict:
    """Return a paginated online view of normalized database rows."""
    try:
        return view_import_dataset_rows(
            dataset_id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{task_id}", response_model=ImportDeleteResponse)
def delete_import(task_id: str) -> dict:
    """Legacy task-id deletion route for database-backed imports."""
    try:
        return delete_import_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
