"""POST /api/login, POST /api/logout, GET /api/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .. import auth, db
from ..deps import get_session_user, require_user
from ..settings import settings

router = APIRouter()


import secrets
import string

from ..services import email_service


@router.post("/login")
def login(payload: dict, response: Response):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "Informe email e senha")

    with db.tx() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.name, u.role, u.tenant_id, u.store_id, u.avatar_url, u.password_hash, st.plan AS store_plan
            FROM users u
            LEFT JOIN stores st ON st.id = u.store_id
            WHERE u.email = ?
            """,
            (email,),
        ).fetchone()
        if not row and email.endswith(".com.br"):
            row = conn.execute(
                """
                SELECT u.id, u.email, u.name, u.role, u.tenant_id, u.store_id, u.avatar_url, u.password_hash, st.plan AS store_plan
                FROM users u
                LEFT JOIN stores st ON st.id = u.store_id
                WHERE u.email = ?
                """,
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
            "avatar_url": row["avatar_url"] if "avatar_url" in row.keys() else None,
            "store_plan": row["store_plan"] if "store_plan" in row.keys() and row["store_plan"] else "Start",
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
    updates = {}
    
    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name or len(name) < 2:
            raise HTTPException(400, "O nome deve ter no mínimo 2 caracteres")
        updates["name"] = name

    if "email" in payload:
        new_email = (payload.get("email") or "").strip().lower()
        if not new_email or "@" not in new_email or "." not in new_email:
            raise HTTPException(400, "Informe um endereço de e-mail válido")
        
        # Valida se o e-mail já pertence a outro usuário
        with db.tx() as conn:
            existing = conn.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, user["id"])).fetchone()
            if existing:
                raise HTTPException(409, "Este endereço de e-mail já está sendo utilizado por outro usuário")
        updates["email"] = new_email

    if "avatar_url" in payload:
        avatar_url = (payload.get("avatar_url") or "").strip() or None
        updates["avatar_url"] = avatar_url

    if not updates:
        raise HTTPException(400, "Nenhum dado informado para atualização")

    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [user["id"]]

    with db.tx() as conn:
        conn.execute(f"UPDATE users SET {cols} WHERE id = ?", vals)
        row = conn.execute(
            "SELECT id, email, name, role, tenant_id, store_id, avatar_url FROM users WHERE id = ?",
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


@router.post("/forgot-password")
def forgot_password(payload: dict):
    """Gera uma nova senha aleatória segura e envia para o e-mail cadastrado."""
    email = (payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Informe um endereço de e-mail válido")

    with db.tx() as conn:
        row = conn.execute("SELECT id, name, email FROM users WHERE lower(email) = ?", (email,)).fetchone()
        if not row and email.endswith(".com.br"):
            row = conn.execute("SELECT id, name, email FROM users WHERE lower(email) = ?", (email[:-3],)).fetchone()

        if row:
            # Gera senha segura de 10 caracteres (letras maiúsculas, minúsculas e dígitos)
            chars = string.ascii_letters + string.digits
            new_plain_pass = "".join(secrets.choice(chars) for _ in range(10))
            new_hash = auth.hash_password(new_plain_pass)

            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row["id"]))
            auth.invalidate_user_sessions(row["id"])

            subject = "Formula OS — Redefinição de Senha de Acesso"
            body_text = (
                f"Olá, {row['name']}!\n\n"
                f"Uma solicitação de recuperação de senha foi realizada para sua conta no Formula OS.\n\n"
                f"Sua nova senha temporária é:\n"
                f"   {new_plain_pass}\n\n"
                f"Recomendamos que você faça login e altere sua senha no menu 'Meu Perfil e Segurança'.\n\n"
                f"Atenciosamente,\n"
                f"Equipe Auto Shopping Fórmula"
            )
            body_html = f"""
            <div style="font-family: sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h2 style="color: #1e3a8a;">Formula OS</h2>
                <p>Olá, <strong>{row['name']}</strong>!</p>
                <p>Uma solicitação de recuperação de senha foi realizada para sua conta.</p>
                <div style="background: #f1f5f9; padding: 15px; border-radius: 6px; text-align: center; font-size: 18px; font-weight: bold; letter-spacing: 2px; color: #0f172a;">
                    {new_plain_pass}
                </div>
                <p style="margin-top: 15px; font-size: 13px; color: #64748b;">
                    Recomendamos que você faça login e atualize sua senha no menu <em>Meu Perfil e Segurança</em>.
                </p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
                <small style="color: #94a3b8;">Auto Shopping Fórmula — Gestão Inteligente</small>
            </div>
            """
            email_service.send_email(row["email"], subject, body_text, body_html)

    # Resposta uniforme para proteção contra user-enumeration
    return {
        "ok": True,
        "message": "Se o e-mail informado estiver cadastrado, a nova senha de acesso foi enviada com sucesso.",
    }

