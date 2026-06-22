from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_current_user
from app.db import repositories
from app.schemas.product_schema import UserProfilePayload
from app.services.product_service import profile_payload_updates, serialize_profile


router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile")
def get_profile(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    return {
        "user_id": user["id"],
        "profile": serialize_profile(repositories.get_user_profile(user["id"])),
    }


@router.put("/profile")
def update_profile(
    payload: UserProfilePayload,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del request
    profile = repositories.upsert_user_profile(
        user["id"],
        profile_payload_updates(payload),
    )
    return {
        "user_id": user["id"],
        "profile": serialize_profile(profile),
    }
