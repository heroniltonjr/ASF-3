import pytest
from backend import db
from backend.services.hybrid_search import search_vehicles, SearchRequest

@pytest.mark.asyncio
async def test_store_deactivation_cascades_to_vehicles(as_master):
    # 1. Cria loja e veículo de teste
    with db.tx() as conn:
        s_cur = conn.execute(
            "INSERT INTO stores (name, tenant_id, type, plan, status, is_active) VALUES ('Loja Teste Cascata', 1, 'Lojista', 'Pro', 'Ativo', 1)"
        )
        store_id = s_cur.lastrowid

        v_cur = conn.execute(
            """INSERT INTO vehicles (store_id, name, brand, model, price, km, active, status, sold)
               VALUES (?, 'Sedan Teste Cascata 2.0', 'Toyota', 'Corolla', 99000, 10000, 1, 'Publicado', 0)""",
            (store_id,)
        )
        vehicle_id = v_cur.lastrowid

    # 2. Verifica se o veículo aparece na busca
    hits = await search_vehicles(SearchRequest(query="Sedan Teste Cascata", limit=5))
    found = any(h.id == vehicle_id for h in hits)
    assert found is True, "Veículo deve aparecer enquanto a loja estiver Ativa"

    # 3. Desativa a loja via PATCH /api/stores/{store_id}
    res = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"status": "Inativo"}
    )
    assert res.status_code == 200

    # 4. Verifica se no banco o veículo foi desativado em cascata
    with db.tx() as conn:
        v_row = conn.execute("SELECT active, status FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
        assert v_row["active"] in (0, False)
        assert v_row["status"] == "Rascunho"

    # 5. Verifica se o veículo sumiu da busca
    hits_after = await search_vehicles(SearchRequest(query="Sedan Teste Cascata", limit=5))
    found_after = any(h.id == vehicle_id for h in hits_after)
    assert found_after is False, "Veículo NÃO deve aparecer quando a loja estiver Inativa"

    # 6. Reativa a loja
    res_reactivate = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"status": "Ativo"}
    )
    assert res_reactivate.status_code == 200

    # 7. Verifica se o veículo voltou a ser Publicado/Ativo
    with db.tx() as conn:
        v_reactivated = conn.execute("SELECT active, status FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
        assert v_reactivated["active"] in (1, True)
        assert v_reactivated["status"] == "Publicado"

    # 8. Limpeza
    with db.tx() as conn:
        conn.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
