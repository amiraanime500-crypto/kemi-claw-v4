"""Roles and user models."""
from enum import Enum

from pydantic import BaseModel


class Role(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


# Hierarchical rank: each role inherits the ones below it
ROLE_RANK = {Role.VIEWER: 1, Role.OPERATOR: 2, Role.ADMIN: 3}


class User(BaseModel):
    username: str
    role: Role


class UserCreate(BaseModel):
    username: str
    password: str
    role: Role = Role.VIEWER


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
