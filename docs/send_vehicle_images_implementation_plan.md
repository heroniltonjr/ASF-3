# Implementation Plan — Suporte ao Envio de Múltiplas Fotos (Campo `pictures`)

Evolução do projeto **ASF-3** para permitir que o **Agente Rafael (SDR)** envie não apenas a imagem principal (`main_image` / `image_path`), mas também a galeria completa de fotos (`pictures`) cadastradas para o veículo.

## User Review Required

> [!IMPORTANT]
> **Como funcionará o envio da galeria de fotos (`pictures`):**
> 1. **Captura do Campo `pictures`:** Ao consultar o veículo no Supabase (ou banco local), o sistema extrairá a lista de URLs da galeria `pictures` além da foto principal.
> 2. **Formatação pelo SDR:** Quando o cliente pedir fotos do veículo, o Rafael incluirá as URLs disponíveis na tag: `[ENVIAR_FOTO: URL1, URL2, URL3]`.
> 3. **Disparo Sequencial no WhatsApp:** O sistema enviará a primeira foto com o texto explicativo da mensagem como legenda, e em seguida enviará as fotos adicionais da galeria sequencialmente para o WhatsApp do cliente.

## Proposed Changes

### Backend — SDR e Ingest

#### [MODIFY] [backend/sdr.py](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py)
- Atualizar a regra 5 do `SYSTEM_PROMPT` orientando o envio de múltiplas URLs de foto quando disponíveis no campo `pictures`.

#### [MODIFY] [backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- Adicionar helper `_extract_pictures` para normalizar URLs de `main_image` e `pictures`.
- Incluir a lista de fotos da galeria no retorno de `search_vehicles_advanced()`.
- Atualizar `handle_inbound` e `process_idle_followups` para parsing de múltiplas fotos em `[ENVIAR_FOTO: URL1, URL2]` e disparo sequencial via `provider.send_image()`.

---

### Testes Automatizados

#### [MODIFY] [tests/test_image_support.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_image_support.py)
- Teste para disparo de múltiplas fotos da galeria (`pictures`) em sequência.

## Verification Plan

### Automated Tests
- Executar `python -m pytest tests/test_image_support.py`
- Executar `python -m pytest` para garantir 100% de aprovação na suíte global.

### Manual Verification
- Solicitar fotos de um veículo com galeria e confirmar o recebimento de múltiplas fotos no WhatsApp.
