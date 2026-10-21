"""Testes da Story 5.1: Backend Analytics Insights & Exportação CSV."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from backend import db


@pytest.mark.asyncio
async def test_insights_unauthenticated(client: AsyncClient):
    """Cliente anônimo deve receber 401."""
    res = await client.get("/api/dashboard/insights")
    assert res.status_code == 401

    res_csv = await client.get("/api/leads/export.csv")
    assert res_csv.status_code == 401


@pytest.mark.asyncio
async def test_insights_master_global(as_master: AsyncClient):
    """Master obtém dados analíticos globais e agrupamentos corretos."""
    # Inserir leads de teste
    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO leads (store_id, name, car_interest, stage, score, phone, city, payment_preference, created_at)
            VALUES
                (1, 'Cliente BH 1', 'Toyota Corolla XEi 2022', 'Novo', 80, '31999990001', 'Belo Horizonte', 'troca', datetime('now', '-2 days')),
                (1, 'Cliente BH 2', 'Jeep Compass Longitude', 'Qualificado', 70, '31999990002', 'Belo Horizonte', 'financiamento', datetime('now', '-3 days')),
                (2, 'Cliente Contagem', 'Fiat Pulse Audace', 'Fechado', 90, '31999990003', 'Contagem', 'entrada', datetime('now', '-5 days'))
            """
        )

    res = await as_master.get("/api/dashboard/insights?period=total")
    assert res.status_code == 200
    data = res.json()

    assert data["total_leads"] >= 3
    assert "by_city" in data
    assert "by_payment" in data
    assert "by_brand" in data
    assert "by_car" in data
    assert "by_store" in data

    # Validar cidades
    city_names = [item["city"] for item in data["by_city"]]
    assert "Belo Horizonte" in city_names
    assert "Contagem" in city_names

    # Validar marcas extraídas inteligentemente
    brands = [item["brand"] for item in data["by_brand"]]
    assert "Toyota" in brands or "Jeep" in brands or "Fiat" in brands


@pytest.mark.asyncio
async def test_insights_lojista_scoped(as_lojista: AsyncClient, as_master: AsyncClient):
    """Lojista visualiza apenas leads associados à sua loja."""
    # Descobrir a store_id da lojista betania
    with db.tx() as conn:
        store_row = conn.execute("SELECT id FROM stores WHERE name = 'Betania Automoveis'").fetchone()
        assert store_row, "Loja Betania deve existir no seed"
        betania_store_id = store_row["id"]

        other_store = conn.execute("SELECT id FROM stores WHERE id != ?", (betania_store_id,)).fetchone()
        assert other_store, "Outra loja deve existir"
        other_store_id = other_store["id"]

        # Inserir um lead em cada loja
        conn.execute(
            """
            INSERT INTO leads (store_id, name, car_interest, stage, phone, city, payment_preference)
            VALUES
                (?, 'Lead Betania Teste', 'Honda HR-V', 'Novo', '31988880001', 'Belo Horizonte', 'troca'),
                (?, 'Lead Outra Loja Teste', 'Renault Duster', 'Novo', '31988880002', 'Betim', 'financiamento')
            """,
            (betania_store_id, other_store_id)
        )

    # Consulta como Lojista Betania
    res = await as_lojista.get("/api/dashboard/insights?period=total")
    assert res.status_code == 200
    data = res.json()

    # Todos os leads retornados por loja devem ser apenas da loja da Betânia
    stores_returned = [s["store_id"] for s in data["by_store"]]
    assert all(s_id == betania_store_id for s_id in stores_returned)


@pytest.mark.asyncio
async def test_insights_period_filters(as_master: AsyncClient):
    """Testa filtros temporais (today, 7days, custom)."""
    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO leads (store_id, name, car_interest, stage, phone, city, payment_preference, created_at)
            VALUES
                (1, 'Lead Hoje', 'Toyota Yaris', 'Novo', '31999991111', 'BH', 'troca', datetime('now')),
                (1, 'Lead Antigo', 'Chevrolet Onix', 'Perdido', '31999992222', 'BH', 'financiamento', datetime('now', '-45 days'))
            """
        )

    # Filtro hoje
    res_today = await as_master.get("/api/dashboard/insights?period=today")
    assert res_today.status_code == 200
    today_data = res_today.json()
    assert today_data["total_leads"] >= 1

    # Filtro custom com range antigo
    res_custom = await as_master.get("/api/dashboard/insights?period=custom&start_date=2020-01-01&end_date=2020-01-02")
    assert res_custom.status_code == 200
    assert res_custom.json()["total_leads"] == 0


@pytest.mark.asyncio
async def test_export_leads_csv(as_master: AsyncClient):
    """Testa geração de CSV com BOM e cabeçalhos corretos."""
    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO leads (store_id, name, car_interest, stage, phone, city, payment_preference)
            VALUES (1, 'Lead CSV Teste', 'Volkswagen Nivus', 'Novo', '31977770001', 'Nova Lima', 'troca')
            """
        )

    res = await as_master.get("/api/leads/export.csv?period=total")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment; filename=" in res.headers["content-disposition"]

    content = res.text
    # Deve conter BOM UTF-8
    assert content.startswith("\ufeff")
    # Deve conter os cabeçalhos esperados
    assert "ID;Nome;Telefone;Cidade;Veiculo de Interesse;Estagio;Forma de Pagamento;Loja;Vendedor;Data de Criacao" in content
    # Deve conter o lead inserido
    assert "Lead CSV Teste" in content
    assert "Volkswagen Nivus" in content
    assert "Nova Lima" in content
