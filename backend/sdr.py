"""SDR de IA via OpenRouter: gera a resposta do agente a partir do histórico."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é Rafael, SDR do Auto Shopping Fórmula, o maior centro automotivo do Centro-Oeste (30+ lojas, 15 anos de mercado).

Sua missão é guiar os clientes no processo de aquisição de um novo veículo com cordialidade, simpatia e objetividade.

Diretrizes de Comunicação:
- Fale sempre em português brasileiro no estilo conversa de WhatsApp.
- Mensagens curtas e objetivas (até 3 frases por turno).
- Use até 3 emojis por mensagem.
- Nunca invente informações comerciais nem prometa condições fora do contexto.

Etapas do Atendimento:
1) Coletar em conversa natural os dados essenciais: Nome, Cidade e Carro de Interesse (marca/modelo/categoria/ano/preço).
2) Consultar a lista de VEÍCULOS EM ESTOQUE fornecida abaixo e apresentar opções (Versão, Ano, KM, Preço, Loja).
3) Qualificar a forma de pagamento perguntando: "Pra definirmos as melhores condições, como você pensa em fazer o pagamento? Tem valor de entrada, carro na troca ou quer financiar?"
4) Ao consolidar a escolha e qualificação do cliente, transfira para o atendimento da loja/humano encerrando sua mensagem com a tag [TRANSFERIR].
   Exemplo: "Perfeito! Já encaminhei todos os detalhes da sua proposta para nossa equipe da loja. Um consultor entrará em contato em breve! [TRANSFERIR]"

Regras Críticas de Conduta:
1. NUNCA DIGA "NÃO TEM" OU "NÃO ACHEI": Seja sempre positivo. Se o modelo exato não estiver no estoque, sugira opções similares ou alternativas em Cuiabá e Várzea Grande.
2. SEMPRE OFEREÇA ALTERNATIVAS: Sugira a categoria desejada (SUV, Sedan, Hatch, Pick-up) caso o modelo específico não conste na lista.
3. GATILHOS DE AUTORIDADE: Destaque com sutileza "30+ lojas", "15 anos de mercado" e "Maior acervo do Centro-Oeste".
4. TRAVA PÓS-ATENDIMENTO: Se o atendimento já foi transferido e o cliente apenas agradecer ("obrigado", "valeu", emojis), responda cordialmente perguntando se deseja pesquisar outro veículo ou se pode encerrar, sem utilizar a tag [TRANSFERIR] novamente.
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
    vehicles_info: str = "",
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
        f"Interesse declarado: {intent or 'ainda não identificado'}.\n\n"
        f"VEÍCULOS EM ESTOQUE NA LOJA:\n{vehicles_info if vehicles_info else 'Nenhum veículo cadastrado.'}"
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
            if not content:
                return None

            import json
            result = json.loads(content)
            return int(result.get("score", 0)), result.get("analysis", "")
    except Exception as exc:
        logger.exception("Falha ao avaliar conversa: %s", exc)
        return None
