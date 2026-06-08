"""SDR de IA via OpenRouter: gera a resposta do agente a partir do histórico."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o SDR (Sales Development Representative) do Auto Shopping Formula,
respondendo via WhatsApp em nome de uma loja parceira.

Sua missão:
- Receber o lead com cordialidade, identificar o veículo de interesse e a urgência.
- Coletar 3 dados antes de qualificar: orçamento, forma de pagamento (à vista/financiado),
  e se possui veículo para troca.
- Ser objetivo, em português brasileiro coloquial, sem emojis em excesso (no máximo um).
- Quando você tiver coletado todas as informações ou se o cliente quiser negociar preços,
  entrada, financiamento ou avaliação de troca, VOCÊ DEVE TRANSFERIR PARA UM HUMANO.
- IMPORTANTE: Para transferir para um humano e qualificar o lead, encerre sua mensagem 
  exata e obrigatoriamente com a tag [TRANSFERIR]. Exemplo: "Um momento, vou chamar um 
  de nossos consultores para ver essa negociação com você. [TRANSFERIR]"

Mensagens curtas, respeitando o ritmo do WhatsApp (até 3 frases por turno).
Nunca prometa preço, prazo ou condição que não esteja no contexto.
"""


def _format_history(messages: list[dict]) -> list[dict]:
    """Converte mensagens do DB para o formato chat de OpenRouter."""
    out = []
    for m in messages:
        sender = m.get("sender")
        if sender == "agent":
            out.append({"role": "assistant", "content": m["body"]})
        elif sender == "lead":
            out.append({"role": "user", "content": m["body"]})
        elif sender == "human":
            # Atendente humano se manifestou — registra como assistant
            out.append({"role": "assistant", "content": m["body"]})
    return out


async def generate_reply(
    *,
    store_name: str,
    store_sdr_prompt: Optional[str] = None,
    intent: Optional[str],
    history: list[dict],
    incoming_text: str,
) -> Optional[tuple[str, dict]]:
    """Retorna `(texto, usage)` ou `None` se SDR não configurado/erro.

    `usage` é um dict com `prompt_tokens`, `completion_tokens`, `total_tokens`,
    `cost_usd` (quando disponível) e `model`. Os campos podem ser 0 se o
    provedor não devolver telemetria.
    """
    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY ausente — SDR desativado.")
        return None

    context = (
        f"Loja parceira: {store_name}.\n"
        f"Interesse declarado: {intent or 'ainda não identificado'}."
    )
    
    final_prompt = SYSTEM_PROMPT
    if store_sdr_prompt:
        final_prompt += f"\n\nINSTRUÇÕES ESPECÍFICAS DA LOJA:\n{store_sdr_prompt}"

    messages = [
        {"role": "system", "content": final_prompt},
        {"role": "system", "content": context},
        *_format_history(history),
        {"role": "user", "content": incoming_text},
    ]

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": 1,   # reasoning models exigem temperature=1
        "max_tokens": 1500,  # reasoning models consomem tokens no pensamento interno
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.public_base_url,
        "X-Title": "Formula OS SDR",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.exception("Falha de rede ao chamar OpenRouter: %s", exc)
        return None

    if r.status_code >= 400:
        logger.error("OpenRouter %s: %s", r.status_code, r.text[:400])
        return None

    data = r.json()
    try:
        choice = data["choices"][0]
        content = choice["message"].get("content")
        finish_reason = choice.get("finish_reason")

        if content is None:
            # Modelos de raciocínio (gpt-5-mini, o1, etc.) podem retornar content=None
            # quando esgotam max_tokens no pensamento interno.
            logger.error(
                "OpenRouter: content=None (finish_reason=%s). "
                "Aumente max_tokens ou troque o modelo. Resposta: %s",
                finish_reason, str(data)[:300],
            )
            return None

        text = content.strip()
        if not text:
            logger.warning("OpenRouter retornou texto vazio (finish_reason=%s).", finish_reason)
            return None
    except (KeyError, IndexError, AttributeError):
        logger.error("OpenRouter respondeu em formato inesperado: %s", str(data)[:400])
        return None
    raw_usage = data.get("usage") or {}
    usage = {
        "model": data.get("model") or settings.openrouter_model,
        "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
        "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
        "total_tokens": int(raw_usage.get("total_tokens") or 0),
        # OpenRouter inclui `usage.cost` em USD na maior parte dos modelos.
        "cost_usd": float(raw_usage.get("cost") or 0),
    }
    return text, usage


async def evaluate_conversation(history: list[dict]) -> Optional[tuple[int, str]]:
    """
    Analisa a transcrição da conversa e retorna uma tupla (nota, justificativa).
    A nota varia de 0 a 100. Retorna None se falhar.
    """
    if not settings.openrouter_api_key:
        return None

    # Filtra apenas mensagens do humano e do lead para avaliar a interação final
    # (ou pode avaliar o contexto todo para ver se o SDR fez um bom trabalho tbm, mas o foco é a qualidade).
    transcript = "\\n".join([f"{m.get('sender')}: {m.get('body')}" for m in history])

    prompt = (
        "Avalie o atendimento do vendedor humano nesta conversa.\\n"
        "Critérios: cordialidade, velocidade (se possível inferir), clareza e poder de persuasão.\\n\\n"
        "Responda EXATAMENTE neste formato JSON, sem crases:\\n"
        "{\\n"
        '  "score": <numero de 0 a 100>,\\n'
        '  "analysis": "<breve justificativa em 2 frases>"\\n'
        "}\\n\\n"
        "Transcrição:\\n"
        f"{transcript}"
    )

    messages = [
        {"role": "system", "content": "Você é um auditor de qualidade de atendimento automotivo. Seja rigoroso, porém justo."},
        {"role": "user", "content": prompt},
    ]

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.public_base_url,
        "X-Title": "Formula OS QA",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.error("QA OpenRouter %s: %s", r.status_code, r.text[:400])
                return None
            data = r.json()
            content = data["choices"][0]["message"].get("content")
            if not content: return None
            
            import json
            result = json.loads(content)
            return int(result.get("score", 0)), result.get("analysis", "")
    except Exception as exc:
        logger.exception("Falha ao avaliar conversa: %s", exc)
        return None
