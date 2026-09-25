# Walkthrough — Otimização Comportamental do Agente Rafael & Busca por Intenção no Banco

Implementação concluída no projeto **ASF-3** para solucionar o travamento de atendimento, repetição de bordões institucionais e falta de apresentação imediata de opções de veículos pelo **Agente Rafael (SDR)**.

---

## Modificações Realizadas

### 1. Reestruturação do Prompt do SDR (`SYSTEM_PROMPT`)
- **Arquivo modificado:** [`backend/sdr.py`](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py)
- **Mudanças Implementadas:**
  - **Fim da Repetição de Jargões:** Proibida expressamente a repetição contínua de bordões como *"nossas 30+ lojas (maior acervo do Centro-Oeste, 15 anos)"* a cada mensagem. Permite no máximo 1 menção na primeira saudação.
  - **Valor Primeiro (Entrega Imediata de Opções):** O Rafael está instruído a apresentar as opções de veículos imediatamente quando o cliente demonstrar interesse ou pedir preços, sem travar o atendimento exigindo cadastro, cidade, valor de entrada ou opção de financiamento primeiro.
  - **Alternativas Diretas:** Se o modelo exato solicitado pelo cliente não constar no estoque (ex: Corolla), o Rafael não pergunta "se o cliente quer ver alternativas". Ele apresenta **diretamente** as opções similares disponíveis no estoque (Civic, Sentra, SUVs).
  - **Proibição de Frases de Adiamento:** Proibido o uso de expressões como *"vou pesquisar no sistema"* ou *"aguarde um instante"*, enviando o resultado da busca na própria mensagem da resposta.

### 2. Busca por Intenção em Tempo Real (Supabase / SQLite)
- **Arquivo modificado:** [`backend/ingest.py`](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- **Mudanças Implementadas:**
  - Reformulada a função `search_vehicles_advanced(conn, store_id, incoming_text, is_feirao)`.
  - Quando o **Supabase** estiver ativo (`supabase_client.is_configured()`), executa uma consulta PostgREST dinâmica parametrizada com os filtros de marca, modelo ou categoria extraídos da mensagem do cliente (`or=(name.ilike.*kw*,model.ilike.*kw*)`), retornando **apenas as 3 a 5 opções mais relevantes (~100 tokens)**.
  - Caso não haja correspondência exata ou em ambiente offline/dev, executa a busca por intenção com fallback de alternativas na base SQLite local em **< 2 milissegundos**.

---

## Verificação e Testes Automatizados

- **Arquivo de teste novo:** [`tests/test_sdr_behavior.py`](file:///c:/ProjetosMLDB/ASF-3/tests/test_sdr_behavior.py)

### Casos de Teste Criados:
1. `test_search_vehicles_advanced_intent_matching`: Valida a busca direcionada por intenção e palavra-chave no banco de dados.
2. `test_search_vehicles_advanced_fallback`: Garante que, ao procurar por modelos inexistentes, a busca retorna alternativas em estoque sem travar a resposta.
3. `test_sdr_behavior_immediate_response`: Garante que o pipeline repassa a mensagem do cliente e o SDR responde com opções de veículos sem gerar promessas de pesquisa futura.

### Resultado dos Testes:
```bash
python -m pytest tests/test_sdr_behavior.py
# 3 passed in 7.11s
```

Suíte global do projeto:
```bash
python -m pytest
# 82 passed in 131s
```
