# Story 4.2: Worker Autônomo de Embeddings & Sincronização Contínua

## Status: Completed

## Description
Como engenheiro de dados e desenvolvedor backend do FormulaOS,
Eu quero implementar o worker Python de geração de embeddings (`backend/services/embeddings_worker.py`) integrado à API da OpenAI (`text-embedding-3-small`), com processamento em lote idempotente baseado em hash MD5 e múltiplos gatilhos de execução (CLI, pós-sync de estoque e background tasks),
Para que todo o acervo ativo de veículos tenha seus vetores mantidos atualizados continuamente, com custo reduzido, tolerância a falhas e sem dependência de workflows externos do n8n.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Data Engineer Lead**: `@data-engineer`
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Módulo do Worker e Configuração OpenAI)**:
  - Criar o serviço `backend/services/embeddings_worker.py`.
  - Configurar cliente `OpenAI` / `AsyncOpenAI` consumindo `OPENAI_API_KEY` das configurações (`settings.py` / `.env`).
  - Utilizar o modelo canônico `text-embedding-3-small` (1536 dimensões, taxa aproximada de US$ 0,02 / 1M tokens).

- [x] **AC2 (Query Idempotente de Veículos Pendentes)**:
  - Implementar seleção de veículos pendentes via `PENDING_SQL`:
    - Veículos com `active = true` e `embedding_text` não vazio.
    - Condição de pendência: ausência de registro em `formulaos_vehicle_embeddings`, ou `e.source_hash <> md5(v.embedding_text)`, ou modelo desatualizado (`e.model <> MODEL`).
    - Lotes configuráveis (padrão de 200 veículos por batch, abaixo do limite máximo de 2048 da OpenAI).

- [x] **AC3 (Upsert de Vetores e Rastreabilidade de Versão)**:
  - Gravar os vetores na tabela `formulaos_vehicle_embeddings` associando `vehicle_id`, vetor `embedding`, `source_hash = md5(text)`, `model` e `embedded_at = now()`.
  - Tratamento nativo do tipo `vector` via `pgvector` adapter / `psycopg`.
  - Idempotência comprovada: reexecuções consecutivas com estoque estável devem processar 0 linhas e consumir 0 tokens da OpenAI.

- [x] **AC4 (Controle de Concorrência e Resiliência)**:
  - Adicionar controle de concorrência com advisory lock (`pg_try_advisory_lock`) para evitar que execuções sobrepostas do worker colidam.
  - Implementar retries com backoff exponencial e timeout de 15s para chamadas à API da OpenAI.
  - Tratamento de exceções com logs claros sem interromper o backend principal.

- [x] **AC5 (Interface CLI e Utilitário de Execução)**:
  - Suportar execução direta via linha de comando: `python -m backend.services.embeddings_worker` executando `run_until_done()` e exibindo métricas de processamento (veículos processados, lotes, tempo total).

- [x] **AC6 (Gatilhos de Acionamento)**:
  - Disponibilizar hook / função `trigger_embeddings_sync()` para ser acionada:
    - Após o término do ciclo de importação de estoque do Trinix.
    - Em background task do FastAPI após criação/edição manual de veículo no admin (`backend/routes/vehicles.py`).

- [x] **AC7 (Suíte de Testes Automatizados)**:
  - Criar testes em `tests/test_embeddings_worker.py` cobrindo:
    - Processamento de lote com mock da OpenAI API.
    - Verificação de não reprocessamento quando o hash não muda.
    - Invalidação e reprocessamento quando o texto do veículo é alterado.
    - Resiliência em caso de falha de conexão com a OpenAI.

---

## Tasks & Checklist

- [x] **Task 1 (Setup de Dependências & Settings)**:
  - Garantir suporte ao pacote `openai` no ambiente Python e `requirements.txt`.
  - Validar `OPENAI_API_KEY` nas configurações centrais do FormulaOS.
- [x] **Task 2 (Core Worker Implementation)**:
  - Implementar `run_once()` e `run_until_done()` com `executemany` e registro vetorial.
  - Implementar cálculo de hash MD5 direto no banco e mapeamento ordenado de índices.
- [x] **Task 3 (Concorrência & CLI)**:
  - Adicionar `pg_try_advisory_lock(42)` e entrypoint `__main__` para execução CLI.
- [x] **Task 4 (Integração de Gatilhos)**:
  - Conectar chamada do worker no pipeline de sync / edição manual de veículos (`backend/routes/vehicles.py`).
- [x] **Task 5 (Testes Automatizados)**:
  - Escrever suíte de testes unitários em `tests/test_embeddings_worker.py` com fixtures de banco isolado e mock da API de embeddings.

---

## File List

- [backend/services/embeddings_worker.py](file:///c:/ProjetosMLDB/ASF-3/backend/services/embeddings_worker.py)
- [backend/db.py](file:///c:/ProjetosMLDB/ASF-3/backend/db.py)
- [backend/routes/vehicles.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/vehicles.py)
- [requirements.txt](file:///c:/ProjetosMLDB/ASF-3/requirements.txt)
- [tests/test_embeddings_worker.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_embeddings_worker.py)
- [docs/stories/story-4.2-worker-embeddings-vetorizacao.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-4.2-worker-embeddings-vetorizacao.md)
