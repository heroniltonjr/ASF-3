"""CRUD de lojas — Master/Gestor enxergam tudo; Lojista vê só a própria."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import db, store_meta
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()

_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")
_MGMT = require_roles("master", "shopping")
_MASTER = require_roles("master")


def _scope_filter(user: dict) -> tuple[str, list]:
    if user["role"] in STORE_SCOPED_ROLES:
        return "WHERE id = ?", [user["store_id"]]
    return "", []


def _resolve_and_sync_store_logo(conn, st: dict) -> dict:
    """Garante que toda loja tenha logo_url sincronizado entre o banco e o site (store_meta)."""
    logo_url = (st.get("logo_url") or "").strip()
    if not logo_url:
        fallback_logo = store_meta.logo_for(st.get("name"))
        if fallback_logo:
            st["logo_url"] = fallback_logo
            try:
                conn.execute("UPDATE stores SET logo_url = ? WHERE id = ?", (fallback_logo, st["id"]))
            except Exception:
                pass
    else:
        store_meta.sync_store_meta(st["name"], logo=logo_url, whatsapp=st.get("phone"))
    return st


@router.get("/stores")
def list_stores(user: dict = Depends(_ALL)):
    where, params = _scope_filter(user)
    with db.tx() as conn:
        rows = conn.execute(f"SELECT * FROM stores {where} ORDER BY name", params).fetchall()
        stores_list = []
        for r in rows:
            st = _resolve_and_sync_store_logo(conn, dict(r))
            # Busca o e-mail do usuário gestor da loja (role lojista ou gestor)
            u_row = conn.execute(
                "SELECT email FROM users WHERE store_id = ? AND role IN ('lojista', 'gestor') ORDER BY id ASC LIMIT 1",
                (st["id"],),
            ).fetchone()
            st["manager_email"] = u_row["email"] if u_row else None
            stores_list.append(st)
    return {"stores": stores_list}


@router.get("/stores/{store_id}")
def get_store(store_id: int, user: dict = Depends(_ALL)):
    if user["role"] in STORE_SCOPED_ROLES and user.get("store_id") != store_id:
        raise HTTPException(403, "Sem acesso a esta loja")
    with db.tx() as conn:
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Loja não encontrada")
        st = _resolve_and_sync_store_logo(conn, dict(row))
        u_row = conn.execute(
            "SELECT email FROM users WHERE store_id = ? AND role IN ('lojista', 'gestor') ORDER BY id ASC LIMIT 1",
            (store_id,),
        ).fetchone()
        st["manager_email"] = u_row["email"] if u_row else None
    return {"store": st}


DEFAULT_PLAN_REVENUE = {
    "Enterprise": 18400,
    "Pro": 1500,
    "Start": 0,
}


@router.post("/stores", status_code=201)
def create_store(payload: dict, user: dict = Depends(_MGMT)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Nome da loja é obrigatório")
    tenant_id = payload.get("tenant_id") or user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "tenant_id obrigatório")

    store_type = payload.get("type") or "Lojista"

    # Se não for Master, força defaults: Plan = Start e Status = Ativo
    if user["role"] == "master":
        plan = payload.get("plan") or ("Enterprise" if store_type == "Auto Shopping" else "Start")
        status = payload.get("status") or "Ativo"
    else:
        plan = "Start"
        status = "Ativo"

    if store_type == "Lojista" and plan == "Enterprise":
        raise HTTPException(400, "O plano Enterprise é exclusivo para Tenants")

    if plan not in DEFAULT_PLAN_REVENUE:
        raise HTTPException(400, f"Plano inválido. Planos permitidos: {', '.join(DEFAULT_PLAN_REVENUE)}")

    monthly_revenue = (
        payload.get("monthly_revenue")
        if payload.get("monthly_revenue") is not None
        else DEFAULT_PLAN_REVENUE.get(plan, 0)
    )

    # Valida credenciais da loja se informadas
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()
    if email:
        if "@" not in email:
            raise HTTPException(400, "E-mail da loja inválido")
        if password and len(password) < 6:
            raise HTTPException(400, "A senha da loja deve ter no mínimo 6 caracteres")

    raw_logo = (payload.get("logo_url") or "").strip() or store_meta.logo_for(name)
    final_logo = store_meta.save_store_logo_asset(name, raw_logo) if raw_logo else None

    fields = {
        "name": name, "tenant_id": tenant_id,
        "type": store_type,
        "plan": plan,
        "status": status,
        "phone": (payload.get("phone") or "").strip() or None,
        "focal_name": (payload.get("focal_name") or "").strip() or None,
        "logo_url": final_logo,
        "response_time": payload.get("response_time"),
        "monthly_cost": payload.get("monthly_cost") or 0,
        "monthly_revenue": monthly_revenue,
    }
    cols = ", ".join(fields)
    placeholders = ", ".join("?" * len(fields))
    with db.tx() as conn:
        if email:
            existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                raise HTTPException(409, "Já existe um usuário com este e-mail")

        cur = conn.execute(f"INSERT INTO stores ({cols}) VALUES ({placeholders})", list(fields.values()))
        new_store_id = cur.lastrowid

        # Cria usuário lojista vinculado se e-mail fornecido
        if email:
            from .. import auth as _auth
            initial_pass = password or "demo123"
            conn.execute(
                "INSERT INTO users (email, password_hash, name, role, tenant_id, store_id) VALUES (?, ?, ?, 'lojista', ?, ?)",
                (email, _auth.hash_password(initial_pass), name, tenant_id, new_store_id),
            )

        row = conn.execute("SELECT * FROM stores WHERE id = ?", (new_store_id,)).fetchone()
        res_store = dict(row)
        res_store["manager_email"] = email or None
        store_meta.sync_store_meta(name, logo=res_store.get("logo_url"), whatsapp=res_store.get("phone"))
    return {"store": res_store}


_PATCHABLE = {
    "name", "type", "plan", "status", "phone", "focal_name", "logo_url", "is_active",
    "response_time", "monthly_cost", "monthly_revenue", "sdr_prompt", "sdr_auto_reactivate_minutes"
}


@router.patch("/stores/{store_id}")
def update_store(store_id: int, payload: dict, user: dict = Depends(_MGMT)):
    updates = {k: v for k, v in payload.items() if k in _PATCHABLE}

    # Restrição por papel: se não for Master, ignora alterações manuais de plan e status
    is_master = user["role"] == "master"
    if not is_master:
        updates.pop("plan", None)
        # Permite alteração de status/is_active se for a ação de ativar/desativar
        if "status" in updates and "name" in updates:
            # Edição geral via popup: não altera status
            updates.pop("status", None)
            updates.pop("is_active", None)

    email = (payload.get("email") or "").strip().lower() if "email" in payload else None
    password = (payload.get("password") or "").strip() if "password" in payload else None

    if email is not None and email != "" and "@" not in email:
        raise HTTPException(400, "E-mail da loja inválido")

    if password is not None and password != "" and len(password) < 6:
        raise HTTPException(400, "A senha da loja deve ter no mínimo 6 caracteres")

    if not updates and email is None and password is None:
        raise HTTPException(400, "Nada a atualizar")

    with db.tx() as conn:
        current = conn.execute("SELECT id, tenant_id, name, type, plan, monthly_revenue, status, is_active, logo_url, phone FROM stores WHERE id = ?", (store_id,)).fetchone()
        if not current:
            raise HTTPException(404, "Loja não encontrada")

        target_name = (updates.get("name") or current["name"]).strip()
        if "logo_url" in updates and updates["logo_url"]:
            updates["logo_url"] = store_meta.save_store_logo_asset(
                target_name, updates["logo_url"], old_name=current["name"]
            )
        elif not current["logo_url"] and "logo_url" not in updates:
            fallback_logo = store_meta.logo_for(target_name)
            if fallback_logo:
                updates["logo_url"] = fallback_logo

        new_type = updates.get("type", current["type"])
        new_plan = updates.get("plan", current["plan"])

        if new_type == "Lojista" and new_plan == "Enterprise":
            raise HTTPException(400, "O plano Enterprise é exclusivo para Tenants")

        if new_plan not in DEFAULT_PLAN_REVENUE:
            raise HTTPException(400, f"Plano inválido. Planos permitidos: {', '.join(DEFAULT_PLAN_REVENUE)}")

        if "plan" in updates and "monthly_revenue" not in updates:
            updates["monthly_revenue"] = DEFAULT_PLAN_REVENUE.get(new_plan, 0)

        # Alinha coerência entre status e is_active
        if updates.get("status") == "Inativo" and "is_active" not in updates:
            updates["is_active"] = 0
        elif updates.get("status") == "Ativo" and "is_active" not in updates:
            updates["is_active"] = 1
        elif updates.get("is_active") == 0 and "status" not in updates:
            updates["status"] = "Inativo"
        elif updates.get("is_active") == 1 and "status" not in updates:
            updates["status"] = "Ativo"

        if updates:
            cols = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE stores SET {cols} WHERE id = ?", [*updates.values(), store_id])

            # Cascata de status para os veículos da loja (compatível com SQLite e PostgreSQL)
            if updates.get("status") == "Inativo" or updates.get("is_active") == 0:
                conn.execute("UPDATE vehicles SET active = FALSE, status = 'Rascunho' WHERE store_id = ?", (store_id,))
            elif updates.get("status") == "Ativo" and updates.get("is_active", 1) == 1:
                conn.execute("UPDATE vehicles SET active = TRUE, status = 'Publicado' WHERE store_id = ? AND NOT coalesce(sold, FALSE)", (store_id,))

        # Atualiza ou cria usuário gestor da loja (role: lojista)
        from .. import auth as _auth
        manager_user = conn.execute(
            "SELECT id, email FROM users WHERE store_id = ? AND role IN ('lojista', 'gestor') ORDER BY id ASC LIMIT 1",
            (store_id,),
        ).fetchone()

        if email or password:
            if manager_user:
                u_updates = {}
                if email and email != manager_user["email"]:
                    existing = conn.execute("SELECT 1 FROM users WHERE email = ? AND id != ?", (email, manager_user["id"])).fetchone()
                    if existing:
                        raise HTTPException(409, "Já existe um usuário com este e-mail")
                    u_updates["email"] = email
                if password:
                    u_updates["password_hash"] = _auth.hash_password(password)

                if u_updates:
                    u_cols = ", ".join(f"{k} = ?" for k in u_updates)
                    conn.execute(f"UPDATE users SET {u_cols} WHERE id = ?", [*u_updates.values(), manager_user["id"]])
                    _auth.invalidate_user_sessions(manager_user["id"])
            elif email:
                # Se não havia usuário lojista criado ainda, cria agora
                existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
                if existing:
                    raise HTTPException(409, "Já existe um usuário com este e-mail")
                initial_pass = password or "demo123"
                conn.execute(
                    "INSERT INTO users (email, password_hash, name, role, tenant_id, store_id) VALUES (?, ?, ?, 'lojista', ?, ?)",
                    (email, _auth.hash_password(initial_pass), current["name"], current["tenant_id"], store_id),
                )

        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
        res_store = dict(row)
        u_row = conn.execute(
            "SELECT email FROM users WHERE store_id = ? AND role IN ('lojista', 'gestor') ORDER BY id ASC LIMIT 1",
            (store_id,),
        ).fetchone()
        res_store["manager_email"] = u_row["email"] if u_row else None
        store_meta.sync_store_meta(
            res_store["name"],
            logo=res_store.get("logo_url"),
            whatsapp=res_store.get("phone"),
            old_name=current["name"],
        )
    return {"store": res_store}


@router.delete("/stores/{store_id}", status_code=204)
def delete_store(store_id: int, user: dict = Depends(_MASTER)):
    with db.tx() as conn:
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
    return None


# ---------- Gerenciamento de vendedores da loja ----------

_LOJISTA_MGMT = require_roles("master", "shopping", "lojista", "gestor")


@router.get("/stores/{store_id}/sellers")
def list_sellers(store_id: int, user: dict = Depends(_LOJISTA_MGMT)):
    """Lista todos os vendedores vinculados a uma loja."""
    from ..deps import STORE_SCOPED_ROLES
    if user["role"] in STORE_SCOPED_ROLES and user.get("store_id") != store_id:
        raise HTTPException(403, "Sem acesso a esta loja")
    with db.tx() as conn:
        rows = conn.execute(
            "SELECT id, name, email, role, created_at FROM users WHERE store_id = ? AND role = 'vendedor' ORDER BY name",
            (store_id,),
        ).fetchall()
    return {"sellers": [dict(r) for r in rows]}


@router.post("/stores/{store_id}/sellers", status_code=201)
def create_seller(store_id: int, payload: dict, user: dict = Depends(_LOJISTA_MGMT)):
    """Cria um vendedor diretamente numa loja, sem necessidade de convite."""
    from .. import auth as _auth
    from ..deps import STORE_SCOPED_ROLES
    if user["role"] in STORE_SCOPED_ROLES and user.get("store_id") != store_id:
        raise HTTPException(403, "Sem acesso a esta loja")

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()

    if not name:
        raise HTTPException(400, "Nome é obrigatório")
    if not email or "@" not in email:
        raise HTTPException(400, "Email inválido")
    if len(password) < 6:
        raise HTTPException(400, "Senha deve ter ao menos 6 caracteres")

    with db.tx() as conn:
        store = conn.execute("SELECT tenant_id FROM stores WHERE id = ?", (store_id,)).fetchone()
        if not store:
            raise HTTPException(404, "Loja não encontrada")
        existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(409, "Já existe um usuário com este email")
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, name, role, tenant_id, store_id) VALUES (?, ?, ?, 'vendedor', ?, ?)",
            (email, _auth.hash_password(password), name, store["tenant_id"], store_id),
        )
        row = conn.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"seller": dict(row)}


@router.delete("/stores/{store_id}/sellers/{seller_id}", status_code=204)
def delete_seller(store_id: int, seller_id: int, user: dict = Depends(_LOJISTA_MGMT)):
    """Remove um vendedor da loja."""
    from ..deps import STORE_SCOPED_ROLES
    if user["role"] in STORE_SCOPED_ROLES and user.get("store_id") != store_id:
        raise HTTPException(403, "Sem acesso a esta loja")
    with db.tx() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE id = ? AND store_id = ? AND role = 'vendedor'", (seller_id, store_id)).fetchone()
        if not row:
            raise HTTPException(404, "Vendedor não encontrado nesta loja")
        conn.execute("DELETE FROM users WHERE id = ?", (seller_id,))
    return None
