from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Resource, ResourceChunk, Subject, UserProfile
from app.services.retrieval import retrieve_for_subject, tokenize


@pytest.fixture
def retrieval_db() -> Generator[tuple[Session, Subject, Subject], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    admin = UserProfile(id=uuid4(), role="admin")
    db.add(admin)
    db.flush()
    physics = Subject(name="Physics", created_by=admin.id)
    biology = Subject(name="Biology", created_by=admin.id)
    db.add_all([physics, biology])
    db.flush()
    physics_resource = Resource(
        subject_id=physics.id,
        uploaded_by=admin.id,
        file_name="physics.txt",
        mime_type="text/plain",
        size_bytes=10,
        sha256="1" * 64,
        cloudinary_public_id="physics/one.txt",
        secure_url="https://private.invalid/one",
        processing_status="ready",
    )
    biology_resource = Resource(
        subject_id=biology.id,
        uploaded_by=admin.id,
        file_name="biology.txt",
        mime_type="text/plain",
        size_bytes=10,
        sha256="2" * 64,
        cloudinary_public_id="biology/two.txt",
        secure_url="https://private.invalid/two",
        processing_status="ready",
    )
    db.add_all([physics_resource, biology_resource])
    db.flush()
    db.add_all(
        [
            ResourceChunk(resource_id=physics_resource.id, chunk_index=0, content="Magnetism is the study of magnetic fields."),
            ResourceChunk(resource_id=biology_resource.id, chunk_index=0, content="Photosynthesis converts light into chemical energy."),
        ]
    )
    db.commit()
    try:
        yield db, physics, biology
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_arabic_normalization_matches_alif_variants() -> None:
    assert tokenize("إِنَّ آليات القوى") == ["ان", "اليات", "القوي"]


def test_retrieval_is_scoped_to_the_requested_subject(
    retrieval_db: tuple[Session, Subject, Subject],
) -> None:
    db, physics, biology = retrieval_db

    physics_result = retrieve_for_subject(db, subject_id=physics.id, query="magnetic fields")
    unrelated = retrieve_for_subject(db, subject_id=physics.id, query="photosynthesis")
    biology_result = retrieve_for_subject(db, subject_id=biology.id, query="photosynthesis")

    assert [item.file_name for item in physics_result] == ["physics.txt"]
    assert unrelated == []
    assert [item.file_name for item in biology_result] == ["biology.txt"]
