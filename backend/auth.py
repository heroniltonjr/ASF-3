"""Auth real: scrypt para senhas, sessões em DB, cookie httpOnly, RBAC."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import db

SESSION_COOKIE = "formula_session"
SESSION_TTL_DAYS = 7

# PBKDF2-HMAC-SHA256 — sempre disponível no stdlib, adequado para protótipo.
# OWASP 2023 recomenda >= 600_000 iterações para SHA-256.
_PBKDF2_ITERATIONS = 600_000
_PBKDF2_DKLEN = 32
_SALT_LEN = 16


def hash_password(plain: str) -> str:
    salt = os.urandom(_SALT_LEN)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, _PBKDF2_ITERATIONS, _PBKDF2_DKLEN,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        expected = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"),
            bytes.fromhex(salt_hex), int(iterations), len(expected),
        )
        return hmac.compare_digest(expected, candidate)
    except (ValueError, AttributeError):
        return False


def create_session(user_id: int) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at.isoformat()),
        )
    return token, expires_at


def get_user_by_token(token: str) -> Optional[dict]:
    if not token:
        return None
    with db.tx() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.name, u.role, u.tenant_id, u.store_id, s.expires_at
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(row["expires_at"])
    except ValueError:
        return None
    if expires < datetime.now(timezone.utc):
        revoke_session(token)
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "tenant_id": row["tenant_id"],
        "store_id": row["store_id"],
    }


def revoke_session(token: str) -> None:
    if not token:
        return
    with db.tx() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))


def purge_expired() -> int:
    with db.tx() as conn:
        cur = conn.execute(
            "DELETE FROM auth_sessions WHERE expires_at < ?",
            (datetime.now(timezone.utc).isoformat(),),
        )
        return cur.rowcount


def parse_cookie(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == SESSION_COOKIE:
            return value
    return None


def session_cookie(token: str, expires: datetime) -> str:
    exp = expires.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return (
        f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Expires={exp}"
    )


def clear_cookie() -> str:
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
