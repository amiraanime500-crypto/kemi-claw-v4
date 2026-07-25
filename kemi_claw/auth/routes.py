"""Routes: login and user management (admin only)."""
from fastapi import APIRouter, Depends, HTTPException

from .models import LoginRequest, Role, TokenResponse, User, UserCreate
from .security import (
    hash_password,
    make_token,
    require_role,
    verify_password,
)
from .store import UserStore

router = APIRouter(prefix="/auth", tags=["auth"])
store = UserStore()


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    u = store.get(req.username)
    if not u or not verify_password(req.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="bad credentials")
    token = make_token(u["username"], u["role"])
    return TokenResponse(access_token=token, role=Role(u["role"]))


@router.post("/users", dependencies=[Depends(require_role(Role.ADMIN))])
async def create_user(body: UserCreate):
    if store.get(body.username):
        raise HTTPException(status_code=409, detail="user exists")
    store.create(body.username, hash_password(body.password), body.role)
    return {"created": body.username, "role": body.role}


@router.get("/users", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_users():
    return store.list_users()


@router.delete(
    "/users/{username}", dependencies=[Depends(require_role(Role.ADMIN))]
)
async def delete_user(username: str):
    store.delete(username)
    return {"deleted": username}


@router.get("/me", response_model=User)
async def me(user: User = Depends(require_role(Role.VIEWER))):
    return user
