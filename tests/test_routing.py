"""Testes automatizados da inversão de roteamento (Story 1.2).

Valida:
1. Portal público na raiz (GET /, /estoque.html, /veiculo.html, etc.)
2. Painel administrativo em /admin e /admin/
3. Aliases amigáveis /sistema e /painel
4. Multiatendimento mobile em /atendimento.html e /atendimento
5. Retrocompatibilidade de /portal/* e /portal/assets/*
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_root_serves_public_portal(client):
    """GET / deve entregar a página inicial da vitrine pública."""
    r = await client.get("/")
    assert r.status_code == 200
    assert "Auto Shopping Fórmula" in r.text
    assert "data-page=\"home\"" in r.text


@pytest.mark.asyncio
async def test_public_subpages_served_at_root(client):
    """Páginas da vitrine devem responder diretamente pela raiz."""
    for path, expected_snippet in [
        ("/estoque.html", "data-page=\"estoque\""),
        ("/veiculo.html", "data-page=\"veiculo\""),
        ("/lojas.html", "data-page=\"lojas\""),
        ("/vender.html", "data-page=\"vender\""),
        ("/sobre.html", "data-page=\"sobre\""),
    ]:
        r = await client.get(path)
        assert r.status_code == 200, f"Falha ao carregar {path}"
        assert expected_snippet in r.text


@pytest.mark.asyncio
async def test_public_assets_served_at_root(client):
    """Assets da vitrine devem responder sob /assets/."""
    r_css = await client.get("/assets/portal.css")
    assert r_css.status_code == 200
    assert "asf" in r_css.text or "color" in r_css.text

    r_js = await client.get("/assets/portal.js")
    assert r_js.status_code == 200
    assert "vehicleCardHTML" in r_js.text


@pytest.mark.asyncio
async def test_admin_redirect_and_serving(client):
    """GET /admin deve redirecionar para /admin/ e servir a SPA de gestão."""
    r_redir = await client.get("/admin", follow_redirects=False)
    assert r_redir.status_code == 301
    assert r_redir.headers["location"] == "/admin/"

    r_admin = await client.get("/admin/")
    assert r_admin.status_code == 200
    assert "Formula OS" in r_admin.text
    assert "Portal comercial" in r_admin.text


@pytest.mark.asyncio
async def test_admin_aliases_redirect(client):
    """Aliases amigáveis /sistema e /painel devem redirecionar para /admin/."""
    for alias in ["/sistema", "/painel"]:
        r = await client.get(alias, follow_redirects=False)
        assert r.status_code == 307
        assert r.headers["location"] == "/admin/"


@pytest.mark.asyncio
async def test_admin_assets_under_admin_prefix(client):
    """Assets relativos do painel (/admin/styles.css, /admin/app.js) devem responder 200."""
    r_css = await client.get("/admin/styles.css")
    assert r_css.status_code == 200
    assert "app-shell" in r_css.text or "sidebar" in r_css.text

    r_js = await client.get("/admin/app.js")
    assert r_js.status_code == 200
    assert "Formula OS" in r_js.text


@pytest.mark.asyncio
async def test_atendimento_mobile_and_pwa_preserved(client):
    """Acesso ao multiatendimento mobile e arquivos PWA (sw.js, manifest.json) preservados."""
    r_atend_redir = await client.get("/atendimento", follow_redirects=False)
    assert r_atend_redir.status_code == 301
    assert r_atend_redir.headers["location"] == "/atendimento.html"

    r_atend = await client.get("/atendimento.html")
    assert r_atend.status_code == 200
    assert "Multiatendimento" in r_atend.text

    r_sw = await client.get("/sw.js")
    assert r_sw.status_code == 200
    assert "javascript" in r_sw.headers.get("content-type", "")

    r_manifest = await client.get("/manifest.json")
    assert r_manifest.status_code == 200
    assert "json" in r_manifest.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_portal_backwards_compatibility(client):
    """Requisições para /portal/* devem redirecionar ou servir assets sem quebrar."""
    r_portal = await client.get("/portal", follow_redirects=False)
    assert r_portal.status_code == 301
    assert r_portal.headers["location"] == "/"

    r_portal_slash = await client.get("/portal/", follow_redirects=False)
    assert r_portal_slash.status_code == 301
    assert r_portal_slash.headers["location"] == "/"

    r_subpage = await client.get("/portal/estoque.html", follow_redirects=False)
    assert r_subpage.status_code == 301
    assert r_subpage.headers["location"] == "/estoque.html"

    # Assets legados /portal/assets/* devem servir 200 direto (para stores.json logos e fixtures)
    r_compat_asset = await client.get("/portal/assets/logo.png")
    assert r_compat_asset.status_code == 200
