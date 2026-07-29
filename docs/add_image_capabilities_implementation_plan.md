# Implementation Plan — Processamento e Envio de Imagens pelo Agente Rafael (Multimodal / Vision)

Habilitar o **Agente Rafael (SDR de IA)** no projeto **ASF-3** a:
1. **Interpretar Imagens Recebidas:** Analisar fotos enviadas pelos clientes (ex: fotos de veículos para avaliação de troca, documento, prints ou peças) usando modelos Multimodais/Vision da OpenRouter.
2. **Enviar Fotos de Veículos Solicitadas:** Enviar automaticamente fotos reais dos veículos do estoque via WhatsApp (Z-API / Meta / Evolution) quando o cliente solicitar na conversa.

## User Review Required

> [!IMPORTANT]
> - Para a interpretação de imagens recebidas dos clientes, a rota do OpenRouter passará blocos de conteúdo `image_url` compatíveis com a especificação Vision. Certifique-se de que o modelo no `.env` (`OPENROUTER_MODEL`) suporte visão (ex: `openai/gpt-5-mini`, `openai/gpt-4o-mini`, `anthropic/claude-3.5-haiku` ou `google/gemini-2.5-flash`).
> - Para o envio de fotos, o sistema extrairá a URL da foto do veículo cadastrado no banco (`vehicles.image_path`). O Agente Rafael usará a tag interna `[ENVIAR_FOTO: URL_DA_FOTO]` para acionar o envio nativo de imagem via provider (`send_image`).

## Proposed Changes

### Backend — Adapters, SDR e Ingest Pipeline

#### [MODIFY] [backend/whatsapp/zapi.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/zapi.py)
- Atualizar `parse_inbound` para extrair mensagens do tipo imagem (`image`, `imageUrl`, `imageMessage`).
- Armazenar `_is_image: True` e `_image_url: URL` no campo `raw` da `InboundMessage`.

#### [MODIFY] [backend/sdr.py](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py)
- **Instruções do Sistema (`SYSTEM_PROMPT`):** Adicionar regras para o Rafael interpretar fotos recebidas e incluir a tag `[ENVIAR_FOTO: URL]` caso o cliente solicite fotos de um veículo disponível no estoque.
- **Suporte Multimodal:** Atualizar `generate_reply` para aceitar o parâmetro opcional `image_url: Optional[str]`. Quando presente, envia a estrutura de payload multimodal `[{"type": "text", ...}, {"type": "image_url", ...}]` para o OpenRouter.

#### [MODIFY] [backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- Incluir o campo de foto (`image_path`) nas listagens formatadas de `search_vehicles_advanced()`.
- No `handle_inbound()`:
  1. Se a mensagem recebida for uma imagem (`_is_image`), repassar a `_image_url` ao `sdr.generate_reply()`.
  2. Ao receber a resposta do SDR com a tag `[ENVIAR_FOTO: URL]`, remover a tag do texto da mensagem e invocar `provider.send_image(to_number, image_url, caption)` para enviar a foto real no WhatsApp do cliente.

---

### Testes Automatizados

#### [NEW] [tests/test_image_support.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_image_support.py)
- Teste unitário do parsing de webhooks de imagem no `ZApiProvider`.
- Teste de integração do SDR interpretando imagem recebida (Vision).
- Teste do envio automatizado de fotos de veículos pelo Agente Rafael quando solicitado pelo lead.

## Verification Plan

### Automated Tests
- Executar `python -m pytest tests/test_image_support.py`
- Executar `python -m pytest` para verificar regressão em toda a suíte.

### Manual Verification
- Enviar payload simulado de imagem recebida e checar a resposta descritiva da IA.
- Enviar mensagem simulada pedindo foto ("Pode me mandar foto do Corolla?") e verificar a chamada do `send_image`.
