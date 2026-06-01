"""Dependencies do FastAPI: auth + RBAC."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request

from . import auth

# Roles com acesso restrito à própria loja (store_id).
# gestor: vê tudo da loja; vendedor: vê só leads atribuídos a ele (Dia 2).
# Por enquanto ambos se comportam como lojista (scoped por store_id).
STORE_SCOPED_ROLES = frozenset({"lojista", "gestor", "vendedor"})


def get_session_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(auth.SESSION_COOKIE)
    return auth.get_user_by_token(token) if token else None


def require_user(user: Optional[dict] = Depends(get_session_user)) -> dict:
    if user is None:
        raise HTTPException(401, "Sessão obrigatória")
    return user


def require_roles(*roles: str):
    allowed = set(roles)

    def dep(user: dict = Depends(require_user)) -> dict:
        if allowed and user["role"] not in allowed:
            raise HTTPException(403, "Sem permissão para este recurso")
        return user

    return dep
