"""
Authentication router — login, user profile, and role verification.
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from app.database import User, get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    full_name: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_session)):
    """Authenticate user with username and password, returning signed Bearer token."""
    username = req.username.strip()
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash, user.salt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(username=user.username, role=user.role)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(
            id=user.id,
            username=user.username,
            role=user.role,
            full_name=user.full_name,
        ),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return profile and permissions for currently authenticated user."""
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        full_name=current_user.full_name,
    )


@router.get("/roles")
async def get_roles_info():
    """Returns available roles and description of their capabilities."""
    return {
        "roles": [
            {
                "role": "inspector",
                "label": "Legal Metrology Enforcement Officer",
                "description": "Full access: statewide analytics, statutory Section 36 penalties, Show Cause Notices, product deletion, cache clearance.",
            },
            {
                "role": "merchant",
                "label": "Brand / Packaging Compliance Manager",
                "description": "Pre-market validation: scan packaging, check compliance score, view detailed rules and suggestions.",
            },
            {
                "role": "public",
                "label": "Consumer / General User",
                "description": "Public audit: scan commodities and check fair trade declarations.",
            },
        ]
    }
