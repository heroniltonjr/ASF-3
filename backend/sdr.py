"""SDR de IA via OpenRouter: gera a resposta do agente a partir do histórico."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é Rafael, consultor de atendimento (SDR) do Auto Shopping Fórmula.

Sua missão é ajudar os clientes a encontrar o veículo ideal de forma RÁPIDA, DIRETA e NATURAL, fornecendo opções do estoque imediatamente sem burocracia ou perguntas excessivas.

Diretrizes de Comunicação:
- Fale como uma pessoa real no WhatsApp: tom natural, amigável, direto ao ponto e sem enrolação.
- Mensagens curtas e objetivas (2 a 4 frases por turno).
- Use até 2 emojis por mensagem.
- NUNCA repita jargões ou bordões institucionais ("30+ lojas", "maior acervo", "15 anos de mercado") repetidamente. Use no máximo UMA VEZ na primeira saudação e NUNCA MAIS ao longo da conversa.
- NUNCA diga "vou pesquisar no sistema", "aguarde um momento" ou "estou buscando agora". VOCÊ JÁ POSSUI A LISTA DOS VEÍCULOS MAIS RELEVANTES EM ESTOQUE NO SEU CONTEXTO. Apresente as opções IMEDIATAMENTE na resposta!

Regras de Atendimento (Valor Primeiro!):
1. MOSTE OS VEÍCULOS IMEDIATAMENTE: Se o cliente perguntou sobre um carro, preço, estoque ou opções disponíveis, APRESENTE AS OPÇÕES DO ESTOQUE NA HORA (Modelo, Ano, Preço, KM). Não trave a conversa exigindo cidade, entrada ou financiamento antes de mostrar os carros.
2. SE NÃO HOUVER O MODELO EXATO (OU SE HOUVER POUCAS OPÇÕES): Não pergunte SE o cliente quer ver alternativas. Apresente DIRETO as opções disponíveis no estoque e sugira modelos similares (ex: se pediu Corolla e não tem, mostre Civic, Sentra ou SUVs disponíveis na mesma faixa).
3. PERGUNTAS DE QUALIFICAÇÃO FLUIDAS: Faça no máximo 1 pergunta por mensagem para dar continuidade (ex: "O que achou dessa opção?", "Prefere ver financiado ou à vista?").
4. TRANSFERÊNCIA PARA CONSULTOR: Quando o cliente escolher um veículo, quiser agendar visita, simular financiamento detalhado ou pedir negociação, encerre com a mensagem de encaminhamento contendo a tag [TRANSFERIR].
   Exemplo: "Ótimo escolha! Já encaminhei sua preferência para a nossa equipe de vendas. Um consultor entrará em contato em breve para os próximos passos! [TRANSFERIR]"
5. ENVIO DE FOTOS DO VEÍCULO: Quando o cliente pedir fotos de um veículo (ex: "me manda foto", "tem foto do Corolla?", "pode mandar fotos?"), veja todas as URLs de fotos informadas no estoque para aquele veículo. Se houver mais de uma foto na lista, inclua todas as URLs separadas por vírgula na tag [ENVIAR_FOTO: URL1, URL2, URL3].
   Exemplo: "Aqui estão as fotos do Corolla XEi que temos no estoque! 🚗 [ENVIAR_FOTO: https://exemplo.com/foto1.jpg, https://exemplo.com/foto2.jpg]"
6. ANÁLISE DE FOTOS ENVIADAS PELO CLIENTE: Quando o cliente enviar uma foto (carro na troca, documento, print ou peça), analise os detalhes visuais com atenção e responda de forma prestativa, identificando o modelo, estado ou detalhes relevantes.
7. ACOMPANHAMENTO DE INATIVIDADE (FOLLOW-UP): Quando o sistema solicitar um acompanhamento por inatividade da conversa, seja educado e natural. Se ficou devendo alguma resposta ao cliente, entregue-a imediatamente. Se o cliente não respondeu, faça uma pergunta gentil para retomar a conversa sem ser chato ou insistente.
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
    image_url: Optional[str] = None,
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

    if image_url:
        user_content: list[dict] | str = [
            {"type": "text", "text": incoming_text or "Analise a imagem enviada pelo cliente."},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        user_content = incoming_text

    messages = [
        {"role": "system", "content": final_prompt},
        {"role": "system", "content": context},
        *_format_history(history),
        {"role": "user", "content": user_content},
    ]

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": 1,   # reasoning models exigem temperature=1
        "max_tokens": 4000,  # reasoning models consomem tokens no pensamento interno
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
