from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import UserProfile
from app.db.session import get_db

SUPPORTED_ALGORITHMS = ["ES256", "RS256"]
bearer_scheme = HTTPBearer(auto_error=False, bearerFormat="JWT")


class UserIdentity(BaseModel):
    id: UUID
    email: str | None = None


class AuthConfigurationError(Exception):
    pass


@lru_cache(maxsize=8)
def get_jwks_client(jwks_url: str) -> PyJWKClient:
    parsed = urlparse(jwks_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise AuthConfigurationError("JWKS URL must use HTTPS.")
    if not parsed.path.rstrip("/").endswith("/.well-known/jwks.json"):
        raise AuthConfigurationError("JWKS URL path is invalid.")
    return PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=600, timeout=5)


def verify_access_token(
    token: str,
    settings: Settings,
    jwks_client: Any,
) -> UserIdentity:
    if not settings.supabase_jwt_issuer or not settings.supabase_jwt_audience:
        raise AuthConfigurationError("JWT issuer and audience must be configured.")
    key = jwks_client.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token,
        key,
        algorithms=SUPPORTED_ALGORITHMS,
        issuer=settings.supabase_jwt_issuer,
        audience=settings.supabase_jwt_audience,
        options={"require": ["exp", "iss", "aud", "sub"]},
    )
    if claims.get("role") != "authenticated":
        raise jwt.InvalidTokenError("Token is not an authenticated user token.")
    return UserIdentity(id=claims["sub"], email=claims.get("email"))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserIdentity:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not settings.supabase_jwt_jwks_url:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    try:
        issuer = urlparse(settings.supabase_jwt_issuer or "")
        jwks = urlparse(settings.supabase_jwt_jwks_url)
        if issuer.scheme != "https" or issuer.hostname != jwks.hostname:
            raise AuthConfigurationError("JWT issuer and JWKS endpoint must share an HTTPS host.")
        client = get_jwks_client(settings.supabase_jwt_jwks_url)
        return verify_access_token(credentials.credentials, settings, client)
    except AuthConfigurationError:
        raise HTTPException(status_code=503, detail="Authentication is not configured.") from None
    except PyJWKClientConnectionError:
        raise HTTPException(status_code=503, detail="Authentication provider is unavailable.") from None
    except (PyJWTError, ValidationError, ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_current_profile(
    identity: Annotated[UserIdentity, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserProfile:
    """Create a default student profile on first verified sign-in."""
    profile = db.scalar(select(UserProfile).where(UserProfile.auth_user_id == str(identity.id)))
    if profile is not None:
        now = datetime.now(timezone.utc)
        if profile.last_active_at is None or (now - profile.last_active_at).total_seconds() > 60:
            profile.last_active_at = now
            try:
                db.commit()
            except Exception:
                db.rollback()
        return profile

    profile = UserProfile(
        id=identity.id,
        auth_user_id=str(identity.id),
        email=identity.email,
        role="student",
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        profile = db.scalar(select(UserProfile).where(UserProfile.auth_user_id == str(identity.id)))
        if profile is None:
            raise HTTPException(status_code=503, detail="Profile could not be initialized.") from None
        return profile
    db.refresh(profile)
    return profile
