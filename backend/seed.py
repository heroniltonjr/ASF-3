"""Seed inicial — popula tenants, users demo, lojas, veículos, leads e conversas.

Idempotente: roda apenas se a tabela `tenants` estiver vazia.
Senha demo para todos os três perfis: "demo123".
"""
from __future__ import annotations

import json

from . import auth, db

DEMO_PASSWORD = "demo123"

TENANTS = [
    ("COLLAB / Arara Azul", "platform", "Enterprise", "Ativo"),
    ("Auto Shopping Formula", "shopping", "Enterprise", "Ativo"),
]

STORES = [
    # (name, type, plan, status, response_time, monthly_cost, monthly_revenue)
    # As 22 lojas oficiais do Auto Shopping Fórmula (autoshoppingformula.com.br).
    ("Auto Shopping Formula", "Auto Shopping", "Enterprise", "Ativo",   "3m 18s", 3842, 18400),
    ("Betania Automoveis",    "Lojista",       "Pro",        "Ativo",   "2m 11s",  612,  1290),
    ("GX Auto",               "Lojista",       "Pro",        "Ativo",   "1m 49s",  438,  1290),
    ("Radar Automóveis",      "Lojista",       "Start",      "Atenção", "5m 02s",  811,   890),
    ("JW Veiculos",           "Lojista",       "Pro",        "Ativo",   "3m 40s",  392,  1290),
    ("Trinity Veículos",      "Lojista",       "Start",      "Ativo",   "4m 15s",  287,   890),
    ("Betel Automóveis",      "Lojista",       "Pro",        "Ativo",   "2m 30s",  450,  1290),
    ("Dani Multimarcas",      "Lojista",       "Start",      "Ativo",   "3m 02s",  320,   890),
    ("EV Automóveis",         "Lojista",       "Pro",        "Ativo",   "2m 48s",  510,  1290),
    ("Evidence Multimarcas",  "Lojista",       "Pro",        "Ativo",   "2m 05s",  490,  1290),
    ("Gilson Automóveis",     "Lojista",       "Start",      "Ativo",   "4m 02s",  280,   890),
    ("Global Automóveis",     "Lojista",       "Pro",        "Ativo",   "2m 22s",  430,  1290),
    ("GR Car",                "Lojista",       "Start",      "Ativo",   "3m 14s",  295,   890),
    ("Kadosh Automóveis",     "Lojista",       "Pro",        "Ativo",   "2m 55s",  460,  1290),
    ("Kallicar Multimarcas",  "Lojista",       "Start",      "Ativo",   "3m 22s",  315,   890),
    ("Luan Multimarcas",      "Lojista",       "Start",      "Ativo",   "3m 48s",  300,   890),
    ("Meu Automóvel",         "Lojista",       "Pro",        "Ativo",   "2m 14s",  420,  1290),
    ("Mundial Automóveis",    "Lojista",       "Pro",        "Ativo",   "2m 41s",  475,  1290),
    ("Neri Veículos",         "Lojista",       "Start",      "Ativo",   "3m 33s",  310,   890),
    ("Rocha Motors",          "Lojista",       "Pro",        "Ativo",   "2m 19s",  445,  1290),
    ("RS Motors",             "Lojista",       "Start",      "Ativo",   "3m 56s",  305,   890),
    ("Seminovos Movida",      "Lojista",       "Enterprise", "Ativo",   "1m 38s",  680,  2490),
    ("Tex Veículos",          "Lojista",       "Pro",        "Ativo",   "2m 29s",  455,  1290),
]

USERS = [
    # (email, name, role, tenant_name, store_name)
    ("master@collab.com",      "COLLAB / Arara Azul",          "master",   "COLLAB / Arara Azul",    None),
    ("gestor@asformula.com",   "Gestor Auto Shopping Formula", "shopping", "Auto Shopping Formula",  None),
    ("betania@betania.com",    "Betania Automoveis",           "lojista",  "Auto Shopping Formula",  "Betania Automoveis"),
]

VEHICLES = [
    # (name, price, mileage, transmission, fuel, store_name, image_path, status)
    ("Toyota Corolla XEi 2.0 Flex 2016/2017", "R$ 94.990",  "132.451 km", "Automático", "Flex",   "GX Auto",             "assets/car-corolla.jpg", "Publicado"),
    ("Volkswagen Gol 1.0 Flex 2021/2022",     "R$ 58.990",  "74.465 km",  "Manual",     "Hatch",  "Radar Automóveis",    "assets/car-gol.jpg",     "Sem atualização"),
    ("Honda City Hatchback Touring 2023",     "R$ 112.900", "49.742 km",  "Automático", "Flex",   "Betania Automoveis",  "assets/car-city.jpg",    "Publicado"),
    ("Volkswagen Saveiro Robust 1.6 2023",    "R$ 68.000",  "52.868 km",  "Manual",     "Picape", "JW Veiculos",         "assets/car-saveiro.jpg", "Publicado"),
    ("Honda Fit Twist 1.5 Flex 2013",         "R$ 57.900",  "135.693 km", "Automático", "Hatch",  "Trinity Veículos",    "assets/car-fit.jpg",     "Publicado"),
    # Catálogo enriquecido para o portal público.
    ("Toyota Yaris XL Plus Connect 2025",     "R$ 99.990",  "12.300 km",  "Automático", "Flex",   "Seminovos Movida",    None, "Publicado"),
    ("Hyundai HB20 Comfort Plus 2022",        "R$ 74.500",  "38.420 km",  "Manual",     "Flex",   "Dani Multimarcas",    None, "Publicado"),
    ("Chevrolet Onix LT 1.0 Turbo 2024",      "R$ 86.700",  "18.700 km",  "Automático", "Flex",   "EV Automóveis",       None, "Publicado"),
    ("Jeep Renegade Longitude 1.3 T 2023",    "R$ 124.900", "29.150 km",  "Automático", "Flex",   "Betel Automóveis",    None, "Publicado"),
    ("Fiat Pulse Drive 1.3 2024",             "R$ 92.300",  "8.900 km",   "Automático", "Flex",   "Mundial Automóveis",  None, "Publicado"),
    ("Volkswagen T-Cross Comfortline 2022",   "R$ 118.900", "41.220 km",  "Automático", "Flex",   "Rocha Motors",        None, "Publicado"),
    ("Toyota Hilux SR 2.8 Diesel 4x4 2023",   "R$ 245.000", "32.500 km",  "Automático", "Diesel", "Seminovos Movida",    None, "Publicado"),
    ("Renault Kwid Zen 1.0 2022",             "R$ 49.900",  "44.300 km",  "Manual",     "Flex",   "GR Car",              None, "Publicado"),
    ("Chevrolet Tracker Premier 2023",        "R$ 139.900", "27.800 km",  "Automático", "Flex",   "Global Automóveis",   None, "Publicado"),
    ("Nissan Kicks Advance 1.6 2022",         "R$ 99.900",  "53.700 km",  "Automático", "Flex",   "Evidence Multimarcas",None, "Publicado"),
    ("Ford Ranger XLS 2.2 Diesel 2021",       "R$ 189.500", "78.900 km",  "Automático", "Diesel", "Meu Automóvel",       None, "Publicado"),
    ("Volkswagen Polo Highline 1.0 TSI 2022", "R$ 89.900",  "36.100 km",  "Automático", "Flex",   "Tex Veículos",        None, "Publicado"),
    ("Hyundai Creta Action 1.6 2024",         "R$ 121.500", "11.400 km",  "Automático", "Flex",   "Kadosh Automóveis",   None, "Publicado"),
    ("Honda HR-V EX 1.8 Flex 2021",           "R$ 112.000", "59.800 km",  "Automático", "Flex",   "Gilson Automóveis",   None, "Publicado"),
    ("Fiat Strada Volcano 1.3 CD 2023",       "R$ 109.500", "21.700 km",  "Manual",     "Flex",   "Luan Multimarcas",    None, "Publicado"),
    ("Toyota Corolla Cross XR 2.0 2024",      "R$ 169.900", "16.300 km",  "Automático", "Flex",   "Kallicar Multimarcas",None, "Publicado"),
    ("Chevrolet S10 LTZ Diesel 4x4 2022",     "R$ 235.000", "62.500 km",  "Automático", "Diesel", "Neri Veículos",       None, "Publicado"),
    ("BYD Dolphin Mini GS 2024",              "R$ 115.900", "5.200 km",   "Automático", "Elétrico","RS Motors",          None, "Publicado"),
]

LEADS = [
    # (name, car_interest, store_name, stage, score, budget, source)
    ("Mariana Souza",   "Honda City Hatchback Touring 2023", "Betania Automoveis", "Humano",      94, "R$ 110 mil", "WhatsApp"),
    ("Carlos Eduardo",  "Toyota Corolla XEi 2017",           "GX Auto",            "Qualificado", 88, "R$ 95 mil",  "Instagram"),
    ("Priscila Lima",   "VW Gol 1.0 2022",                   "Radar Automóveis",   "Novo",        71, "R$ 60 mil",  "Site"),
    ("João Ferreira",   "VW Saveiro Robust 2023",            "JW Veiculos",        "Visita",      91, "R$ 70 mil",  "WhatsApp"),
    ("Ana Paula",       "Honda Fit Twist 2013",              "Trinity Veículos",   "Fechado",     97, "R$ 58 mil",  "Google"),
    ("Rafael Moura",    "SUV até R$ 120 mil",                "Betania Automoveis", "Novo",        69, "R$ 120 mil", "WhatsApp"),
    ("Bianca Nunes",    "Sedan automático flex",             "GX Auto",            "Qualificado", 83, "R$ 90 mil",  "Site"),
    ("Mateus Rocha",    "Pick-up cabine dupla",              "Radar Automóveis",   "Humano",      86, "R$ 130 mil", "WhatsApp"),
]

CONVERSATIONS = [
    {
        "lead_name": "Mariana Souza", "store": "Betania Automoveis",
        "intent": "Honda City Touring", "status": "Handoff humano",
        "details": {"Score": "94/100", "Entrada": "R$ 30 mil", "Troca": "HB20 2019", "Próxima ação": "Negociar avaliação da troca"},
        "messages": [
            ("lead",  "Oi, quero saber se o Honda City Touring ainda está disponível."),
            ("agent", "Está sim, Mariana. Ele é 2023, automático, flex e está com 49.742 km. Você pretende financiar ou comprar à vista?"),
            ("lead",  "Tenho uma entrada e queria colocar meu HB20 na troca."),
            ("agent", "Perfeito. Já qualifiquei seu interesse e vou chamar um consultor para continuar a negociação por aqui."),
        ],
    },
    {
        "lead_name": "Mateus Rocha", "store": "Radar Automóveis",
        "intent": "Pick-up cabine dupla", "status": "Negociação",
        "details": {"Score": "86/100", "Entrada": "R$ 45 mil", "Uso": "Trabalho e família", "Próxima ação": "Enviar opções até R$ 130 mil"},
        "messages": [
            ("lead",  "Preciso de uma caminhonete boa para trabalho, mas confortável."),
            ("agent", "Tenho algumas opções dentro do seu perfil. Você prefere diesel ou flex?"),
            ("lead",  "Pode ser flex se estiver bem conservada."),
            ("agent", "Vou transferir para um atendente com as opções mais aderentes."),
        ],
    },
    {
        "lead_name": "Carlos Eduardo", "store": "GX Auto",
        "intent": "Corolla XEi", "status": "Aguardando visita",
        "details": {"Score": "88/100", "Entrada": "R$ 50 mil", "Horário": "Sábado 10h", "Próxima ação": "Confirmar visita"},
        "messages": [
            ("lead",  "Vi o Corolla no site. Dá para visitar sábado?"),
            ("agent", "Dá sim. O Auto Shopping atende sábado das 08:00 às 13:00. Posso reservar 10h para você?"),
            ("lead",  "Pode ser."),
            ("agent", "Combinado, vou avisar a loja GX Auto e deixar tudo registrado no CRM."),
        ],
    },
]


def already_seeded(conn) -> bool:
    row = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()
    return row["c"] > 0


# ---------------------------------------------------------------------------
# Épico 1 (Tex) — Dia 1. Seed de multiatendimento, idempotente (guard em tags).
# Não cria usuários vendedor/gestor: esses roles dependem da migration de enums
# (deferida). Aqui só dados aditivos sobre a loja-piloto Tex.
# ---------------------------------------------------------------------------
TEX_STORE_NAME = "Tex Veículos"

# (name, color, scope) — scope 'global' = visível a toda a loja (user_id NULL).
TEX_TAGS = [
    ("Quente",              "#e60023", "global"),
    ("Frio",                "#64748b", "global"),
    ("Test-drive agendado", "#16a34a", "global"),
    ("Aguardando doc",      "#f59e0b", "global"),
    ("Sem retorno",         "#000000", "global"),
]

# (name, car_interest, stage, score, budget, source, phone) — stages dentro do
# enum atual (Novo/Qualificado/Humano/Visita/Fechado).
TEX_LEADS = [
    ("Fernando Tex (gestor demo)", "Toyota Hilux SR Diesel", "Qualificado", 90, "R$ 240 mil", "WhatsApp", "5565990000010"),
    ("Cliente Renata",             "Jeep Renegade Longitude", "Novo",        72, "R$ 125 mil", "Instagram", "5565990000011"),
    ("Cliente Paulo",              "VW Polo Highline TSI",    "Visita",      85, "R$ 90 mil",  "Site",      "5565990000012"),
    ("Cliente Aline",              "Hyundai Creta Action",    "Humano",      88, "R$ 120 mil", "WhatsApp",  "5565990000013"),
]

# Aplicação de tags: (lead_name, [tag_name, ...])
TEX_LEAD_TAGS = [
    ("Fernando Tex (gestor demo)", ["Quente", "Test-drive agendado"]),
    ("Cliente Renata",             ["Frio"]),
    ("Cliente Paulo",              ["Quente", "Aguardando doc"]),
]

# Notas privadas: (lead_name, body)
TEX_NOTES = [
    ("Fernando Tex (gestor demo)", "Lead quente — quer fechar até sexta. Tem entrada de R$ 80 mil."),
    ("Cliente Paulo",              "Visita marcada sábado 10h. Confirmar documentação do usado na troca."),
]


def seed_multiatendimento() -> bool:
    """Seed do Épico 1 para a loja Tex. Returns True se semeou agora."""
    with db.tx() as conn:
        has_tags = conn.execute("SELECT COUNT(*) AS c FROM tags").fetchone()["c"]
        if has_tags:
            return False

        store = conn.execute(
            "SELECT id FROM stores WHERE name = ?", (TEX_STORE_NAME,)
        ).fetchone()
        if not store:
            # Sem a loja Tex (DB com seed antigo); nada a fazer com segurança.
            return False
        store_id = store["id"]

        # Tenant da loja Tex (para vincular os usuários).
        tex_tenant = conn.execute(
            "SELECT tenant_id FROM stores WHERE id = ?", (store_id,)
        ).fetchone()
        tex_tenant_id = tex_tenant["tenant_id"] if tex_tenant else None

        # Cria os usuários reais da Tex: Fernando (gestor) e Cauê (vendedor).
        def _ensure_user(email, name, role):
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                return existing["id"]
            cur = conn.execute(
                """
                INSERT INTO users (email, password_hash, name, role, tenant_id, store_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (email, auth.hash_password(DEMO_PASSWORD), name, role, tex_tenant_id, store_id),
            )
            return cur.lastrowid

        gestor_id = _ensure_user("fernando@tex.com", "Fernando (Tex)", "gestor")
        vendedor_id = _ensure_user("caue@tex.com", "Cauê (Tex)", "vendedor")

        # Autor das tags/notas = gestor; leads são atribuídos ao vendedor.
        author_id = gestor_id

        tag_id_by_name: dict[str, int] = {}
        for name, color, scope in TEX_TAGS:
            user_id = None if scope == "global" else author_id
            cur = conn.execute(
                "INSERT INTO tags (store_id, user_id, name, color) VALUES (?, ?, ?, ?)",
                (store_id, user_id, name, color),
            )
            tag_id_by_name[name] = cur.lastrowid

        lead_id_by_name: dict[str, int] = {}
        for name, car, stage, score, budget, source, phone in TEX_LEADS:
            cur = conn.execute(
                """
                INSERT INTO leads
                    (store_id, name, car_interest, stage, score, budget, source, phone, assigned_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (store_id, name, car, stage, score, budget, source, phone, vendedor_id),
            )
            lead_id_by_name[name] = cur.lastrowid

        for lead_name, tag_names in TEX_LEAD_TAGS:
            lead_id = lead_id_by_name.get(lead_name)
            if not lead_id:
                continue
            for tag_name in tag_names:
                tag_id = tag_id_by_name.get(tag_name)
                if tag_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO lead_tags (lead_id, tag_id, applied_by_user_id) VALUES (?, ?, ?)",
                        (lead_id, tag_id, author_id),
                    )

        for lead_name, body in TEX_NOTES:
            lead_id = lead_id_by_name.get(lead_name)
            if lead_id and author_id:
                conn.execute(
                    "INSERT INTO lead_notes (store_id, lead_id, user_id, body) VALUES (?, ?, ?, ?)",
                    (store_id, lead_id, author_id, body),
                )

        return True


def run() -> bool:
    """Returns True if seeded now, False if already seeded."""
    with db.tx() as conn:
        if already_seeded(conn):
            return False

        tenant_id_by_name: dict[str, int] = {}
        for name, type_, plan, status in TENANTS:
            cur = conn.execute(
                "INSERT INTO tenants (name, type, plan, status) VALUES (?, ?, ?, ?)",
                (name, type_, plan, status),
            )
            tenant_id_by_name[name] = cur.lastrowid

        shopping_tenant_id = tenant_id_by_name["Auto Shopping Formula"]

        store_id_by_name: dict[str, int] = {}
        for name, type_, plan, status, response, cost, revenue in STORES:
            cur = conn.execute(
                """
                INSERT INTO stores
                    (tenant_id, name, type, plan, status, response_time, monthly_cost, monthly_revenue)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (shopping_tenant_id, name, type_, plan, status, response, cost, revenue),
            )
            store_id_by_name[name] = cur.lastrowid

        for email, name, role, tenant_name, store_name in USERS:
            conn.execute(
                """
                INSERT INTO users (email, password_hash, name, role, tenant_id, store_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    auth.hash_password(DEMO_PASSWORD),
                    name,
                    role,
                    tenant_id_by_name.get(tenant_name),
                    store_id_by_name.get(store_name) if store_name else None,
                ),
            )

        for name, price, mileage, transmission, fuel, store, image, status in VEHICLES:
            conn.execute(
                """
                INSERT INTO vehicles
                    (store_id, name, price, mileage, transmission, fuel, image_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (store_id_by_name[store], name, price, mileage, transmission, fuel, image, status),
            )

        lead_id_by_name: dict[str, int] = {}
        for name, car, store, stage, score, budget, source in LEADS:
            cur = conn.execute(
                """
                INSERT INTO leads
                    (store_id, name, car_interest, stage, score, budget, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (store_id_by_name[store], name, car, stage, score, budget, source),
            )
            lead_id_by_name[name] = cur.lastrowid

        for conv in CONVERSATIONS:
            cur = conn.execute(
                """
                INSERT INTO conversations
                    (store_id, lead_id, lead_name, intent, status, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    store_id_by_name[conv["store"]],
                    lead_id_by_name.get(conv["lead_name"]),
                    conv["lead_name"],
                    conv["intent"],
                    conv["status"],
                    json.dumps(conv["details"], ensure_ascii=False),
                ),
            )
            conversation_id = cur.lastrowid
            for sender, body in conv["messages"]:
                conn.execute(
                    "INSERT INTO messages (conversation_id, sender, body) VALUES (?, ?, ?)",
                    (conversation_id, sender, body),
                )

        return True
