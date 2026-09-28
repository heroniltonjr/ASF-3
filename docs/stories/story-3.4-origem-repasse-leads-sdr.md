# Story 3.4: Origem, Propriedade e Motor de Repasse de Leads (SDR Central e Lojas)

## Status: Completed

## Description
Como consultor e gestor do Formula OS (Auto Shopping Fórmula),
Eu quero que todos os leads registrem com precisão o SDR de origem (`origin_id`), mantendo a posse original do SDR Central após a qualificação e gerando uma cópia de repasse para a loja selecionada (seja por rodízio do Modo Feirão ou pela loja proprietária do veículo),
Para que leads do Autoshopping permaneçam sob controle do shopping, lojas com Plano Pro recebam os leads diretamente no seu painel de atendimento via SSE, lojas com Plano Start recebam os dados via WhatsApp para atendimento manual, e o Modo Feirão seja governado exclusivamente por gestores.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Modelagem de Dados e Sessão com `store_plan`)**:
  - Criada migration `021_lead_origin_id.sql` adicionando a coluna `origin_id INTEGER NOT NULL DEFAULT 1` na tabela `leads` do SQLite e criando o índice `idx_leads_origin`.
  - A camada de autenticação (`backend/auth.py` e `/api/me`) retorna o plano da loja associada (`store_plan`) no payload do usuário da sessão.

- [x] **AC2 (Atribuição de Origem na Ingestão do WhatsApp)**:
  - Na criação de lead via `_ensure_lead` em `backend/ingest.py`:
    - Leads criados na loja 1 (Auto Shopping / SDR Central) recebem `origin_id = 1`.
    - Leads criados em instâncias de lojas parceiras recebem `origin_id = store_id`.

- [x] **AC3 (Preservação do Lead Central e Motor de Repasse no Transbordo)**:
  - Ao qualificar um lead (`[TRANSFERIR]`):
    - Se a conversa for do SDR Central (`store_id == 1`), o lead original permanece com `store_id = 1` e `origin_id = 1` no status `'Qualificado'`.
    - A loja destinatária é determinada de acordo com o modo em vigor:
      - **Modo Feirão**: selecionada pelo algoritmo de rodízio equilibrado `select_store_round_robin(conn)` (lojas ativas com menos leads no mês).
      - **Modo Normal**: loja proprietária do veículo de interesse (ou fallback para `select_store_round_robin` caso não identificada).
    - É criada uma cópia do lead para a loja destinatária com `store_id = loja_destino.id`, `origin_id = 1` e mesmos atributos (nome, telefone, preferências, histórico, veículo e orçamento).

- [x] **AC4 (Bifurcação de Repasse por Plano da Loja Destino)**:
  - **Se a loja destinatária for Plano Pro**:
    - Uma conversa é criada para a loja (`conversations` com `store_id = loja_destino.id`, `lead_id = copia_lead_id`, `status = 'Humano'`).
    - É publicado evento SSE no barramento para atualizar a inbox da loja em tempo real.
  - **Se a loja destinatária for Plano Start**:
    - Uma mensagem formatada com os dados do lead (Nome, Telefone, Veículo, Entrada/Troca, Cidade) é enviada via WhatsApp da Central para o número de contato da loja (`store_number` / `whatsapp`).
    - O disparo é registrado na tabela `messages_sent` através de `record_message_sent()`.
    - Uma conversa com flag de repasse é registrada para que a loja possa visualizar o histórico na sua listagem.

- [x] **AC5 (Governança e Restrição do Modo Feirão)**:
  - A rota `PUT /api/stores/{store_id}/sdr-mode` exige perfil de gestão (`master`, `shopping` ou `gestor`).
  - Requisições feitas por usuários com perfil `lojista` ou `vendedor` são rejeitadas com `HTTP 403 Forbidden`.

- [x] **AC6 (Cobertura de Testes Automatizados)**:
  - Criada suíte de testes `tests/test_lead_repasse.py` validando:
    - Atribuição de `origin_id` em leads da Central vs. leads de lojas.
    - Cópia do lead preservando o lead central.
    - Repasse para loja Pro com evento de conversa e SSE.
    - Repasse para loja Start com mensagem enviada ao número da loja e log em `messages_sent`.
    - Restrição de permissão do Modo Feirão (permissão para gestor/master e bloqueio para lojista).
  - 100% dos testes da suíte passando.

---

## Tasks & Checklist

- [x] **Task 1 (Database Migration & Auth Context)**:
  - Criar `backend/migrations/021_lead_origin_id.sql`.
  - Atualizar `backend/auth.py` para injetar `store_plan` no cache de sessão e no dicionário retornado pelo `get_session_user`.
  - Atualizar `backend/routes/auth_routes.py` para devolver `store_plan` no payload de `/api/login` e `/api/me`.

- [x] **Task 2 (Ingestion & Origin ID)**:
  - Atualizar `_ensure_lead` em `backend/ingest.py` para persistir `origin_id`.

- [x] **Task 3 (Lead Transfer Engine on Qualified)**:
  - Implementar lógica de repasse completo no bloco `if qualified:` de `backend/ingest.py`:
    - Lookup da loja de destino (Feirão vs Normal).
    - Criação da cópia do lead com `origin_id = 1` e `store_id = destino_id`.
    - Tratamento para loja Pro (conversa + SSE).
    - Tratamento para loja Start (envio WhatsApp + `record_message_sent`).

- [x] **Task 4 (Governance on SDR Mode)**:
  - Atualizar controle de roles em `backend/routes/whatsapp.py` para o endpoint `PUT /api/stores/{store_id}/sdr-mode`.

- [x] **Task 5 (Testes Automatizados & Quality Gate)**:
  - Criar e rodar `tests/test_lead_repasse.py`.
  - Garantir regressão zero com a suíte de testes existente do projeto.

---

## File List

- [NEW] [backend/migrations/021_lead_origin_id.sql](file:///c:/ProjetosMLDB/ASF-3/backend/migrations/021_lead_origin_id.sql)
- [MODIFY] [backend/auth.py](file:///c:/ProjetosMLDB/ASF-3/backend/auth.py)
- [MODIFY] [backend/routes/auth_routes.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/auth_routes.py)
- [MODIFY] [backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- [MODIFY] [backend/routes/whatsapp.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py)
- [NEW] [tests/test_lead_repasse.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_lead_repasse.py)
- [NEW] [docs/stories/story-3.4-origem-repasse-leads-sdr.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.4-origem-repasse-leads-sdr.md)
