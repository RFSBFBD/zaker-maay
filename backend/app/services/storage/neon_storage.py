from __future__ import annotations

import io
import logging
import os
import re
from pathlib import PurePosixPath
from typing import BinaryIO
from uuid import UUID

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StorageNotConfigured(Exception):
    """Raised when Neon/S3 object storage credentials or endpoints are not configured."""
    pass


class StorageOperationFailed(Exception):
    """Raised when an S3 storage operation encounters a failure."""
    pass


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and invalid characters."""
    clean = (filename or "").replace("\\", "/")
    leaf = PurePosixPath(clean).name
    # Strip null bytes and control chars
    leaf = re.sub(r"[\x00-\x1f\x7f]", "", leaf).strip()
    # Strip leading dots and slashes to prevent hidden files or traversal
    leaf = re.sub(r"^[./\\]+", "", leaf)
    if not leaf or leaf in {".", ".."}:
        leaf = "document.bin"
    return leaf[:255]


def build_object_key(
    *,
    user_id: UUID | str,
    document_id: UUID | str,
    filename: str,
    prefix: str = "users",
) -> str:
    """Build a collision-resistant, sanitized S3 object key.

    Format: {prefix}/{user_id}/documents/{document_id}/{sanitized_filename}
    """
    safe_user_id = str(user_id).replace("/", "").replace("\\", "")
    safe_doc_id = str(document_id).replace("/", "").replace("\\", "")
    safe_name = sanitize_filename(filename)
    return f"{prefix}/{safe_user_id}/documents/{safe_doc_id}/{safe_name}"


def get_s3_client():
    """Create and return a configured boto3 S3 client for Neon Object Storage."""
    settings = get_settings()
    endpoint = settings.aws_endpoint_url_s3
    access_key = settings.aws_access_key_id
    secret_key = settings.aws_secret_access_key
    region = settings.aws_region or "us-east-2"

    if not all((endpoint, access_key, secret_key)):
        raise StorageNotConfigured(
            "Neon Object Storage is not configured. Set AWS_ENDPOINT_URL_S3, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY."
        )

    # Neon Object Storage requires path-style addressing and S3v4 signatures
    s3_config = Config(
        s3={"addressing_style": "path"},
        signature_version="s3v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=s3_config,
    )


def get_default_bucket() -> str:
    """Return the configured Neon storage bucket name."""
    settings = get_settings()
    return settings.neon_storage_bucket or "ai-documents"


def ensure_bucket_exists(bucket: str | None = None) -> None:
    """Check if the bucket exists; create it if it does not."""
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=target_bucket)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchBucket"}:
            settings = get_settings()
            region = settings.aws_region or "us-east-2"
            create_args: dict = {"Bucket": target_bucket}
            if region != "us-east-1":
                create_args["CreateBucketConfiguration"] = {"LocationConstraint": region}
            try:
                client.create_bucket(**create_args)
                logger.info("Created Neon storage bucket: %s", target_bucket)
            except Exception as create_exc:
                logger.error("Failed to create bucket %s: %s", target_bucket, create_exc)
                raise StorageOperationFailed(f"Could not create bucket {target_bucket}") from create_exc
        else:
            raise StorageOperationFailed(f"Could not verify bucket {target_bucket}") from exc


def upload_file(
    content: bytes | BinaryIO,
    key: str,
    *,
    bucket: str | None = None,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, str]:
    """Upload binary content to Neon Object Storage.

    All uploaded user documents are kept private by default.
    """
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()

    extra_args: dict[str, object] = {
        "ServerSideEncryption": "AES256",
    }
    if content_type:
        extra_args["ContentType"] = content_type
    if metadata:
        extra_args["Metadata"] = metadata

    try:
        if isinstance(content, bytes):
            file_obj = io.BytesIO(content)
        else:
            file_obj = content

        client.upload_fileobj(
            Fileobj=file_obj,
            Bucket=target_bucket,
            Key=key,
            ExtraArgs=extra_args,
        )
        return {
            "bucket": target_bucket,
            "key": key,
            "storage_provider": "neon",
        }
    except Exception as exc:
        logger.exception("Neon storage upload failed for key: %s", key)
        raise StorageOperationFailed(f"Failed to upload file to Neon storage: {exc}") from exc


def download_file(key: str, *, bucket: str | None = None) -> bytes:
    """Download a file from Neon Object Storage as bytes."""
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    try:
        buffer = io.BytesIO()
        client.download_fileobj(Bucket=target_bucket, Key=key, Fileobj=buffer)
        return buffer.getvalue()
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchKey"}:
            raise FileNotFoundError(f"Object {key} not found in bucket {target_bucket}") from exc
        raise StorageOperationFailed(f"Failed to download object {key}: {exc}") from exc
    except Exception as exc:
        raise StorageOperationFailed(f"Unexpected error downloading object {key}: {exc}") from exc


def download_file_to_path(key: str, target_path: str, *, bucket: str | None = None) -> None:
    """Download a file directly to a destination filesystem path."""
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    try:
        client.download_file(Bucket=target_bucket, Key=key, Filename=target_path)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchKey"}:
            raise FileNotFoundError(f"Object {key} not found in bucket {target_bucket}") from exc
        raise StorageOperationFailed(f"Failed to download object {key}: {exc}") from exc
    except Exception as exc:
        raise StorageOperationFailed(f"Failed to download object {key} to {target_path}: {exc}") from exc


def delete_file(key: str, *, bucket: str | None = None) -> bool:
    """Delete a file from Neon Object Storage."""
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    try:
        client.delete_object(Bucket=target_bucket, Key=key)
        return True
    except Exception as exc:
        logger.exception("Neon storage delete failed for key: %s", key)
        raise StorageOperationFailed(f"Failed to delete object {key}: {exc}") from exc


def file_exists(key: str, *, bucket: str | None = None) -> bool:
    """Check if an object exists in Neon Object Storage."""
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    try:
        client.head_object(Bucket=target_bucket, Key=key)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchKey"}:
            return False
        logger.warning("Error checking file existence for key %s: %s", key, exc)
        return False
    except Exception:
        return False


def list_files(prefix: str = "", *, bucket: str | None = None, max_keys: int = 1000) -> list[str]:
    """List object keys under a given prefix."""
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    try:
        resp = client.list_objects_v2(Bucket=target_bucket, Prefix=prefix, MaxKeys=max_keys)
        contents = resp.get("Contents", [])
        return [item["Key"] for item in contents if "Key" in item]
    except Exception as exc:
        raise StorageOperationFailed(f"Failed to list objects with prefix '{prefix}': {exc}") from exc


def generate_presigned_url(
    key: str,
    *,
    expires_in: int = 600,
    bucket: str | None = None,
    filename: str | None = None,
) -> str:
    """Generate a temporary presigned GET URL for secure downloading."""
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    params: dict[str, str] = {
        "Bucket": target_bucket,
        "Key": key,
    }
    if filename:
        safe_name = sanitize_filename(filename)
        params["ResponseContentDisposition"] = f'attachment; filename="{safe_name}"'

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        logger.exception("Failed to generate presigned URL for key: %s", key)
        raise StorageOperationFailed(f"Failed to generate download URL: {exc}") from exc


def generate_presigned_upload_url(
    key: str,
    *,
    content_type: str,
    expires_in: int = 600,
    bucket: str | None = None,
) -> str:
    """Generate a temporary presigned PUT URL so the browser can upload a file
    directly to Neon Object Storage, bypassing the backend entirely (and with it,
    the hosting platform's serverless request-body size limit).
    """
    target_bucket = bucket or get_default_bucket()
    client = get_s3_client()
    try:
        url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": target_bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        logger.exception("Failed to generate presigned upload URL for key: %s", key)
        raise StorageOperationFailed(f"Failed to generate upload URL: {exc}") from exc

