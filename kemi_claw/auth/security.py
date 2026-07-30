"""Password hashing (bcrypt), JWT issue/verify, and the role guard."""
import os
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .models import ROLE_RANK, Role, User

SECRET = os.getenv("KEMI_JWT_SECRET", "")
ALGO = "HS256"
TTL = int(os.getenv("KEMI_JWT_TTL", "3600"))

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(p: str) -> str:
    encoded = p.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("password must not exceed 72 UTF-8 bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("ascii"))
    except (ValueError, TypeError):
        return False


def make_token(username: str, role: str) -> str:
    if len(SECRET) < 24:
        raise RuntimeError("KEMI_JWT_SECRET must contain at least 24 characters")
    payload = {"sub": username, "role": role, "exp": time.time() + TTL}
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def current_user(token: str = Depends(oauth2)) -> User:
    if len(SECRET) < 24:
        raise HTTPException(status_code=503, detail="JWT signing secret is not configured")
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALGO])
        username = data["sub"]
        role = Role(data["role"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    from .store import UserStore
    store = UserStore()
    try:
        stored = store.get(username)
    finally:
        store.conn.close()
    if not stored or stored["role"] != role.value:
        raise HTTPException(status_code=401, detail="user is inactive or role changed")
    return User(username=username, role=role)


def require_role(min_role: Role):
    """Allow only roles equal to or above min_role."""

    def guard(user: User = Depends(current_user)) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
            raise HTTPException(
                status_code=403, detail="insufficient permissions"
            )
        return user

    return guard
