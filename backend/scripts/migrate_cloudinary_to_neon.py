"""Legacy migration tool: Migrate Cloudinary documents to Neon Object Storage.

Usage:
    python -m scripts.migrate_cloudinary_to_neon [--dry-run] [--limit N] [--subject-id UUID]

Rules:
- Preserves original record ID
- Verifies upload with Neon S3 before updating DB
- NEVER deletes Cloudinary assets
- Supports --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

# Setup python path to import app modules if run directly
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.api.routes.resources import _fetch_file_from_cloudinary, _safe_filename, ALLOWED_TYPES
from app.db.models import Resource
from app.db.session import get_session_factory
from app.services.storage import neon_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_cloudinary_to_neon")


def migrate_records(*, dry_run: bool = False, limit: int | None = None, subject_id: UUID | None = None) -> dict[str, int]:
    stats = {"total_found": 0, "migrated": 0, "skipped": 0, "failed": 0}
    factory = get_session_factory()
    session: Session = factory()

    try:
        query = select(Resource).where(
            Resource.storage_key.is_(None),
            Resource.cloudinary_public_id.isnot(None),
        )
        if subject_id:
            query = query.where(Resource.subject_id == subject_id)
        if limit:
            query = query.limit(limit)

        records = list(session.scalars(query).all())
        stats["total_found"] = len(records)
        logger.info("Found %d legacy records to migrate (dry_run=%s)", len(records), dry_run)

        bucket = neon_storage.get_default_bucket()

        for rec in records:
            # Skip internal synthetic resources (e.g. gemini-only or local audio transcript)
            if (rec.cloudinary_public_id or "").startswith(("gemini-resource/", "audio-transcript/", "direct-resource/")):
                logger.info("Skipping internal synthetic resource %s (%s)", rec.id, rec.file_name)
                stats["skipped"] += 1
                continue

            logger.info("Processing record %s: %s (Public ID: %s)", rec.id, rec.file_name, rec.cloudinary_public_id)

            try:
                # 1. Download file content from Cloudinary
                _, extension = _safe_filename(rec.file_name)
                resource_type = ALLOWED_TYPES.get(extension, ("", "raw"))[1]
                content, mime_type = _fetch_file_from_cloudinary(
                    rec.cloudinary_public_id or "", resource_type, rec.secure_url
                )
                if not content:
                    logger.warning("Empty content fetched for record %s, skipping", rec.id)
                    stats["failed"] += 1
                    continue

                # 2. Build collision-resistant Neon object key
                key = neon_storage.build_object_key(
                    user_id=rec.uploaded_by,
                    document_id=rec.id,
                    filename=rec.file_name,
                    prefix=f"subjects/{rec.subject_id}/resources",
                )

                if dry_run:
                    logger.info("[DRY-RUN] Would upload %d bytes to Neon: bucket=%s key=%s", len(content), bucket, key)
                    stats["migrated"] += 1
                    continue

                # 3. Upload to Neon Object Storage
                neon_storage.upload_file(
                    content=content,
                    key=key,
                    bucket=bucket,
                    content_type=mime_type or rec.mime_type,
                )

                # 4. Verify upload
                if not neon_storage.file_exists(key, bucket=bucket):
                    logger.error("Upload verification failed for key %s", key)
                    stats["failed"] += 1
                    continue

                # 5. Update database record preserving original ID
                rec.storage_provider = "neon"
                rec.storage_bucket = bucket
                rec.storage_key = key
                session.commit()
                logger.info("Successfully migrated record %s -> %s", rec.id, key)
                stats["migrated"] += 1

            except Exception as exc:
                logger.exception("Failed to migrate record %s (%s): %s", rec.id, rec.file_name, exc)
                session.rollback()
                stats["failed"] += 1

    finally:
        session.close()

    logger.info("Migration complete: %s", stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Cloudinary documents to Neon Object Storage")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and simulate migration without uploading or updating database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of records to process")
    parser.add_argument("--subject-id", type=str, default=None, help="Migrate records for a specific subject UUID only")
    args = parser.parse_args()

    sub_id = UUID(args.subject_id) if args.subject_id else None
    stats = migrate_records(dry_run=args.dry_run, limit=args.limit, subject_id=sub_id)
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
