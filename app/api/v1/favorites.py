from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import get_current_user
from app.db import repositories
from app.schemas.product_schema import FavoriteJobRequest
from app.services.product_service import model_dump, sanitize_for_storage


router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.post("/jobs")
def save_favorite_job(
    payload: FavoriteJobRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    data = model_dump(payload)
    data["raw_job_json"] = sanitize_for_storage(data.get("raw_job_json") or {})
    favorite = repositories.upsert_favorite(user["id"], data)
    return {"favorite": favorite, "items": repositories.list_favorites(user["id"])}


@router.get("/jobs")
def get_favorite_jobs(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    items = repositories.list_favorites(user["id"])
    return {"items": items, "count": len(items)}


@router.delete("/jobs/{favorite_id}")
def remove_favorite_job(
    favorite_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    if not repositories.delete_favorite(user["id"], favorite_id):
        raise HTTPException(status_code=404, detail="收藏不存在")
    return {"deleted": True, "favorite_id": favorite_id}
