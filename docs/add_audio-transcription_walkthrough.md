# Walkthrough — Transcrição de Áudio com OpenAI Whisper no Agente Rafael (SDR)

Implementação concluída para capacitar o **Agente Rafael** a receber mensagens de áudio/voz do WhatsApp, transcrevê-las automaticamente usando a API do **OpenAI Whisper** e responder contextualmente de forma integrada.

---

## Modificações Realizadas

### 1. Novo Módulo STT (Speech-To-Text)
- **Arquivo novo:** [`backend/stt.py`](file:///c:/ProjetosMLDB/ASF-3/backend/stt.py)
- **Descrição:** Módulo assíncrono que realiza o download da mídia de áudio `.ogg` e efetua a chamada HTTP REST para o endpoint `https://api.openai.com/v1/audio/transcriptions` da OpenAI usando o modelo `whisper-1` (que executa a engine Whisper v3 da OpenAI).

```python
async def transcribe_audio_url(audio_url: str) -> Optional[str]:
    api_key = (os.getenv("OPENAI_API_KEY") or settings.openai_api_key or "").strip()
    if not api_key or not audio_url:
        return None
    # Executa o download da mídia e a chamada para api.openai.com/v1/audio/transcriptions
```

### 2. Configurações Globais
- **Arquivos modificados:** [`backend/settings.py`](file:///c:/ProjetosMLDB/ASF-3/backend/settings.py) e [`.env.example`](file:///c:/ProjetosMLDB/ASF-3/.env.example)
- **Campos adicionados:**
  - `OPENAI_API_KEY`: Chave da API da OpenAI (`sk-proj-...`).
  - `STT_MODEL`: Modelo de transcrição (padrão `"whisper-1"`).

### 3. Extração de Áudio no Z-API Provider
- **Arquivo modificado:** [`backend/whatsapp/zapi.py`](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/zapi.py)
- **Descrição:** O método `parse_inbound` foi atualizado para identificar payloads contendo mídia de áudio (`audio`, `audioUrl` ou `audioMessage`) e anexar as flags `_is_audio: True` e `_audio_url` no dicionário da `InboundMessage`.

### 4. Orquestração no Ingest Pipeline
- **Arquivo modificado:** [`backend/ingest.py`](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- **Descrição:** No método `handle_inbound`, ao detectar `_is_audio`, o pipeline aciona `stt.transcribe_audio_url(_audio_url)` e formata o corpo da mensagem com o prefixo `[🎙️ Áudio transcrito]: "..."`. A mensagem transcrita é gravada no banco e enviada ao Agente Rafael (`sdr.generate_reply`) para a geração da resposta.

---

## Verificação e Testes Automatizados

- **Arquivo de teste novo:** [`tests/test_stt_audio.py`](file:///c:/ProjetosMLDB/ASF-3/tests/test_stt_audio.py)

### Casos de Teste Desenvolvidos:
1. `test_stt_transcribe_audio_url_success`: Moca as chamadas HTTP para a OpenAI e confirma o retorno do texto transcrito.
2. `test_stt_no_api_key`: Garante tratamento elegante e sem exceções caso `OPENAI_API_KEY` esteja ausente.
3. `test_zapi_audio_inbound_integration`: Testa o fluxo end-to-end de recebimento de áudio via Z-API, transcrição, persistência formatada e resposta automatizada da IA.

### Resultado da Suíte de Testes:
```bash
python -m pytest tests/test_stt_audio.py
# 3 passed in 3.36s
```

Suíte global do projeto:
```bash
python -m pytest
# 74 passed in 118s
```
