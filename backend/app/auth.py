import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

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


async def get_operator_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise _unauthorized()
    try:
        claims = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise _unauthorized()
    if "church_id" not in claims:
        raise _unauthorized()
    return claims


async def get_current_operator(claims: dict = Depends(get_operator_claims)) -> int:
    return int(claims["church_id"])
