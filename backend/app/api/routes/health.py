from fastapi import APIRouter

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, object]:
    settings = get_settings()
    services = {
        "database": bool(settings.database_url),
        "supabase_auth": bool(
            (settings.supabase_url or (settings.supabase_jwt_issuer and settings.supabase_jwt_jwks_url))
            and settings.supabase_jwt_audience
        ),
        "cloudinary": bool(
            settings.cloudinary_cloud_name
            and settings.cloudinary_api_key
            and settings.cloudinary_api_secret
        ),
        "gemini": bool(settings.gemini_api_key),
    }
    return {
        "status": "configured_unchecked" if all(services.values()) else "not_configured",
        "services": services,
    }


@router.get("/config")
def config_check(settings: Settings = get_settings()) -> dict[str, object]:
    """Report configuration presence only; never include configuration values."""
    keys = {
        "database_url": settings.database_url,
        "supabase_auth": bool(
            (settings.supabase_url or (settings.supabase_jwt_issuer and settings.supabase_jwt_jwks_url))
            and settings.supabase_jwt_audience
        ),
        "cloudinary": settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret,
        "gemini": settings.gemini_api_key,
    }
    return {"configured": {name: bool(value) for name, value in keys.items()}}
