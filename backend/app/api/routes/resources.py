from __future__ import annotations

import hashlib
import io
import logging
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID, uuid4

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
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
from app.services.ai_router import resolve_ai_config, safe_call_ai
from app.services.audio_processing import InvalidAudio, TRANSCRIBABLE_EXTENSIONS, inspect_audio
from app.services.document_processing import SUPPORTED_TEXT_EXTENSIONS, process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/subjects/{subject_id}/resources", tags=["resources"])

MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MiB
ALLOWED_TYPES: dict[str, tuple[str, str]] = {
    ".pdf": ("application/pdf", "raw"),
    ".txt": ("text/plain", "raw"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "raw"),
    ".mp3": ("audio/mpeg", "video"),
    ".wav": ("audio/wav", "video"),
    ".m4a": ("audio/mp4", "video"),
    ".webm": ("audio/webm", "video"),
    ".ogg": ("audio/ogg", "video"),
    ".aac": ("audio/aac", "video"),
    ".flac": ("audio/flac", "video"),
    ".mp4": ("audio/mp4", "video"),
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


class TranscribeGeminiFileRequest(BaseModel):
    gemini_file_name: str
    file_name: str
    size_bytes: int
    mime_type: str = "audio/mp4"


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


@router.get("/upload-params", response_model=dict)
def get_cloudinary_upload_params(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    file_name: str = Query(...),
    resource_type: str = Query(...),
) -> dict:
    """Return signed Cloudinary upload parameters so the browser can upload directly."""
    _accessible_subject(db, subject_id, profile)
    from cloudinary import utils as cu

    settings = get_settings()
    if not all((settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret)):
        raise HTTPException(status_code=503, detail="تخزين السحابة غير مهيأ.")

    public_id = f"study-platform/{subject_id}/{uuid4().hex}{PurePosixPath(file_name).suffix}"
    params_to_sign = {
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "public_id": public_id,
    }
    signature = cu.api_sign_request(params_to_sign, settings.cloudinary_api_secret)
    return {
        "cloud_name": settings.cloudinary_cloud_name,
        "api_key": settings.cloudinary_api_key,
        "timestamp": str(params_to_sign["timestamp"]),
        "public_id": public_id,
        "resource_type": resource_type,
        "signature": signature,
    }


@router.post("/gemini-upload-url", response_model=dict)
def get_gemini_upload_url(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    file_name: str = Query(...),
    file_size: int = Query(...),
    mime_type: str = Query("audio/mp4"),
) -> dict:
    """Generate a resumable Gemini upload URL so the browser can upload files directly to the AI agent."""
    _accessible_subject(db, subject_id, profile)
    settings = get_settings()
    ai_cfg = resolve_ai_config(
        "audio_transcription",
        db=db,
        default_model=settings.gemini_model,
        default_key=settings.gemini_api_key,
    )
    if not ai_cfg.api_key:
        raise HTTPException(status_code=503, detail="خدمة الذكاء الاصطناعي غير مهيأة.")

    _, extension = _safe_filename(file_name)
    allowed_extensions = TRANSCRIBABLE_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
    if extension not in allowed_extensions:
        raise HTTPException(status_code=422, detail="نوع الملف غير مدعوم للمعالجة المباشرة.")

    if file_size > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز الحد الأقصى المسموح به (100 ميغابايت).")

    res = requests.post(
        "https://generativelanguage.googleapis.com/upload/v1beta/files",
        headers={
            "x-goog-api-key": ai_cfg.api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        },
        json={"file": {"display_name": file_name}},
        timeout=15,
    )
    if res.status_code != 200:
        logger.error("Failed to initiate Gemini upload: %s %s", res.status_code, res.text)
        raise HTTPException(status_code=502, detail="تعذر الاتصال بخدمة الذكاء الاصطناعي.")

    upload_url = res.headers.get("x-goog-upload-url")
    if not upload_url:
        raise HTTPException(status_code=502, detail="تعذر الحصول على رابط رفع الملف.")

    return {"upload_url": upload_url}


@router.post("/process-audio-transcript", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
def process_audio_transcript(
    subject_id: UUID,
    payload: TranscribeGeminiFileRequest,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> Resource:
    """Process an audio or large document file uploaded directly to Gemini and index it as study material."""
    _accessible_subject(db, subject_id, profile)
    _, extension = _safe_filename(payload.file_name)
    is_audio = extension in TRANSCRIBABLE_EXTENSIONS
    is_document = extension in SUPPORTED_TEXT_EXTENSIONS
    if not is_audio and not is_document:
        raise HTTPException(status_code=422, detail="نوع الملف غير مدعوم للمعالجة المباشرة.")

    transcript_text: str | None = None
    transcript_language: str | None = None
    processed_content: bytes = b""

    if is_audio:
        try:
            transcript = gemini.transcribe_gemini_file(
                payload.gemini_file_name,
                payload.mime_type,
                db=db,
            )
            transcript_text = transcript.transcript
            transcript_language = transcript.language
            processed_content = transcript_text.encode("utf-8")
        except gemini.GeminiNotConfigured:
            raise HTTPException(status_code=503, detail="خدمة التفريغ الذكي غير مهيأة.")
        except (gemini.GeminiRateLimited, gemini.GeminiRequestFailed) as exc:
            logger.exception("Gemini audio transcription failed: %s", exc)
            raise HTTPException(status_code=502, detail="تعذر تفريغ الملف الصوتي بواسطة الذكاء الاصطناعي.")
    else:
        try:
            extracted_text = gemini.extract_gemini_document(
                payload.gemini_file_name,
                payload.mime_type,
                db=db,
            )
            transcript_text = extracted_text
            processed_content = extracted_text.encode("utf-8")
        except gemini.GeminiNotConfigured:
            raise HTTPException(status_code=503, detail="خدمة معالجة المستندات الذكية غير مهيأة.")
        except (gemini.GeminiRateLimited, gemini.GeminiRequestFailed) as exc:
            logger.exception("Gemini document extraction failed: %s", exc)
            raise HTTPException(status_code=502, detail="تعذر استخراج محتوى الكتاب/المستند بواسطة الذكاء الاصطناعي.")

    # Process text into chunks for the AI Agent
    processed = process_document(
        f"{PurePosixPath(payload.file_name).stem}.txt",
        processed_content,
    )

    sha256 = hashlib.sha256(f"{payload.file_name}:{uuid4().hex}".encode()).hexdigest()
    resource = Resource(
        subject_id=subject_id,
        uploaded_by=profile.id,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        sha256=sha256,
        cloudinary_public_id=f"gemini-resource/{uuid4().hex}" if not is_audio else f"audio-transcript/{uuid4().hex}",
        secure_url="internal://gemini-resource" if not is_audio else "internal://audio-transcript",
        transcript_text=transcript_text,
        transcript_language=transcript_language,
        transcription_model="gemini",
        audio_duration_seconds=None,
        processing_status=processed.status,
    )
    db.add(resource)
    db.flush()

    for index, (page, chunk_text) in enumerate(processed.chunks):
        db.add(
            ResourceChunk(
                resource_id=resource.id,
                chunk_index=index,
                page_number=page,
                content=chunk_text,
            )
        )
    db.commit()
    db.refresh(resource)
    return resource


@router.post("/upload-direct", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_direct_resource(
    subject_id: UUID,
    file: UploadFile = File(...),
    profile: Annotated[UserProfile, Depends(get_current_profile)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Resource:
    """Directly stream and process an audio or document file server-to-server, eliminating browser CORS."""
    _accessible_subject(db, subject_id, profile)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="الملف المرفوع فارغ.")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز الحد الأقصى المسموح به (100 ميغابايت).")

    file_name = file.filename or "uploaded_resource"
    stem, extension = _safe_filename(file_name)
    if extension not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="نوع الملف غير مدعوم.")

    mime_type, _ = ALLOWED_TYPES[extension]
    is_audio = extension in TRANSCRIBABLE_EXTENSIONS

    transcript_text: str | None = None
    transcript_language: str | None = None
    processed_content: bytes = file_bytes

    if is_audio:
        try:
            transcript = gemini.transcribe_audio(content=file_bytes, mime_type=mime_type, db=db)
            transcript_text = transcript.transcript
            transcript_language = transcript.language
            processed_content = transcript_text.encode("utf-8")
        except gemini.GeminiNotConfigured:
            raise HTTPException(status_code=503, detail="خدمة التفريغ الصوتي الذكي غير مهيأة.")
        except gemini.GeminiRateLimited:
            raise HTTPException(status_code=429, detail="تم تجاوز حد طلبات الذكاء الاصطناعي مؤقتاً.")
        except Exception as exc:
            logger.exception("Audio transcription failed: %s", exc)
            raise HTTPException(status_code=502, detail="تعذر تفريغ التسجيل الصوتي بواسطة الذكاء الاصطناعي.")

    # Process text / chunks for the AI Agent
    doc_name = f"{stem}.txt" if is_audio else file_name
    processed = process_document(doc_name, processed_content)

    sha256 = hashlib.sha256(f"{file_name}:{uuid4().hex}".encode()).hexdigest()
    resource = Resource(
        subject_id=subject_id,
        uploaded_by=profile.id,
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=len(file_bytes),
        sha256=sha256,
        cloudinary_public_id=f"direct-resource/{uuid4().hex}",
        secure_url="internal://direct-resource" if not is_audio else "internal://audio-transcript",
        transcript_text=transcript_text,
        transcript_language=transcript_language,
        transcription_model="gemini" if is_audio else None,
        audio_duration_seconds=None,
        processing_status=processed.status,
    )
    db.add(resource)
    db.flush()

    for index, (page, chunk_text) in enumerate(processed.chunks):
        db.add(
            ResourceChunk(
                resource_id=resource.id,
                chunk_index=index,
                page_number=page,
                content=chunk_text,
            )
        )
    db.commit()
    db.refresh(resource)
    return resource


def _fetch_file_from_cloudinary(public_id: str, resource_type: str, secure_url: str | None = None) -> tuple[bytes, str]:
    """Download a file from Cloudinary by its public_id or secure_url for local processing.

    Returns (content_bytes, mime_type_from_header).
    """
    settings = get_settings()
    if secure_url and secure_url.startswith("http"):
        url = secure_url
    else:
        from cloudinary import utils as cu
        url = cu.cloudinary_url(
            public_id,
            resource_type=resource_type,
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            format="",
        )[0]
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    content = b""
    mime_type = "application/octet-stream"
    with tempfile.TemporaryFile() as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)
                content += chunk
                if len(content) > MAX_FILE_BYTES + 1:
                    raise HTTPException(status_code=413, detail="File exceeds the 100 MiB limit.")
        tmp.seek(0)
        headers = dict(resp.headers)
        mime_type = headers.get("content-type", "application/octet-stream").split(";")[0]
    return content, mime_type


@router.post("", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
def upload_resource(
    subject_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
    cloudinary_public_id: Annotated[str, Form(...)],
    cloudinary_secure_url: Annotated[str, Form(...)],
    file_name: Annotated[str, Form(...)],
    size_bytes: Annotated[int, Form(...)],
    transcribe_audio: Annotated[bool, Form()] = False,
) -> Resource:
    """Create a Resource record from an already-uploaded Cloudinary file.

    The browser uploads the file directly to Cloudinary first, then posts only
    metadata here — no file bytes traverse this endpoint.
    """
    _accessible_subject(db, subject_id, profile)
    _, extension = _safe_filename(file_name)
    resource_type = ALLOWED_TYPES[extension][1]

    # Re-download from Cloudinary so we can compute sha256 and process content
    try:
        try:
            content, mime_type = _fetch_file_from_cloudinary(cloudinary_public_id, resource_type, cloudinary_secure_url)
        except TypeError:
            content, mime_type = _fetch_file_from_cloudinary(cloudinary_public_id, resource_type)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch uploaded file from Cloudinary: %s", exc)
        raise HTTPException(status_code=502, detail="تعذر تنزيل الملف المرفوع للمعالجة.") from None

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 100 MiB limit.")
    if not content:
        raise HTTPException(status_code=422, detail="Empty files are not supported.")
    mime_type = _validate_content(content, extension)
    processed = process_document(file_name, content)
    transcript = None
    audio_duration_seconds = None

    # Audio transcription pipeline: only transcribe when explicitly requested
    is_audio = extension in TRANSCRIBABLE_EXTENSIONS
    if is_audio and transcribe_audio:
        try:
            audio_duration_seconds = inspect_audio(content, extension)
        except InvalidAudio as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        try:
            transcript = safe_call_ai(gemini.transcribe_audio, content, mime_type, db=db)
        except gemini.GeminiNotConfigured:
            logger.warning("Gemini transcription not configured, storing audio as is.")
        except (gemini.GeminiRateLimited, gemini.GeminiRequestFailed) as ai_err:
            logger.error("Gemini transcription failed for %s: %s", file_name, ai_err)
            raise HTTPException(status_code=502, detail="تعذر معالجة الملف الصوتي — بقي الملف على جهازك.") from None
        except Exception as exc:
            logger.exception("Unexpected transcription error for %s: %s", file_name, exc)
            raise HTTPException(status_code=502, detail="تعذر معالجة الملف الصوتي. حاول مجددًا.") from None

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

    resource = Resource(
        subject_id=subject_id,
        uploaded_by=profile.id,
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=sha256,
        cloudinary_public_id=cloudinary_public_id,
        secure_url=cloudinary_secure_url,
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
        _remove_orphan(cloudinary_public_id, resource_type)
        raise HTTPException(status_code=409, detail="This file already exists in the subject library.") from None
    except SQLAlchemyError:
        db.rollback()
        _remove_orphan(cloudinary_public_id, resource_type)
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


@router.post("/{resource_id}/transcribe", response_model=ResourceResponse)
def trigger_resource_transcription(
    subject_id: UUID,
    resource_id: UUID,
    profile: Annotated[UserProfile, Depends(get_current_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> Resource:
    """Manually transcribe an uploaded audio lecture so the AI Agent can read, search, and reference it."""
    _accessible_subject(db, subject_id, profile)
    resource = db.scalar(select(Resource).where(Resource.id == resource_id, Resource.subject_id == subject_id))
    if resource is None:
        raise HTTPException(status_code=404, detail="الملف غير موجود.")

    _, extension = _safe_filename(resource.file_name)
    if extension not in TRANSCRIBABLE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="هذا الملف ليس تسجيلاً صوتياً قابلاً للتفريغ.")

    resource_type = ALLOWED_TYPES[extension][1]
    try:
        try:
            content, mime_type = _fetch_file_from_cloudinary(resource.cloudinary_public_id, resource_type, resource.secure_url)
        except TypeError:
            content, mime_type = _fetch_file_from_cloudinary(resource.cloudinary_public_id, resource_type)
    except Exception as exc:
        logger.exception("Failed to fetch audio for transcription: %s", exc)
        raise HTTPException(status_code=502, detail="تعذر تنزيل الملف الصوتي من السحابة.") from None

    try:
        duration = inspect_audio(content, extension)
    except InvalidAudio as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    try:
        transcript = safe_call_ai(gemini.transcribe_audio, content, mime_type, db=db)
    except gemini.GeminiNotConfigured:
        raise HTTPException(status_code=503, detail="خدمة التفريغ الصوتي بالذكاء الاصطناعي غير مهيأة.") from None
    except gemini.GeminiRateLimited:
        raise HTTPException(status_code=429, detail="وصلت خدمة التفريغ الصوتي إلى حد الطلبات مؤقتاً. حاول لاحقاً.") from None
    except Exception as exc:
        logger.exception("Audio transcription failed for %s: %s", resource.file_name, exc)
        raise HTTPException(status_code=502, detail="تعذر معالجة وتفريغ الملف الصوتي حالياً.") from None

    if not transcript or not transcript.transcript.strip():
        raise HTTPException(status_code=502, detail="لم يتم استخراج أي نص مسموع من التسجيل الصوتي.")

    processed = process_document(
        f"{PurePosixPath(resource.file_name).stem}.txt",
        transcript.transcript.encode("utf-8"),
    )

    resource.transcript_text = transcript.transcript.strip()
    resource.transcript_language = transcript.language.strip()
    resource.transcription_model = get_settings().gemini_model
    resource.audio_duration_seconds = duration
    resource.processing_status = processed.status

    from sqlalchemy import delete
    db.execute(delete(ResourceChunk).where(ResourceChunk.resource_id == resource.id))
    db.add_all(
        ResourceChunk(resource_id=resource.id, chunk_index=index, page_number=page, content=text)
        for index, (page, text) in enumerate(processed.chunks)
    )
    db.commit()
    db.refresh(resource)
    return resource


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
    if resource.cloudinary_public_id.startswith(("audio-transcript/", "gemini-resource/")) or resource.secure_url.startswith("internal://"):
        import urllib.parse
        encoded = urllib.parse.quote(resource.transcript_text or "")
        return DownloadResponse(download_url=f"data:text/plain;charset=utf-8,{encoded}")

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
    if not resource.cloudinary_public_id.startswith("audio-transcript/"):
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
