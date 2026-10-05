"""Script para criar usuários lojistas para todas as lojas em formulaos_stores.
Ambientes: Supabase (PostgreSQL) e SQLite local (portal.sqlite3).
"""
import os
import re
import secrets
import sqlite3
import string
import unicodedata
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import auth, db


def generate_store_email(store_name: str) -> str:
    normalized = unicodedata.normalize("NFKD", store_name).encode("ascii", "ignore").decode("utf-8")
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", normalized).lower()
    return f"{clean_name}@asformula.com"


def generate_random_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.islower() for c in pwd) and any(c.isupper() for c in pwd) and any(c.isdigit() for c in pwd):
            return pwd


def main():
    print("1. Conectando ao banco Supabase PostgreSQL...")
    conn = db.connect()
    cur = conn.cursor() if hasattr(conn, "cursor") else conn

    # Busca todas as lojas do tipo Lojista
    stores = cur.execute(
        "SELECT id, name, type, tenant_id FROM stores WHERE lower(type) = 'lojista' ORDER BY id"
    ).fetchall()

    print(f"Total de lojas lojistas encontradas: {len(stores)}")

    credentials = []

    for s in stores:
        store_id = s["id"]
        store_name = s["name"]
        tenant_id = s.get("tenant_id") or 2
        email = generate_store_email(store_name)
        plain_password = generate_random_password(10)
        pwd_hash = auth.hash_password(plain_password)

        # Insere ou atualiza no Supabase (PostgreSQL)
        # Verifica se o email já existe
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        existing = cur.fetchone()

        if existing:
            user_id = existing["id"] if hasattr(existing, "keys") else existing[0]
            cur.execute(
                """
                UPDATE users
                SET store_id = ?, tenant_id = ?, password_hash = ?, name = ?, role = 'lojista'
                WHERE id = ?
                """,
                (store_id, tenant_id, pwd_hash, store_name, user_id),
            )
            action = "Atualizado"
        else:
            cur.execute(
                """
                INSERT INTO users (tenant_id, store_id, email, password_hash, name, role)
                VALUES (?, ?, ?, ?, ?, 'lojista')
                """,
                (tenant_id, store_id, email, pwd_hash, store_name),
            )
            action = "Criado"

        credentials.append({
            "store_id": store_id,
            "store_name": store_name,
            "tenant_id": tenant_id,
            "email": email,
            "password": plain_password,
            "password_hash": pwd_hash,
            "action": action
        })
        print(f"[{action}] Loja #{store_id} '{store_name}' -> {email} (Senha: {plain_password})")

    # Commit no PostgreSQL
    if hasattr(conn, "commit"):
        conn.commit()
    print("Sucesso no Supabase PostgreSQL!")

    # 2. Sincroniza também no SQLite local (portal.sqlite3) se existir
    sqlite_path = ROOT / "portal.sqlite3"
    if sqlite_path.exists():
        print(f"\n2. Sincronizando com SQLite local em {sqlite_path}...")
        sq_conn = sqlite3.connect(sqlite_path)
        sq_conn.row_factory = sqlite3.Row
        with sq_conn:
            for cred in credentials:
                existing = sq_conn.execute("SELECT id FROM users WHERE email = ?", (cred["email"],)).fetchone()
                if existing:
                    sq_conn.execute(
                        """
                        UPDATE users
                        SET store_id = ?, tenant_id = ?, password_hash = ?, name = ?, role = 'lojista'
                        WHERE id = ?
                        """,
                        (cred["store_id"], cred["tenant_id"], cred["password_hash"], cred["store_name"], existing["id"]),
                    )
                else:
                    sq_conn.execute(
                        """
                        INSERT INTO users (tenant_id, store_id, email, password_hash, name, role)
                        VALUES (?, ?, ?, ?, ?, 'lojista')
                        """,
                        (cred["tenant_id"], cred["store_id"], cred["email"], cred["password_hash"], cred["store_name"]),
                    )
        print("Sucesso na sincronização do SQLite local!")

    # 3. Gera documento Markdown com tabela de credenciais
    doc_path = ROOT / "docs" / "credenciais_lojistas.md"
    print(f"\n3. Escrevendo arquivo {doc_path}...")
    
    rows = []
    for c in credentials:
        rows.append(
            f"| {c['store_id']} | **{c['store_name']}** | `{c['email']}` | `{c['password']}` | `lojista` | {c['action']} |"
        )

    content = f"""# 🔐 Credenciais de Acesso dos Lojistas — Auto Shopping Fórmula

Tabela de usuários gerada automaticamente para os lojistas cadastrados em `formulaos_stores`.

- **Domínio padrão:** `@asformula.com`
- **Perfil de acesso (role):** `lojista`
- **Ambiente de autenticação:** Supabase PostgreSQL (`formulaos_users`) e SQLite local (`portal.sqlite3`)
- **Algoritmo de Hash:** PBKDF2-HMAC-SHA256 (600.000 iterações padrão OWASP)

---

### Tabela de Lojistas e Credenciais

| Loja ID | Nome da Loja | E-mail de Acesso | Senha Inicial | Perfil (Role) | Status |
| :---: | :--- | :--- | :--- | :---: | :---: |
{chr(10).join(rows)}

---

> [!NOTE]
> Os usuários acima têm acesso ao **Portal Administrativo** (`/admin/`) e ao **Painel de Atendimento PWA** (`/atendimento.html`).
> A senha pode ser alterada a qualquer momento pelo lojista através do menu **"Meu Perfil"** no cabeçalho ou menu lateral.
"""
    doc_path.write_text(content, encoding="utf-8")
    print("Arquivo de credenciais gerado com sucesso!")


if __name__ == "__main__":
    main()
