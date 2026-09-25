# Implementation Plan — Busca Direcionada por Intenção no Banco (RAG Leve) & Prompt Ágil do SDR

Abordagem otimizada para consulta de veículos no projeto **ASF-3**: em vez de enviar todo o acervo no prompt da IA (o que consumiria milhares de tokens por requisição), o sistema realiza uma **busca direcionada por intenção no banco SQLite em tempo real (< 2ms)** antes de chamar o modelo.

## User Review Required

> [!IMPORTANT]
> **Como funcionará a busca por intenção no banco de dados:**
> 1. **Busca Dinâmica em Tempo Real:** Quando o cliente envia uma mensagem (ex: *"Tem Corolla?"*, *"Procuro SUV até 100 mil"*), a função `search_vehicles_advanced` analisa o texto e executa uma query SQL parametrizada no SQLite buscando modelos, marcas ou categorias correspondentes.
> 2. **Fallback Automático de Alternativas:** Se a busca exata não retornar resultados para aquela loja (ex: a loja não tem Corolla), o algoritmo busca instantaneamente os veículos da mesma categoria/faixa de preço no acervo do Shopping (ex: Civic, Sentra, SUVs) e entrega **apenas as 3 a 5 melhores opções** ao Rafael.
> 3. **Consumo Mínimo de Tokens:** O prompt do Rafael receberá apenas 3 a 5 veículos altamente relevantes (~100 tokens), garantindo custo extremamente baixo e velocidade máxima na resposta.

## Proposed Changes

### Backend — Ingest e SDR Prompt

#### [MODIFY] [backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- **`search_vehicles_advanced(conn, store_id, incoming_text, is_feirao)`:**
  - Extração de palavras-chave (modelos, marcas, categorias, carroceria).
  - Consulta SQL direcionada na tabela `vehicles` (filtrando por status publicado e loja/shopping).
  - Algoritmo de fallback para alternativas similares caso o modelo desejado não exista.
  - Retorno limitado aos top 3 a 5 veículos relevantes.

#### [MODIFY] [backend/sdr.py](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py)
- **`SYSTEM_PROMPT`:**
  - Proibição estrita de repetição contínua de bordões institucionais (*"30+ lojas, 15 anos"*).
  - Regra de apresentação imediata dos veículos recebidos no contexto (sem travar pedindo cadastro/cidade).
  - Apresentação direta das alternativas retornadas pela busca sem perguntar *"posso buscar?"*.
  - Proibição de frases de adiamento como *"vou pesquisar no sistema"*.

---

### Testes Automatizados

#### [NEW] [tests/test_sdr_behavior.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_sdr_behavior.py)
- Teste unitário da busca por intenção em `search_vehicles_advanced` (busca exata, por categoria e fallback de alternativas).
- Teste de integração do SDR exibindo os veículos encontrados imediatamente no mesmo turno.

## Verification Plan

### Automated Tests
- Executar `python -m pytest tests/test_sdr_behavior.py`
- Executar `python -m pytest` para validar a suíte completa sem regressões.

### Manual Verification
- Testar no atendimento simulado mensagens como *"Tem Corolla?"*, *"Quero ver os carros disponíveis"* e validar que os veículos retornam na hora e o consumo de tokens permanece baixo.
