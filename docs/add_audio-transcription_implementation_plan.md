# Implementation Plan — Recebimento e Transcrição de Áudio com OpenAI Whisper (STT)

Habilitar o Agente Rafael (SDR de IA) a receber mensagens de voz/áudio enviadas via WhatsApp (Z-API / Meta / Evolution), transcrevê-las automaticamente usando o OpenAI Whisper (`whisper-1`) e responder de forma contextual ao lead.

## User Review Required

> [!IMPORTANT]
> - O serviço de transcrição usará o endpoint oficial da OpenAI (`https://api.openai.com/v1/audio/transcriptions`) com o modelo `whisper-1` (que executa a engine Whisper v3 da OpenAI).
> - As chaves necessárias no arquivo `.env` serão `OPENAI_API_KEY` e a opção configurável `STT_MODEL=whisper-1`.
> - Se a API da OpenAI falhar ou não estiver configurada, o sistema salvará a mensagem como `[Áudio sem transcrição disponível]` no histórico sem travar o pipeline.

## Proposed Changes

### Backend — Módulo STT, Settings e WhatsApp Provider

#### [NEW] [stt.py](file:///c:/ProjetosMLDB/ASF-3/backend/stt.py)
- Módulo assíncrono para download da mídia de áudio e chamada para a API `v1/audio/transcriptions` da OpenAI usando `httpx`.
- Tratamento de exceções e timeout com fallback gracioso.

#### [MODIFY] [settings.py](file:///c:/ProjetosMLDB/ASF-3/backend/settings.py)
- Adicionar as configurações `openai_api_key` e `stt_model` (default `"whisper-1"`).

#### [MODIFY] [zapi.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/zapi.py)
- Atualizar `parse_inbound` para detectar payloads de áudio (`audio`, `audioUrl`, `audioMessage`).
- Marcar a `InboundMessage` com a flag `_is_audio` e a URL da mídia `_audio_url` no campo `raw`.

#### [MODIFY] [ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- No `handle_inbound`, detectar mensagens de áudio (`_is_audio=True`), invocar a transcrição via `stt.transcribe_audio_url(_audio_url)`.
- Atualizar o corpo da mensagem com a formatação `[🎙️ Áudio transcrito]: "<texto_transcrito>"`.
- Persistir a mensagem transcrita e passar a transcrição normalmente para o Agente Rafael (`sdr.generate_reply`).

#### [MODIFY] [.env.example](file:///c:/ProjetosMLDB/ASF-3/.env.example)
- Documentar as variáveis `OPENAI_API_KEY` e `STT_MODEL=whisper-1`.

---

### Testes Automatizados

#### [NEW] [test_stt_audio.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_stt_audio.py)
- Testes unitários para o módulo `stt.py` (com mocks da API da OpenAI).
- Teste de ingestão de áudio via Z-API garantindo transcrição, persistência e resposta do Agente Rafael.

## Verification Plan

### Automated Tests
- Executar `python -m pytest tests/test_stt_audio.py`
- Executar `python -m pytest` para verificar regressão em toda a suíte de testes.

### Manual Verification
- Enviar payload simulado de mensagem de áudio e verificar que a conversa no histórico reflete `[🎙️ Áudio transcrito]: ...` e o SDR responde adequadamente.
