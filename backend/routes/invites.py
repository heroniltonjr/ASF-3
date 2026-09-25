"""Onboarding self-service: convite → aceitação → criação de user + (opcional) loja."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from .. import auth, db
from ..deps import require_roles
from ..settings import settings

router = APIRouter()
_ADMIN = require_roles("master", "shopping")

INVITE_TTL_DAYS = 7
MIN_PASSWORD_LEN = 8


@router.post("/api/invites", status_code=201)
def create_invite(payload: dict, user: dict = Depends(_ADMIN)):
    email = (payload.get("email") or "").strip().lower()
    role = payload.get("role") or "lojista"
    if not email or "@" not in email:
        raise HTTPException(400, "Email inválido")
    if role not in ("lojista", "shopping"):
        raise HTTPException(400, "role deve ser 'lojista' ou 'shopping'")

    tenant_id = payload.get("tenant_id") or user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "tenant_id obrigatório")

    store_id = payload.get("store_id")
    new_store_name = (payload.get("new_store_name") or "").strip() or None
    new_store_plan = (payload.get("new_store_plan") or "Start").strip()
    if role == "lojista" and not (store_id or new_store_name):
        raise HTTPException(400, "Informe store_id OU new_store_name")

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat()

    with db.tx() as conn:
        # Checa email já existente
        exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            raise HTTPException(409, "Já existe um usuário com este email")
        conn.execute(
            """
            INSERT INTO invites
              (token, email, role, tenant_id, store_id, new_store_name, new_store_plan,
               invited_by_user_id, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (token, email, role, tenant_id, store_id, new_store_name, new_store_plan,
             user["id"], expires_at),
        )

    return {
        "token": token,
        "url": f"{settings.public_base_url.rstrip('/')}/onboard?token={token}",
        "expires_at": expires_at,
    }


def _load_active_invite(conn, token: str) -> dict:
    row = conn.execute(
        "SELECT * FROM invites WHERE token = ?",
        (token,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Convite inválido")
    if row["used_at"]:
        raise HTTPException(410, "Convite já utilizado")
    exp_val = row["expires_at"]
    if isinstance(exp_val, datetime):
        exp = exp_val if exp_val.tzinfo else exp_val.replace(tzinfo=timezone.utc)
    elif isinstance(exp_val, str):
        try:
            exp = datetime.fromisoformat(exp_val.replace("Z", "+00:00"))
            if not exp.tzinfo:
                exp = exp.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise HTTPException(410, "Convite com expiração inválida") from exc
    else:
        raise HTTPException(410, "Convite com expiração inválida")
    if exp < datetime.now(timezone.utc):
        raise HTTPException(410, "Convite expirado")
    return dict(row)


@router.get("/api/invites/{token}")
def verify_invite(token: str):
    with db.tx() as conn:
        inv = _load_active_invite(conn, token)
    return {
        "email": inv["email"],
        "role": inv["role"],
        "store_id": inv["store_id"],
        "new_store_name": inv["new_store_name"],
        "expires_at": inv["expires_at"],
    }


@router.post("/api/invites/{token}/accept")
def accept_invite(token: str, payload: dict, response: Response):
    name = (payload.get("name") or "").strip()
    password = payload.get("password") or ""
    if not name:
        raise HTTPException(400, "Informe o nome")
    if len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(400, f"Senha deve ter ao menos {MIN_PASSWORD_LEN} caracteres")

    with db.tx() as conn:
        inv = _load_active_invite(conn, token)
        existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (inv["email"],)).fetchone()
        if existing:
            raise HTTPException(409, "Já existe um usuário com este email")

        store_id = inv["store_id"]
        if not store_id and inv["new_store_name"]:
            cur = conn.execute(
                """
                INSERT INTO stores (tenant_id, name, type, plan, status)
                VALUES (?, ?, 'Lojista', ?, 'Ativo')
                """,
                (inv["tenant_id"], inv["new_store_name"], inv["new_store_plan"] or "Start"),
            )
            store_id = cur.lastrowid

        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, name, role, tenant_id, store_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                inv["email"], auth.hash_password(password), name, inv["role"],
                inv["tenant_id"], store_id if inv["role"] == "lojista" else None,
            ),
        )
        user_id = cur.lastrowid
        conn.execute(
            "UPDATE invites SET used_at = CURRENT_TIMESTAMP WHERE id = ?",
            (inv["id"],),
        )

    # Loga o usuário imediatamente
    token_session, _ = auth.create_session(user_id)
    response.set_cookie(
        key=auth.SESSION_COOKIE, value=token_session,
        max_age=auth.SESSION_TTL_DAYS * 86400,
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/",
    )
    return {
        "user": {
            "id": user_id, "email": inv["email"], "name": name,
            "role": inv["role"], "tenant_id": inv["tenant_id"], "store_id": store_id,
        }
    }
