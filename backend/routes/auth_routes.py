"""POST /api/login, POST /api/logout, GET /api/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .. import auth, db
from ..deps import get_session_user
from ..settings import settings

router = APIRouter()


@router.post("/login")
def login(payload: dict, response: Response):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "Informe email e senha")

    with db.tx() as conn:
        row = conn.execute(
            "SELECT id, email, name, role, tenant_id, store_id, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if not row or not auth.verify_password(password, row["password_hash"]):
        raise HTTPException(401, "Credenciais inválidas")

    token, _expires = auth.create_session(row["id"])
    response.set_cookie(
        key=auth.SESSION_COOKIE,
        value=token,
        max_age=auth.SESSION_TTL_DAYS * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return {
        "user": {
            "id": row["id"], "email": row["email"], "name": row["name"],
            "role": row["role"], "tenant_id": row["tenant_id"], "store_id": row["store_id"],
        }
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        auth.revoke_session(token)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(get_session_user)):
    return {"user": user}
