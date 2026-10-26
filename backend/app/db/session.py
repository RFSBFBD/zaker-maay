from collections.abc import Generator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache(maxsize=4)
def get_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


def get_session_factory() -> sessionmaker[Session]:
    database_url = get_settings().database_url
    if not database_url:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    return sessionmaker(bind=get_engine(database_url), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    with factory() as session:
        yield session
