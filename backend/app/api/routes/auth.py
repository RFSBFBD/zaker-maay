from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import get_current_profile
from app.db.models import UserProfile

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me")
def me(profile: Annotated[UserProfile, Depends(get_current_profile)]) -> dict[str, object]:
    return {"id": str(profile.id), "email": profile.email, "role": profile.role}

