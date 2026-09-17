"""POST /api/login, POST /api/logout, GET /api/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .. import auth, db
from ..deps import get_session_user, require_user
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
        if not row and email.endswith(".com.br"):
            row = conn.execute(
                "SELECT id, email, name, role, tenant_id, store_id, password_hash FROM users WHERE email = ?",
                (email[:-3],),  # tenta sem '.br' (ex: gestor@asformula.com)
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


@router.patch("/me")
def update_profile(payload: dict, user: dict = Depends(require_user)):
    name = (payload.get("name") or "").strip()
    if not name or len(name) < 2:
        raise HTTPException(400, "O nome deve ter no mínimo 2 caracteres")

    with db.tx() as conn:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user["id"]))
        row = conn.execute(
            "SELECT id, email, name, role, tenant_id, store_id FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()

    auth.invalidate_user_sessions(user["id"])
    return {"ok": True, "user": dict(row)}


@router.post("/me/change-password")
def change_password(payload: dict, user: dict = Depends(require_user)):
    current_password = payload.get("current_password") or ""
    new_password = payload.get("new_password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if not current_password or not new_password:
        raise HTTPException(400, "Informe a senha atual e a nova senha")

    if confirm_password and confirm_password != new_password:
        raise HTTPException(400, "A confirmação da nova senha não confere")

    if len(new_password) < 6:
        raise HTTPException(400, "A nova senha deve ter no mínimo 6 caracteres")

    if new_password == current_password:
        raise HTTPException(400, "A nova senha deve ser diferente da senha atual")

    with db.tx() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not row or not auth.verify_password(current_password, row["password_hash"]):
            raise HTTPException(400, "Senha atual incorreta")

        new_hash = auth.hash_password(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))

    auth.invalidate_user_sessions(user["id"])
    return {"ok": True, "message": "Senha atualizada com sucesso"}
