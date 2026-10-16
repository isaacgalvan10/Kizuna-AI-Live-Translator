import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or "kizuna-dev-secret-change-in-production"
ALGORITHM = "HS256"
TOKEN_LIFETIME_HOURS = 12

bearer_scheme = HTTPBearer(auto_error=False)


def _truncated_password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_truncated_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_truncated_password_bytes(password), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_operator_token(email: str, church_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "church_id": church_id,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_LIFETIME_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Invalid or missing operator token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def operator_claims_from_token(token: str | None) -> dict | None:
    """Decodes an operator JWT, returning its claims or None when unusable.

    Used where raising an HTTPException is not an option — notably the WebSocket
    handshake, where browsers cannot send an Authorization header and the token
    arrives as a query parameter instead.
    """
    if not token:
        return None
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if "church_id" not in claims:
        return None
    return claims


async def get_operator_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    claims = operator_claims_from_token(
        credentials.credentials if credentials is not None else None
    )
    if claims is None:
        raise _unauthorized()
    return claims


async def get_current_operator(claims: dict = Depends(get_operator_claims)) -> int:
    return int(claims["church_id"])
