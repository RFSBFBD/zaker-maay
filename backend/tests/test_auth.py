from datetime import datetime, timedelta, timezone
from collections.abc import Generator
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.exceptions import InvalidAudienceError, InvalidIssuerError, InvalidSignatureError
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.core import auth
from app.core.auth import UserIdentity, verify_access_token
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

ISSUER = "https://study.example.test/auth/v1"
AUDIENCE = "authenticated"
USER_ID = uuid4()


class StaticJwksClient:
    def __init__(self, key: object) -> None:
        self.key = key

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        return SimpleNamespace(key=self.key)


@pytest.fixture
def rsa_keys() -> tuple[object, object]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        supabase_jwt_issuer=ISSUER,
        supabase_jwt_audience=AUDIENCE,
    )


def make_token(private_key: object, **overrides: object) -> str:
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(USER_ID),
        "role": "authenticated",
        "email": "student@example.test",
        "user_metadata": {"role": "admin"},
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=3),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def test_valid_token_returns_identity_and_ignores_user_metadata(rsa_keys: tuple[object, object]) -> None:
    private_key, public_key = rsa_keys
    identity = verify_access_token(make_token(private_key), make_settings(), StaticJwksClient(public_key))

    assert identity == UserIdentity(id=USER_ID, email="student@example.test")
    assert not hasattr(identity, "role")


@pytest.mark.parametrize(
    ("claim", "value", "error"),
    [
        ("iss", "https://attacker.example.test", InvalidIssuerError),
        ("aud", "another-service", InvalidAudienceError),
        ("role", "service_role", jwt.InvalidTokenError),
    ],
)
def test_rejects_untrusted_token_claims(
    rsa_keys: tuple[object, object], claim: str, value: str, error: type[Exception]
) -> None:
    private_key, public_key = rsa_keys
    token = make_token(private_key, **{claim: value})

    with pytest.raises(error):
        verify_access_token(token, make_settings(), StaticJwksClient(public_key))


def test_rejects_expired_token(rsa_keys: tuple[object, object]) -> None:
    private_key, public_key = rsa_keys
    token = make_token(private_key, exp=datetime.now(timezone.utc) - timedelta(minutes=1))

    with pytest.raises(jwt.ExpiredSignatureError):
        verify_access_token(token, make_settings(), StaticJwksClient(public_key))


def test_rejects_invalid_signature(rsa_keys: tuple[object, object]) -> None:
    signing_key, _ = rsa_keys
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(InvalidSignatureError):
        verify_access_token(make_token(other_key), make_settings(), StaticJwksClient(signing_key.public_key()))


def test_protected_endpoint_rejects_missing_bearer_token() -> None:
    response = TestClient(app).get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_protected_endpoint_accepts_verified_user_token(
    rsa_keys: tuple[object, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, public_key = rsa_keys
    test_settings = Settings(
        _env_file=None,
        supabase_jwt_issuer=ISSUER,
        supabase_jwt_audience=AUDIENCE,
        supabase_jwt_jwks_url=f"{ISSUER}/.well-known/jwks.json",
    )
    monkeypatch.setattr(auth, "get_jwks_client", lambda _: StaticJwksClient(public_key))
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def get_test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[auth.get_settings] = lambda: test_settings
    app.dependency_overrides[get_db] = get_test_db
    try:
        response = TestClient(app).get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {make_token(private_key)}"},
        )
    finally:
        app.dependency_overrides.pop(auth.get_settings, None)
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"id": str(USER_ID), "email": "student@example.test", "role": "student"}
