# Story 4.3: API de Busca Híbrida & Integração com SDR WhatsApp e Vitrine

## Status: Completed

## Description
Como atendente virtual de vendas (SDR Rafael), gestor e comprador no portal do FormulaOS,
Eu quero dispor do endpoint FastAPI `/api/vehicles/search` e da integração da busca híbrida no fluxo de atendimento em `backend/ingest.py` e na vitrine pública, com cache LRU em memória, degradação graciosa para trigramas caso a OpenAI fique indisponível e classificação por `match_type` (`exato`, `similar`, `filtro`),
Para que qualquer busca por texto livre, áudio transcrito ou filtros encontre com máxima precisão o veículo desejado no estoque do shopping ou de uma loja específica, tolerando erros ortográficos, marcas compostas e descrições conceituais de intenção de compra.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Contratos Pydantic de Entrada e Saída)**:
  - Criar modelos Pydantic estruturados:
    - `SearchRequest`: `query` (texto livre opcional), `brand`, `model`, `category`, `year_from`, `year_to`, `price_min`, `price_max`, `store_ids: list[int] | None`, `limit: int = 15`.
    - `VehicleHit`: `id`, `identifier`, `brand`, `model`, `name`, `version`, `category`, `store_id`, `store`, `model_year`, `km`, `price`, `exchange`, `fuel_text`, `color`, `main_image`, `score`, `trgm_score`, `vector_score`, `match_type` (`exato` | `similar` | `filtro`).

- [x] **AC2 (Normalização de Texto e Regras de Limpeza)**:
  - Implementar função `build_search_text(req)`:
    - Concatena `query`, `brand`, `model`, `category`.
    - Sanitiza espaços em branco e descarta termos nulos, vazios ou marcadores genéricos como `_ALL_`.
    - Normaliza caracteres em minúsculas para vetorização e trigramas.

- [x] **AC3 (Vetorização da Consulta com Cache e Degradação Graciosa)**:
  - Implementar função assíncrona `embed_query(text: str) -> list[float] | None`.
  - Cache em memória LRU thread-safe / async (`_QUERY_EMBEDDINGS_CACHE`, capacidade de 2048 itens) para consultas repetidas ("onix", "corolla", "suv", "hilux").
  - Timeout estrito de 5.0 segundos.
  - Degradação graciosa garantida: caso a OpenAI demore, falhe ou esteja offline, a função retorna `None`, e a busca prossegue utilizando exclusivamente a via de trigramas, sem gerar erro HTTP 500.

- [x] **AC4 (Endpoint REST FastAPI `/api/vehicles/search`)**:
  - Implementar `POST /api/vehicles/search` com autenticação RBAC:
    - Extrai `tenant_id` e escopo de loja (`store_id`) da sessão do usuário autenticado.
    - Gestores/Masters podem pesquisar globalmente ou especificar `store_ids`. Lojistas têm a busca restrita à sua própria loja.
    - Executa a stored procedure `search_formulaos_vehicles` no PostgreSQL e retorna a lista de `VehicleHit`.
  - Implementar `POST /api/public/vehicles/search` para consultas públicas sem necessidade de token de sessão.

- [x] **AC5 (Integração com o SDR WhatsApp do FormulaOS)**:
  - Refatorar a função `search_vehicles_advanced(conn, store_id, incoming_text, is_feirao)` em `backend/ingest.py`:
    - Eliminar a lista estática de 27 palavras-chave e chamadas rudimentares com `ILIKE`.
    - Invocar a busca híbrida passando a mensagem do cliente como `p_query` e aplicando o escopo correto:
      - Em **Modo Feirão**: `p_store_ids = None` (busca no acervo completo do Auto Shopping).
      - Em **Modo Loja Individual**: `p_store_ids = [store_id]` (busca restrita ao estoque da loja).
    - Montar o card de apresentação de veículos para o prompt do SDR incluindo nome, preço, fotos, loja e se o match é exato ou alternativa sugerida (`similar` / `filtro`).

- [x] **AC6 (Compatibilidade com a Vitrine Pública)**:
  - Permitir que a rota pública de veículos (`/api/public/vehicles` e `/api/public/vehicles/search`) utilize a busca híbrida preservando a ordenação de relevância e os filtros de paginação.

- [x] **AC7 (Suíte de Testes Automatizados)**:
  - Criar `tests/test_hybrid_search_api.py` validando os 9 casos de teste canônicos:
    1. Erro ortográfico com marca sem padrão: `brand='Chevrolet', model='Onyx'` → Retorna Onix.
    2. Erro ortográfico direto: `query='corola'` → Retorna Corolla com `match_type = 'exato'`.
    3. Espaçamento atípico: `query='hb 20'` → Retorna HB20 e HB20S.
    4. Alias de marca: `query='volks polo'` → Retorna Polo com marca "VW - VolksWagen".
    5. Modelo com marca vazia extraída do `note`: `query='cronos'` → Retorna Cronos com marca Fiat extraída.
    6. Busca por intenção (vetorial pura): `query='picape diesel 4x4'` → Retorna picapes a diesel.
    7. Busca por intenção descritiva: `query='SUV automático econômico'` → Retorna SUVs automáticos com `match_type = 'similar'`.
    8. Busca sem texto (somente filtros de ano/preço): Retorna ordenado por preço com `match_type = 'filtro'`.
    9. Degradação offline: Chamada com OpenAI indisponível retorna resultados por trigramas sem erro 500.

---

## Tasks & Checklist

- [x] **Task 1 (Pydantic Schemas & Text Builder)**:
  - Criar `backend/schemas/search.py` com `SearchRequest` e `VehicleHit`.
  - Implementar e testar `build_search_text()`.
- [x] **Task 2 (Embedding Service with LRU Cache)**:
  - Implementar cliente assíncrono com cache LRU e fallback gracioso de timeout em `backend/services/hybrid_search.py`.
- [x] **Task 3 (FastAPI Route Implementation)**:
  - Criar endpoint `POST /api/vehicles/search` e `POST /api/public/vehicles/search` integrando a stored procedure com suporte a tenancy em `backend/routes/search.py`.
- [x] **Task 4 (SDR Ingestion Refactoring)**:
  - Atualizar `search_vehicles_advanced()` em `backend/ingest.py` consumindo a busca híbrida.
- [x] **Task 5 (Testes Automatizados)**:
  - Implementar suíte de testes em `tests/test_hybrid_search_api.py` cobrindo todos os cenários de intenção, typos e fallbacks (15 testes passando).

---

## File List

- [backend/schemas/search.py](file:///c:/ProjetosMLDB/ASF-3/backend/schemas/search.py)
- [backend/services/hybrid_search.py](file:///c:/ProjetosMLDB/ASF-3/backend/services/hybrid_search.py)
- [backend/routes/search.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/search.py)
- [backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- [backend/app.py](file:///c:/ProjetosMLDB/ASF-3/backend/app.py)
- [tests/test_hybrid_search_api.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_hybrid_search_api.py)
- [docs/stories/story-4.3-api-busca-hibrida-integracao-sdr.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-4.3-api-busca-hibrida-integracao-sdr.md)
