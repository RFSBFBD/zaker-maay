import hashlib
import io
import logging
import re
import zipfile
from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, computed_field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import get_current_profile
from app.core.config import get_settings
from app.db.models import Resource, ResourceChunk, Subject, SubjectMembership, UserProfile
from app.db.session import get_db
from app.services import cloudinary_storage
from app.services import gemini
from app.services.ai_router import safe_call_ai
from app.services.audio_processing import InvalidAudio, TRANSCRIBABLE_EXTENSIONS, inspect_audio
from app.services.document_processing import process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/subjects/{subject_id}/resources", tags=["resources"])

MAX_FILE_BYTES = 20 * 1024 * 1024
ALLOWED_TYPES: dict[str, tuple[str, str]] = {
    ".pdf": ("application/pdf", "raw"),
    ".txt": ("text/plain", "raw"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "raw"),
    ".mp3": ("audio/mpeg", "video"),
    ".wav": ("audio/wav", "video"),
    ".m4a": ("audio/mp4", "video"),
    ".webm": ("audio/webm", "video"),
}


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_id: UUID
    uploaded_by: UUID
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    processing_status: str
    transcript_language: str | None
    audio_duration_seconds: int | None
    created_at: datetime

    @computed_field
    @property
    def has_transcript(self) -> bool:
        return bool(self.transcript_language and self.audio_duration_seconds)


class DownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int = 600


class TranscriptResponse(BaseModel):
    resource_id: UUID
    language: str
    transcript: str
    model: str
    audio_duration_seconds: int
    timestamp_quality: str = "not_provided"


def _accessible_subject(db: Session, subject_id: UUID, profile: UserProfile) -> Subject:
    query = select(Subject).where(Subject.id == subject_id, Subject.archived_at.is_(None))
    if profile.role != "admin":
        query = query.join(SubjectMembership).where(SubjectMembership.user_id == profile.id)
    subject = db.scalar(query)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return subject


def _safe_filename(raw_name: str | None) -> tuple[str, str]:
    leaf = PurePosixPath((raw_name or "").replace("\\", "/")).name
    leaf = re.sub(r"[\x00-\x1f\x7f]", "", leaf).strip().strip(".")
    if not leaf or len(leaf) > 255:
        raise HTTPException(status_code=422, detail="Invalid file name.")
    extension = PurePosixPath(leaf).suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="File type is not supported.")
    return leaf, extension


def _validate_content(content: bytes, extension: str) -> str:
    mime_type = ALLOWED_TYPES[extension][0]
    valid = False
    if extension == ".pdf":
        valid = content.startswith(b"%PDF-")
    elif extension == ".txt":
        try:
            content.decode("utf-8")
            valid = b"\x00" not in content
        except UnicodeDecodeError:
            valid = False
    elif extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                names = {info.filename for info in infos}
                bounded = len(infos) <= 10_000 and sum(info.file_size for info in infos) <= 50 * 1024 * 1024
                safe_paths = all(not name.startswith("/") and ".." not in PurePosixPath(name).parts for name in names)
                valid = (
                    bounded
                    and safe_paths
                    and "[Content_Types].xml" in names
                    and "word/document.xml" in names
                )
        except (zipfile.BadZipFile, OSError):
            valid = False
    elif extension == ".mp3":
        valid = content.startswith(b"ID3") or (
            len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
        )
    elif extension == ".wav":
        valid = len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WAVE"
    elif extension == ".m4a":
        valid = len(content) >= 12 and content[4:8] == b"ftyp"
    elif extension == ".webm":
        valid = content.startswith(b"\x1aE\xdf\xa3")
    if not valid:
        raise HTTPException(status_code=415, detail="File content does not match its extension.")
    return mime_type


def _remove_orphan(public_id: str, resource_type: str) -> None:
    try:
        cloudinary_storage.delete_asset(public_id=public_id, resource_type=resource_type)
    except cloudinary_storage.StorageNotConfigured:
        logger.error("Cloudinary credentials became unavailable during orphan cleanup.")
    except cloudinary_storage.StorageOperationFailed:
        logger.error("Unable to remove an orphaned Cloudinary asset after a database failure.")


@router.get("", response_model=list[ResourceResponse])
def list_resources(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Resource]:
    _accessible_subject(db, subject_id, profile)
    return list(
        db.scalars(select(Resource).where(Resource.subject_id == subject_id).order_by(Resource.created_at.desc())).all()
    )


@router.post("", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
def upload_resource(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    transcribe_audio: Annotated[bool, Form()] = False,
) -> Resource:
    _accessible_subject(db, subject_id, profile)
    file_name, extension = _safe_filename(file.filename)
    content = file.file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MiB limit.")
    if not content:
        raise HTTPException(status_code=422, detail="Empty files are not supported.")
    mime_type = _validate_content(content, extension)
    processed = process_document(file_name, content)
    transcript = None
    audio_duration_seconds = None

    # Automated AI Processing Pipeline:
    # 1. If audio file: automatically transcribe via Gemini to extract study text
    is_audio = extension in TRANSCRIBABLE_EXTENSIONS
    if is_audio or transcribe_audio:
        try:
            audio_duration_seconds = inspect_audio(content, extension)
        except InvalidAudio as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        try:
            transcript = safe_call_ai(gemini.transcribe_audio, content, mime_type, db=db)
        except gemini.GeminiNotConfigured:
            logger.warning("Gemini transcription not configured, storing audio as is.")
        except (gemini.GeminiRateLimited, gemini.GeminiRequestFailed) as ai_err:
            logger.warning("Gemini transcription failed or rate-limited: %s", ai_err)

        if transcript and transcript.transcript:
            processed = process_document(
                f"{PurePosixPath(file_name).stem}.txt",
                transcript.transcript.encode("utf-8"),
            )

    # 2. If document had no text (e.g. scanned PDF/book): let AI extract text directly
    if not processed.chunks and extension == ".pdf":
        try:
            settings = get_settings()
            from app.services.ai_router import resolve_ai_config
            from google import genai
            from google.genai import types

            ai_cfg = resolve_ai_config(
                "document_ai",
                db=db,
                default_model=settings.gemini_model,
                default_key=settings.gemini_api_key,
            )
            if ai_cfg.api_key:
                client = genai.Client(api_key=ai_cfg.api_key, http_options=types.HttpOptions(timeout=30_000))
                resp = client.models.generate_content(
                    model=ai_cfg.model_name,
                    contents=[
                        "Extract and transcribe the educational study text from this document accurately in its original language.",
                        types.Part.from_bytes(data=content, mime_type=mime_type),
                    ],
                )
                if resp.text and resp.text.strip():
                    processed = process_document(
                        f"{PurePosixPath(file_name).stem}.txt",
                        resp.text.encode("utf-8"),
                    )
                client.close()
        except Exception as doc_err:
            logger.warning("Document AI extraction fallback error: %s", doc_err)
    sha256 = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(select(Resource.id).where(Resource.subject_id == subject_id, Resource.sha256 == sha256))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="This file already exists in the subject library.")

    resource_type = ALLOWED_TYPES[extension][1]
    public_id = f"study-platform/{subject_id}/{uuid4().hex}{extension if resource_type == 'raw' else ''}"
    try:
        uploaded = cloudinary_storage.upload_private_asset(
            content, public_id=public_id, resource_type=resource_type
        )
    except cloudinary_storage.StorageNotConfigured:
        raise HTTPException(status_code=503, detail="File storage is not configured.") from None
    except cloudinary_storage.StorageOperationFailed:
        raise HTTPException(status_code=502, detail="File storage could not complete the upload.") from None

    resource = Resource(
        subject_id=subject_id,
        uploaded_by=profile.id,
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=sha256,
        cloudinary_public_id=uploaded["public_id"],
        secure_url=uploaded.get("secure_url", ""),
        transcript_text=transcript.transcript if transcript else None,
        transcript_language=transcript.language if transcript else None,
        transcription_model=get_settings().gemini_model if transcript else None,
        audio_duration_seconds=audio_duration_seconds,
        processing_status=processed.status,
    )
    db.add(resource)
    try:
        db.flush()
        db.add_all(
            ResourceChunk(resource_id=resource.id, chunk_index=index, page_number=page, content=text)
            for index, (page, text) in enumerate(processed.chunks)
        )
        db.commit()
        db.refresh(resource)
    except IntegrityError:
        db.rollback()
        _remove_orphan(public_id, resource_type)
        raise HTTPException(status_code=409, detail="This file already exists in the subject library.") from None
    except SQLAlchemyError:
        db.rollback()
        _remove_orphan(public_id, resource_type)
        raise HTTPException(status_code=503, detail="File metadata could not be saved.") from None
    return resource


@router.get("/{resource_id}/transcript", response_model=TranscriptResponse)
def get_resource_transcript(
    subject_id: UUID,
    resource_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> TranscriptResponse:
    _accessible_subject(db, subject_id, profile)
    resource = db.scalar(select(Resource).where(Resource.id == resource_id, Resource.subject_id == subject_id))
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    if not resource.transcript_text or not resource.transcript_language or not resource.audio_duration_seconds:
        raise HTTPException(status_code=404, detail="A transcript is not available for this resource.")
    return TranscriptResponse(
        resource_id=resource.id,
        language=resource.transcript_language,
        transcript=resource.transcript_text,
        model=resource.transcription_model or "unknown",
        audio_duration_seconds=resource.audio_duration_seconds,
    )


@router.get("/{resource_id}/download", response_model=DownloadResponse)
def get_download_url(
    subject_id: UUID,
    resource_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> DownloadResponse:
    _accessible_subject(db, subject_id, profile)
    resource = db.scalar(select(Resource).where(Resource.id == resource_id, Resource.subject_id == subject_id))
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    extension = PurePosixPath(resource.file_name).suffix.lower()
    resource_type = ALLOWED_TYPES.get(extension, ("", ""))[1]
    try:
        url = cloudinary_storage.create_download_url(
            public_id=resource.cloudinary_public_id,
            extension=extension.lstrip("."),
            resource_type=resource_type,
        )
    except cloudinary_storage.StorageNotConfigured:
        raise HTTPException(status_code=503, detail="File storage is not configured.") from None
    except cloudinary_storage.StorageOperationFailed:
        raise HTTPException(status_code=502, detail="File download link could not be created.") from None
    return DownloadResponse(download_url=url)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(
    subject_id: UUID,
    resource_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    _accessible_subject(db, subject_id, profile)
    resource = db.scalar(select(Resource).where(Resource.id == resource_id, Resource.subject_id == subject_id))
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    if profile.role != "admin" and resource.uploaded_by != profile.id:
        raise HTTPException(status_code=403, detail="Only the uploader or an admin can delete this file.")
    extension = PurePosixPath(resource.file_name).suffix.lower()
    resource_type = ALLOWED_TYPES.get(extension, ("", ""))[1]
    try:
        cloudinary_storage.delete_asset(public_id=resource.cloudinary_public_id, resource_type=resource_type)
    except cloudinary_storage.StorageNotConfigured:
        raise HTTPException(status_code=503, detail="File storage is not configured.") from None
    except cloudinary_storage.StorageOperationFailed:
        raise HTTPException(status_code=502, detail="File storage could not delete the file.") from None
    try:
        db.delete(resource)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="File metadata could not be removed.") from None
