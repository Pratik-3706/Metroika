"""
Authentication and Role-Based Access Control (RBAC) service.
Uses standard library cryptographic primitives (PBKDF2-HMAC-SHA256 and signed tokens)
for maximum reliability, security, and zero external C-dependency build risks.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session

logger = logging.getLogger(__name__)

# Server-side signing secret (persists per server run or loaded from config)
_SECRET_KEY = getattr(settings, "secret_key", None)
if not _SECRET_KEY or _SECRET_KEY == "YOUR_SECRET_KEY":
    # Fallback to a stable derived key or random secure key
    _SECRET_KEY = hashlib.sha256(b"metroika_legal_metrology_secure_secret_2026").digest()
else:
    _SECRET_KEY = hashlib.sha256(_SECRET_KEY.encode("utf-8")).digest()

# Token lifetime: 7 days
TOKEN_LIFETIME_SECONDS = 7 * 24 * 3600
PBKDF2_ITERATIONS = 100_000

security_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password Hashing & Verification
# ---------------------------------------------------------------------------
def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random salt."""
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return pw_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Constant-time verification of a password against its stored hash."""
    computed_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return hmac.compare_digest(computed_hash, password_hash)


# ---------------------------------------------------------------------------
# Cryptographic Signed Tokens
# ---------------------------------------------------------------------------
def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def create_access_token(username: str, role: str) -> str:
    """Create a tamper-proof cryptographically signed bearer token."""
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64_encode(payload_bytes)

    # Sign with HMAC-SHA256
    sig = hmac.new(_SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64_encode(sig)

    return f"{payload_b64}.{sig_b64}"


def verify_access_token(token: str) -> Optional[Dict]:
    """Verify signature and expiration of a bearer token."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        payload_b64, sig_b64 = parts
        expected_sig = hmac.new(
            _SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256
        ).digest()
        provided_sig = _b64_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("exp", 0) < int(time.time()):
            return None  # Expired

        return payload
    except Exception as e:
        logger.debug(f"Token verification failed: {e}")
        return None


# ---------------------------------------------------------------------------
# FastAPI Dependency Injection
# ---------------------------------------------------------------------------
async def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_session),
):
    """Returns the authenticated user if valid token present, otherwise None."""
    if not auth or not auth.credentials:
        return None

    payload = verify_access_token(auth.credentials)
    if not payload:
        return None

    from app.database import User
    result = await db.execute(select(User).where(User.username == payload.get("sub")))
    user = result.scalar_one_or_none()
    return user


async def get_current_user(
    user = Depends(get_current_user_optional),
):
    """Requires an authenticated user, returning HTTP 401 if missing."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(allowed_roles: List[str]):
    """
    Enforces that the current authenticated user has one of the allowed roles.
    Raises HTTP 403 Forbidden if the user does not possess sufficient privileges.
    """
    async def role_checker(user = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: this action requires role {allowed_roles} (current role: {user.role}).",
            )
        return user

    return role_checker
