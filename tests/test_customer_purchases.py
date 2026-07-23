"""Testes para o perfil expandido de leads e histórico de compras (customer_purchases)."""
import pytest
from backend import db, ingest


async def test_lead_expanded_fields(as_master):
    """Testa criação e edição de lead com novos campos (city, trade_in_car, payment_preference, searched_history_json)."""
    # 1. Criar lead com novos campos
    payload = {
        "store_id": 2,
        "name": "Carlos Eduardo",
        "car_interest": "Jeep Compass",
        "stage": "Novo",
        "phone": "5565988887777",
        "city": "Cuiabá",
        "trade_in_car": "Gol 1.6 2019",
        "payment_preference": "Financiamento",
        "searched_history_json": '["Jeep Compass", "Toyota Corolla"]'
    }
    r = await as_master.post("/api/leads", json=payload)
    assert r.status_code == 201
    lead = r.json()["lead"]
    assert lead["city"] == "Cuiabá"
    assert lead["trade_in_car"] == "Gol 1.6 2019"
    assert lead["payment_preference"] == "Financiamento"

    # 2. Editar lead
    lid = lead["id"]
    r_patch = await as_master.patch(f"/api/leads/{lid}", json={"city": "Várzea Grande"})
    assert r_patch.status_code == 200
    assert r_patch.json()["lead"]["city"] == "Várzea Grande"


async def test_customer_purchases_table(as_master):
    """Testa inserção e consulta na nova tabela customer_purchases."""
    with db.tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO customer_purchases (store_id, lead_id, vehicle_name, sale_price, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (2, 1, "Toyota Corolla Cross 2.0", 165000.0, "À vista", "Venda concluída no Feirão")
        )
        pid = cur.lastrowid
        assert pid is not None

        row = conn.execute("SELECT * FROM customer_purchases WHERE id = ?", (pid,)).fetchone()
        assert row is not None
        assert row["vehicle_name"] == "Toyota Corolla Cross 2.0"
        assert float(row["sale_price"]) == 165000.0


async def test_enrich_lead_from_interaction(as_master):
    """Testa o enriquecimento automático e incremental do lead durante as mensagens enviadas."""
    with db.tx() as conn:
        lid = conn.execute(
            "INSERT INTO leads (store_id, name, car_interest, stage, phone) VALUES (2, 'Lead Teste', 'A definir', 'Novo', '5565977776666')"
        ).lastrowid

        # Simula mensagem informando cidade, forma de pagamento e carro buscado
        ingest._enrich_lead_from_interaction(conn, lid, "Moro em Cuiabá e procuro um Corolla para financiar")

        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lid,)).fetchone()
        assert lead["city"] == "Cuiabá"
        assert lead["payment_preference"] == "Financiamento"
        assert lead["car_interest"] == "Corolla"
        assert "Corolla" in lead["searched_history_json"]
