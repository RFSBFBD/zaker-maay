from datetime import datetime, timezone
from typing import Any

import cloudinary
from cloudinary import uploader, utils

from app.core.config import get_settings


class StorageNotConfigured(Exception):
    pass


class StorageOperationFailed(Exception):
    pass


def _configure() -> None:
    settings = get_settings()
    if not all((settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret)):
        raise StorageNotConfigured
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def upload_private_asset(content: bytes, *, public_id: str, resource_type: str) -> dict[str, Any]:
    _configure()
    try:
        result = uploader.upload(
            content,
            public_id=public_id,
            resource_type=resource_type,
            type="authenticated",
            overwrite=False,
            unique_filename=False,
            use_filename=False,
            invalidate=True,
        )
    except Exception as exc:
        raise StorageOperationFailed from exc
    if not isinstance(result, dict) or not result.get("public_id"):
        raise StorageOperationFailed
    return result


def delete_asset(*, public_id: str, resource_type: str) -> None:
    _configure()
    try:
        result = uploader.destroy(public_id, resource_type=resource_type, type="authenticated", invalidate=True)
    except Exception as exc:
        raise StorageOperationFailed from exc
    if result.get("result") not in {"ok", "not found"}:
        raise StorageOperationFailed


def create_download_url(*, public_id: str, extension: str, resource_type: str) -> str:
    _configure()
    try:
        return utils.private_download_url(
            public_id,
            extension,
            resource_type=resource_type,
            type="authenticated",
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 600,
            attachment=True,
        )
    except Exception as exc:
        raise StorageOperationFailed from exc
