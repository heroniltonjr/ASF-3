# Story 2.2: Backend CRUD Expandido para Suporte aos 41 Campos da Tabela `formulaos_vehicles`

## Status: Ready for Dev

## Description
Como operador, gestor do shopping ou lojista parceiro,
Eu quero registrar e editar veículos com todos os atributos detalhados suportados pelo banco de dados PostgreSQL (`formulaos_vehicles`),
Para que o estoque contenha informações completas de marca, modelo, versão, ano, km, galeria de fotos CDN, opcionais e badges comerciais, alimentando com precisão a vitrine pública e o CRM de atendimento.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)

---

## Acceptance Criteria

- [ ] **AC1 (Persistência Completa de Atributos)**: Os endpoints `POST /api/vehicles` e `PATCH /api/vehicles/{id}` devem receber, validar e persistir todos os campos da tabela `formulaos_vehicles`:
  - Identificação: `brand`, `model`, `version`, `name`, `category`, `kind`, `doors`, `color`, `plate`, `unit_id`.
  - Anos e Rodagem: `fabrication_year`, `model_year`, `km`, `mileage`.
  - Câmbio e Combustível: `transmission`, `exchange`, `fuel`, `fuel_text`.
  - Comercial: `price`, `status`, `store_id`, `store`.
  - Badges/Flags: `featured`, `new_vehicle`, `shielded`, `in_transit`, `sold`, `active`.
  - Opcionais: `item_list` (array de strings / `text[]`).
  - Observações: `note` (texto livre).
  - Fotos CDN: `image_path`, `main_image` e `pictures` (JSONB com estrutura `[{"remote_image_url": "..."}]`).
- [ ] **AC2 (Isolamento por Perfil - RBAC)**:
  - Usuários com perfil `lojista` só podem criar, atualizar e excluir veículos associados ao seu próprio `store_id` (`STORE_SCOPED_ROLES`). O payload é forçado para `store_id = user["store_id"]` ignorando qualquer valor arbitrário enviado.
  - Usuários com perfil `gestor` ou `master` podem definir ou alterar o `store_id` para qualquer loja cadastrada.
- [ ] **AC3 (Sincronização Bidirecional e Triggers)**:
  - Garantir compatibilidade com as triggers do banco: `trg_set_formulaos_vehicles_identifier` (geração de UUID/identificador) e `trg_sync_formulaos_vehicles_fields` (sincronização entre `km`/`mileage`, `transmission`/`exchange`, `image_path`/`main_image`).
- [ ] **AC4 (Consulta e Retorno Detalhado)**:
  - `GET /api/vehicles` e `GET /api/vehicles/{id}` devem retornar todos os novos campos serializados corretamente (incluindo parsing seguro de `pictures` e `item_list`).
- [ ] **AC5 (Compatibilidade com Vitrine Pública)**:
  - A rota pública `backend/routes/public.py` (`/api/public/vehicles` e `/api/public/vehicles/{id}`) deve consumir diretamente os novos campos estruturados (`brand`, `model`, `version`, `fabrication_year`, `model_year`, `item_list`, `note`, `pictures`).
- [ ] **AC6 (Testes Automatizados)**:
  - Criar `tests/test_vehicles_crud_expanded.py` cobrindo criação, edição e consulta com todos os 41 campos, testando isolamento de lojas para `lojista` e flexibilidade para `gestor`. 100% de sucesso no `pytest`.

---

## Tasks & Checklist

- [ ] **Task 1 (Rotas de Veículos)**: Expandir `_FIELDS`, `_REQUIRED` e `_PATCHABLE` em `backend/routes/vehicles.py` para incluir todos os novos campos.
- [ ] **Task 2 (Mapeamento de Tipos e Serialização)**: Tratar tipos especiais no SQLite e PostgreSQL:
  - `pictures`: JSONB (serializar `json.dumps(pictures)` no insert/update e `json.loads` no retorno).
  - `item_list`: array de strings (salvar como array Postgres ou JSON no SQLite).
  - `price`: float/numeric; `km`: int.
- [ ] **Task 3 (Adaptação da Consulta GET)**: Garantir que `store_name` e todos os campos sejam retornados no payload para a tabela e o modal do frontend.
- [ ] **Task 4 (Ajustes no Portal Público)**: Garantir que `backend/routes/public.py` utilize os novos campos para alimentar os cards da vitrine e a página de detalhes com a galeria completa.
- [ ] **Task 5 (Testes Automatizados)**: Implementar `tests/test_vehicles_crud_expanded.py` cobrindo cenários com e sem loja, validação de payload e perfil lojista vs gestor.
- [ ] **Task 6 (Quality Gate)**: Rodar `pytest tests/test_vehicles_crud_expanded.py` e `ruff check backend tests`.

---

## File List

- [NEW] [tests/test_vehicles_crud_expanded.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_vehicles_crud_expanded.py)
- [MODIFY] [backend/routes/vehicles.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/vehicles.py)
- [MODIFY] [backend/routes/public.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/public.py)

---

## Dev Notes
- As triggers do Postgres `trg_sync_formulaos_vehicles_fields` sincronizam `km` e `mileage` automaticamente, mas é boa prática enviar ambos preenchidos para compatibilidade com o SQLite de desenvolvimento.
- Se `pictures` vier vazio ou não for enviado, o padrão no banco é `'[]'::jsonb`.
