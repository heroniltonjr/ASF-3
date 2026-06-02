"""Testes para conversas e suas tags no endpoint REST."""
from __future__ import annotations


async def test_conversation_tags_retrieval(as_master):
    # 1. Cria uma tag de teste para a loja 2 (onde estão os dados de seed do multiatendimento)
    r = await as_master.post("/api/tags", json={
        "name": "Interesse Alto",
        "color": "#e60023",
        "scope": "personal",
        "store_id": 2
    })
    assert r.status_code == 201
    tag = r.json()["tag"]
    tag_id = tag["id"]

    # 2. Obtém a lista de conversas
    r = await as_master.get("/api/conversations")
    assert r.status_code == 200
    convs = r.json()["conversations"]
    assert len(convs) > 0

    # Todas as conversas devem iniciar sem a tag associada
    target_conv = next(c for c in convs if c["lead_id"])
    assert all(t["id"] != tag_id for t in target_conv["_tags"])

    # 3. Associa a tag ao lead
    r = await as_master.post(f"/api/leads/{target_conv['lead_id']}/tags/{tag_id}")
    assert r.status_code == 201

    # 4. Busca a lista novamente e valida que a tag agora aparece na conversa
    r = await as_master.get("/api/conversations")
    convs_updated = r.json()["conversations"]
    target_conv_updated = next(c for c in convs_updated if c["id"] == target_conv["id"])
    assert any(t["id"] == tag_id and t["name"] == "Interesse Alto" and t["color"] == "#e60023" for t in target_conv_updated["_tags"])

    # 5. Valida o detalhe da conversa individual (/conversations/{cid})
    r = await as_master.get(f"/api/conversations/{target_conv['id']}")
    assert r.status_code == 200
    conv_detail = r.json()["conversation"]
    assert any(t["id"] == tag_id for t in conv_detail["_tags"])

    # 6. Remove a tag e valida que foi desassociada
    r = await as_master.delete(f"/api/leads/{target_conv['lead_id']}/tags/{tag_id}")
    assert r.status_code == 204

    r = await as_master.get(f"/api/conversations/{target_conv['id']}")
    conv_detail_removed = r.json()["conversation"]
    assert all(t["id"] != tag_id for t in conv_detail_removed["_tags"])


async def test_media_upload(as_master):
    files = {"file": ("test.jpg", b"fake_image_content", "image/jpeg")}
    r = await as_master.post("/api/media/upload", files=files)
    assert r.status_code == 200
    data = r.json()
    assert "url" in data
    assert data["kind"] == "image"
    assert data["content_type"] == "image/jpeg"

    # Tenta baixar o arquivo de volta
    url = data["url"]
    r_get = await as_master.get(url)
    assert r_get.status_code == 200
    assert r_get.content == b"fake_image_content"
