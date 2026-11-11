"""Security utilities: bcrypt password hashing, JWT creation, and token verification."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core import messages
from app.core.config import get_settings
from app.core.constants import TokenType
from app.core.exceptions import UnauthorizedException


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def hash_token(token: str) -> str:
    """Return deterministic SHA-256 hex digest of a raw refresh token for DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_token_payload(
    user_id: int, token_type: TokenType, expires_delta: timedelta
) -> tuple[dict[str, Any], str, datetime]:
    """Construct standard JWT payload with sub, type, jti, iat, and exp."""
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type.value,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    return payload, jti, expires_at


def create_access_token(user_id: int) -> str:
    """Generate a signed short-lived JWT access token."""
    settings = get_settings()
    payload, _, _ = _build_token_payload(
        user_id=user_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Generate a signed refresh token and return (raw_token, jti, expires_at)."""
    settings = get_settings()
    payload, jti, expires_at = _build_token_payload(
        user_id=user_id,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    encoded = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded, jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> tuple[int, str]:
    """Decode and validate JWT signature, expiration, token type, and subject.

    Returns (user_id, jti). Raises UnauthorizedException (401) on any invalid claim.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedException(message=messages.TOKEN_EXPIRED) from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedException(message=messages.TOKEN_INVALID) from exc

    if payload.get("type") != expected_type.value:
        raise UnauthorizedException(message=messages.INVALID_TOKEN_TYPE)

    try:
        raw_sub = payload["sub"]
        if not isinstance(raw_sub, str | int) or isinstance(raw_sub, bool):
            raise ValueError("Invalid subject claim type")
        user_id = int(raw_sub)
        if user_id <= 0:
            raise ValueError("Subject must be positive integer")
        raw_jti = payload["jti"]
        if not isinstance(raw_jti, str) or not raw_jti:
            raise ValueError("Invalid jti claim")
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedException(message=messages.TOKEN_INVALID) from exc

    return user_id, raw_jti

