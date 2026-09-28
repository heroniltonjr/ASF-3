"""Testes automatizados para Story 3.7:
Remoção do item de menu Monetização (billing) para os perfis Shopping e Gestor.
"""
import re
from pathlib import Path
import pytest


APP_JS_PATH = Path(__file__).resolve().parent.parent / "app.js"
INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"


def test_app_js_role_labels_monetizacao_removed():
    """Valida que o item billing (Monetização) foi completamente removido
    das views e navegações dos perfis 'shopping' e 'gestor' em app.js,
    mantendo-se apenas para 'master'.
    """
    assert APP_JS_PATH.exists(), "app.js deve existir"
    content = APP_JS_PATH.read_text(encoding="utf-8")

    # Extrai o bloco de ROLE_LABELS
    role_labels_match = re.search(r"const ROLE_LABELS = ({[\s\S]+?});\s*\n\s*const STAGES", content)
    assert role_labels_match, "ROLE_LABELS deve ser declarado em app.js"
    block = role_labels_match.group(1)

    # 1. Verifica shopping: allowedViews NÃO deve conter "billing"
    shopping_match = re.search(r"shopping:\s*{([\s\S]+?)},\s*gestor:", block)
    assert shopping_match, "Perfil shopping deve estar presente antes de gestor"
    shopping_content = shopping_match.group(1)

    assert "Monetização" not in shopping_content, "shopping não pode ter o texto 'Monetização'"
    assert '"billing"' not in shopping_content and "'billing'" not in shopping_content, (
        "shopping não pode ter 'billing' em allowedViews nem em nav"
    )

    # 2. Verifica gestor: allowedViews NÃO deve conter "billing"
    gestor_match = re.search(r"gestor:\s*{([\s\S]+?)},\s*lojista:", block)
    assert gestor_match, "Perfil gestor deve estar presente antes de lojista"
    gestor_content = gestor_match.group(1)

    assert "Monetização" not in gestor_content, "gestor não pode ter o texto 'Monetização'"
    assert '"billing"' not in gestor_content and "'billing'" not in gestor_content, (
        "gestor não pode ter 'billing' em allowedViews nem em nav"
    )

    # 3. Verifica master: deve manter "billing" em nav e allowedViews
    master_match = re.search(r"master:\s*{([\s\S]+?)},\s*shopping:", block)
    assert master_match, "Perfil master deve estar presente"
    master_content = master_match.group(1)
    assert "billing" in master_content, "master deve manter acesso a billing"


def test_index_html_cache_busting():
    """Valida que index.html aponta para a versão atualizada app.js?v=1.8."""
    assert INDEX_HTML_PATH.exists()
    content = INDEX_HTML_PATH.read_text(encoding="utf-8")
    assert 'src="app.js?v=1.8"' in content, "index.html deve conter app.js?v=1.8"


@pytest.mark.asyncio
async def test_billing_endpoint_permissions(as_master, as_shopping, as_lojista):
    """Valida integridade do backend para o endpoint de billing."""
    # Master acessa com sucesso
    r_master = await as_master.get("/api/billing/summary")
    assert r_master.status_code == 200
    assert "total" in r_master.json()

    # Shopping acessa com sucesso (dados de tenant)
    r_shopping = await as_shopping.get("/api/billing/summary")
    assert r_shopping.status_code == 200

    # Lojista acessa com sucesso (dados da sua loja)
    r_lojista = await as_lojista.get("/api/billing/summary")
    assert r_lojista.status_code == 200
