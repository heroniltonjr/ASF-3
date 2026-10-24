"""Testes automatizados para Story 3.8:
Remoção do item de menu "Equipe do Shopping" (team) para os perfis Shopping e Gestor.
"""
import re
from pathlib import Path
import pytest


APP_JS_PATH = Path(__file__).resolve().parent.parent / "app.js"
INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"


def test_app_js_role_labels_team_removed_from_shopping_and_gestor():
    """Valida que o item team (Equipe do Shopping) foi removido
    das views e navegações dos perfis 'shopping' e 'gestor' em app.js,
    mantendo-se apenas para 'lojista' (Minha equipe).
    """
    assert APP_JS_PATH.exists(), "app.js deve existir"
    content = APP_JS_PATH.read_text(encoding="utf-8")

    # Extrai o bloco de ROLE_LABELS
    role_labels_match = re.search(r"const ROLE_LABELS = ({[\s\S]+?});\s*\n\s*const STAGES", content)
    assert role_labels_match, "ROLE_LABELS deve ser declarado em app.js"
    block = role_labels_match.group(1)

    # 1. Verifica shopping: allowedViews NÃO deve conter "team" e nav NÃO deve conter "Equipe do Shopping"
    shopping_match = re.search(r"shopping:\s*{([\s\S]+?)},\s*gestor:", block)
    assert shopping_match, "Perfil shopping deve estar presente antes de gestor"
    shopping_content = shopping_match.group(1)

    assert "Equipe do Shopping" not in shopping_content, "shopping não pode ter o texto 'Equipe do Shopping'"
    assert '"team"' not in shopping_content and "'team'" not in shopping_content, (
        "shopping não pode ter 'team' em allowedViews nem em nav"
    )

    # 2. Verifica gestor: allowedViews NÃO deve conter "team" e nav NÃO deve conter "Equipe do Shopping"
    gestor_match = re.search(r"gestor:\s*{([\s\S]+?)},\s*lojista:", block)
    assert gestor_match, "Perfil gestor deve estar presente antes de lojista"
    gestor_content = gestor_match.group(1)

    assert "Equipe do Shopping" not in gestor_content, "gestor não pode ter o texto 'Equipe do Shopping'"
    assert '"team"' not in gestor_content and "'team'" not in gestor_content, (
        "gestor não pode ter 'team' em allowedViews nem em nav"
    )

    # 3. Verifica lojista: DEVE manter "team" em nav ("Minha equipe") e allowedViews
    lojista_match = re.search(r"lojista:\s*{([\s\S]+?)}\s*$", block)
    assert lojista_match, "Perfil lojista deve estar presente"
    lojista_content = lojista_match.group(1)

    assert "Minha equipe" in lojista_content, "lojista deve manter 'Minha equipe' no nav"
    assert '"team"' in lojista_content or "'team'" in lojista_content, "lojista deve manter 'team' em allowedViews"


def test_index_html_cache_busting_v1_9():
    """Valida que index.html aponta para a versão com cache busting (>= 1.9)."""
    assert INDEX_HTML_PATH.exists()
    content = INDEX_HTML_PATH.read_text(encoding="utf-8")
    assert re.search(r'src="app\.js\?v=(1\.9|[2-9]\.\d+)"', content), "index.html deve conter app.js com cache busting >= 1.9"


@pytest.mark.asyncio
async def test_team_endpoint_accessible(as_shopping, as_lojista, as_master):
    """Garante que a rota de dashboard/team continue íntegra no backend."""
    r_shop = await as_shopping.get("/api/dashboard/team")
    assert r_shop.status_code == 200
    assert "team" in r_shop.json()

    r_loj = await as_lojista.get("/api/dashboard/team")
    assert r_loj.status_code == 200
    assert "team" in r_loj.json()

    r_mst = await as_master.get("/api/dashboard/team")
    assert r_mst.status_code == 200
    assert "team" in r_mst.json()
