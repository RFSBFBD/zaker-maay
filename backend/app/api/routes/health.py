from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, object]:
    """Lightweight health check verifying application and subsystem configurations."""
    settings = get_settings()
    has_neon_storage = bool(
        settings.aws_endpoint_url_s3
        and settings.aws_access_key_id
        and settings.aws_secret_access_key
    )
    has_cloudinary = bool(
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    )
    storage_provider = "neon" if has_neon_storage else ("cloudinary" if has_cloudinary else "none")

    # Fast DB check if configured
    db_ok = False
    if settings.database_url:
        try:
            factory = get_session_factory()
            with factory() as session:
                session.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            db_ok = False

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "checks": {
            "database": db_ok,
            "storage": has_neon_storage or has_cloudinary,
            "storage_provider": storage_provider,
            "ai_provider": bool(settings.gemini_api_key),
        },
    }


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, object]:
    settings = get_settings()
    has_neon_storage = bool(
        settings.aws_endpoint_url_s3
        and settings.aws_access_key_id
        and settings.aws_secret_access_key
    )
    has_cloudinary = bool(
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    )
    services = {
        "database": bool(settings.database_url),
        "supabase_auth": bool(
            (settings.supabase_url or (settings.supabase_jwt_issuer and settings.supabase_jwt_jwks_url))
            and settings.supabase_jwt_audience
        ),
        "cloudinary": has_cloudinary or has_neon_storage,
        "gemini": bool(settings.gemini_api_key),
    }
    return {
        "status": "configured_unchecked" if all(services.values()) else "not_configured",
        "services": services,
    }


@router.get("/config")
def config_check(settings: Settings = get_settings()) -> dict[str, object]:
    """Report configuration presence only; never include configuration values."""
    has_neon_storage = bool(
        settings.aws_endpoint_url_s3
        and settings.aws_access_key_id
        and settings.aws_secret_access_key
    )
    keys = {
        "database_url": bool(settings.database_url),
        "supabase_auth": bool(
            (settings.supabase_url or (settings.supabase_jwt_issuer and settings.supabase_jwt_jwks_url))
            and settings.supabase_jwt_audience
        ),
        "neon_storage": has_neon_storage,
        "cloudinary_legacy": bool(
            settings.cloudinary_cloud_name
            and settings.cloudinary_api_key
            and settings.cloudinary_api_secret
        ),
        "gemini": bool(settings.gemini_api_key),
    }
    return {"configured": keys}
