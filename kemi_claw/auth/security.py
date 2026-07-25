"""Password hashing (bcrypt), JWT issue/verify, and the role guard."""
import os
import time

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from .models import ROLE_RANK, Role, User

SECRET = os.getenv("KEMI_JWT_SECRET", "change_this_secret")
ALGO = "HS256"
TTL = int(os.getenv("KEMI_JWT_TTL", "3600"))

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p, h)


def make_token(username: str, role: str) -> str:
    payload = {"sub": username, "role": role, "exp": time.time() + TTL}
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def current_user(token: str = Depends(oauth2)) -> User:
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALGO])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    return User(username=data["sub"], role=Role(data["role"]))


def require_role(min_role: Role):
    """Allow only roles equal to or above min_role."""

    def guard(user: User = Depends(current_user)) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
            raise HTTPException(
                status_code=403, detail="insufficient permissions"
            )
        return user

    return guard
