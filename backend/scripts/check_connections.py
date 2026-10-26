"""Run bounded, read-only checks for configured external providers.

Prints provider status only. It never logs credentials, connection URLs, or
exception messages. Gemini performs one tiny generation request.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from urllib.request import urlopen

import cloudinary
import cloudinary.api
from google import genai
from google.genai import types
from sqlalchemy import create_engine, text

from app.core.config import get_settings


def check_supabase() -> None:
    settings = get_settings()
    if not settings.supabase_jwt_jwks_url:
        raise RuntimeError
    with urlopen(settings.supabase_jwt_jwks_url, timeout=10) as response:
        if response.status != 200 or b'"keys"' not in response.read(262_144):
            raise RuntimeError


def check_database() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                raise RuntimeError
    finally:
        engine.dispose()


def check_cloudinary() -> None:
    settings = get_settings()
    if not all((settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret)):
        raise RuntimeError
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    cloudinary.api.usage(timeout=10)


def check_gemini() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=12_000),
    )
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents="Reply OK.",
            config=types.GenerateContentConfig(
                max_output_tokens=64,
                thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            ),
        )
        if not response.text:
            raise RuntimeError
    finally:
        client.close()


def main() -> int:
    checks: tuple[tuple[str, Callable[[], None]], ...] = (
        ("supabase_auth", check_supabase),
        ("database", check_database),
        ("cloudinary", check_cloudinary),
        ("gemini", check_gemini),
    )
    failed = False
    for name, check in checks:
        try:
            check()
            print(f"{name}: connected")
        except Exception:
            failed = True
            print(f"{name}: failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
