# Story 1.1: Implementação do Agente Rafael (SDR n8n) no FormulaOS

## Status: Done

## Description
Como gestor/lojista do Auto Shopping Fórmula,
Eu quero ter o Agente Rafael (SDR de IA) integrado nativamente ao FormulaOS com suporte aos modos Normal e Feirão, transcrição de áudio, busca avançada de veículos, trava de duplicados e controle visual de modalidade no painel,
Para que o atendimento automatizado via WhatsApp aos leads seja qualificado, transparente e distribuído de forma justa entre as lojas participantes durante os eventos.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Product Owner**: `@po` (Pax)

---

## Acceptance Criteria

- [x] **AC1 (Database & Migrations)**: Migration `backend/migrations/015_agente_rafael_feirao.sql` adicionando colunas `leads_this_month INTEGER DEFAULT 0`, `total_leads INTEGER DEFAULT 0`, `is_active BOOLEAN DEFAULT TRUE`, `operation_mode TEXT DEFAULT 'normal'`, `updated_at TIMESTAMP` na tabela `stores`, além da tabela de log `messages_sent`.
- [x] **AC2 (Busca Avançada de Estoque)**: Implementação do mecanismo `search_vehicles_advanced` em `backend/ingest.py` / `backend/sdr.py` replicando a lógica do sub-workflow `QuickSearchV3` (filtros opcionais de marca, modelo, categoria, ano e faixa de preço com valores default).
- [x] **AC3 (Modo Feirão & Load Balancing)**: Algoritmo `select_store_round_robin` em `backend/ingest.py` realizando o rodízio justo de lojas para o Modo Feirão (ordenação por menor `leads_this_month`, `updated_at` mais antigo e menor `total_leads`).
- [x] **AC4 (Engenharia de Prompt & Trava POS_ATENDIMENTO)**: Prompt do SDR em `backend/sdr.py` atualizado com a persona do Agente Rafael, regras de linguagem positiva ("nunca diga não tem"), gatilhos de autoridade ("30+ lojas, 15 anos de mercado") e a trava do estado `POS_ATENDIMENTO` para evitar mensagens duplicadas às lojas.
- [x] **AC5 (Processamento de Voz / Áudio)**: Ingestão e transcrição automática de mensagens de voz (`audio.audioUrl`) via OpenAI Whisper na rota de webhook `backend/routes/whatsapp.py`.
- [x] **AC6 (Intervenção Humana & Pausa do SDR)**: Integração nativa garantindo que quando o status da conversa for `'Humano'`, o SDR permaneça pausado no `ingest.py`, reativando automaticamente apenas quando o status retornar para `'SDR ativo'`.
- [x] **AC7 (Controle de Modalidade na UI)**: Seletor visual (`Toggle Switch / Dropdown`) no painel web (`atendimento.html` / `app.js`) conectado ao endpoint `PUT /api/stores/:id/sdr-mode` permitindo alternar entre Modo Normal e Modo Feirão em tempo real.
- [x] **AC8 (Testes & Qualidade)**: Suíte de testes automatizados `tests/test_sdr_rafael.py` e atualizações em `tests/test_ingest.py` executando com 100% de sucesso no `pytest` (66/66 testes).

---

## Tasks & Checklist

- [x] **Task 1 (DB Schema)**: Criar migration `backend/migrations/015_agente_rafael_feirao.sql` e atualizar a inicialização em `backend/db.py`.
- [x] **Task 2 (Busca de Estoque)**: Implementar função de busca parametrizada de veículos `search_vehicles_advanced` em `backend/ingest.py`.
- [x] **Task 3 (Modo Feirão)**: Implementar seleção equilibrada Round-Robin `select_store_round_robin` em `backend/ingest.py`.
- [x] **Task 4 (Prompt SDR & Trava)**: Atualizar `backend/sdr.py` com o prompt do Agente Rafael, regras de conduta e controle de estado `POS_ATENDIMENTO`.
- [x] **Task 5 (Transcrição de Áudio)**: Adicionar suporte à transcrição de áudio Whisper no handler do webhook em `backend/routes/whatsapp.py`.
- [x] **Task 6 (API & UI Toggle)**: Adicionar rota `PUT /api/stores/:id/sdr-mode` em `backend/routes/whatsapp.py` e criar o componente visual em `atendimento.html` / `app.js`.
- [x] **Task 7 (Testes)**: Criar `tests/test_sdr_rafael.py` e validar a suíte completa com `pytest`.

---

## File List

- [NEW] [backend/migrations/015_agente_rafael_feirao.sql](file:///c:/ProjetosMLDB/ASF-3/backend/migrations/015_agente_rafael_feirao.sql)
- [NEW] [tests/test_sdr_rafael.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_sdr_rafael.py)
- [MODIFY] [backend/db.py](file:///c:/ProjetosMLDB/ASF-3/backend/db.py)
- [MODIFY] [backend/sdr.py](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py)
- [MODIFY] [backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- [MODIFY] [backend/routes/whatsapp.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py)
- [MODIFY] [atendimento.html](file:///c:/ProjetosMLDB/ASF-3/atendimento.html)
