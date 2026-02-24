from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.models.enums import UserRole
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class TokenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _build_token(data: dict[str, Any], token_type: str, expires_delta: timedelta) -> str:
    now_utc = datetime.now(timezone.utc)
    payload = data.copy()
    payload.update(
        {
            "type": token_type,
            "iat": int(now_utc.timestamp()),
            "exp": int((now_utc + expires_delta).timestamp()),
        }
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(data: dict[str, Any]) -> str:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    return _build_token(data=data, token_type="access", expires_delta=expires_delta)


def create_refresh_token(data: dict[str, Any]) -> str:
    expires_delta = timedelta(minutes=settings.refresh_token_expire_minutes)
    return _build_token(data=data, token_type="refresh", expires_delta=expires_delta)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise TokenError() from exc

    subject = payload.get("sub")
    role = payload.get("role")
    token_type = payload.get("type")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")

    if not subject or not role or token_type not in {"access", "refresh"}:
        raise TokenError()
    if not isinstance(issued_at, int) or not isinstance(expires_at, int):
        raise TokenError()

    return payload


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db_session: AsyncSession = Depends(get_db_session),
) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise TokenError()

    try:
        user_id = UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise TokenError() from exc

    result = await db_session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise TokenError()

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


async def require_faculty(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.FACULTY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


async def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user
