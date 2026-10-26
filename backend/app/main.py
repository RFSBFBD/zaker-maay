from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.subjects import router as subjects_router
from app.api.routes.study_sessions import router as study_sessions_router
from app.api.routes.resources import router as resources_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.quizzes import router as quizzes_router
from app.api.routes.progress import router as progress_router
from app.api.routes.youtube_links import router as youtube_links_router
from app.api.routes.study_artifacts import router as study_artifacts_router
from app.api.routes.admin import router as admin_router
from app.api.routes.subject_chat import router as subject_chat_router
from app.api.routes.image_generation import router as image_generation_router
from app.api.routes.inquiries import router as inquiries_router
from app.api.routes.skills import router as skills_router
from app.core.middleware import UploadBodyLimitMiddleware
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(UploadBodyLimitMiddleware)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(subjects_router)
app.include_router(study_sessions_router)
app.include_router(resources_router)
app.include_router(assistant_router)
app.include_router(quizzes_router)
app.include_router(progress_router)
app.include_router(youtube_links_router)
app.include_router(study_artifacts_router)
app.include_router(admin_router)
app.include_router(subject_chat_router)
app.include_router(image_generation_router)
app.include_router(inquiries_router)
app.include_router(skills_router)


@app.get("/api/v1/meta", tags=["meta"])
def metadata() -> dict[str, str]:
    return {"name": settings.app_name, "api_version": "v1"}
