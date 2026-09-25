# Walkthrough: Integração Completa do Supabase no ASF-3

Esta documentação resume as alterações realizadas para migrar o banco de dados principal do sistema para o Supabase (PostgreSQL), mantendo a compatibilidade retroativa para testes locais via SQLite e introduzindo uma sincronização automatizada via triggers na nova tabela unificada `formulaos_vehicles`.

## Alterações Realizadas

### 1. Banco de Dados & Infraestrutura (Supabase)
* Criada a tabela `formulaos_vehicles` no Supabase contendo todos os campos do CRM (SQLite) integrados com os campos do catálogo público (vitrine).
* Criado o trigger `trg_sync_formulaos_vehicles_fields` associado à função `fn_sync_formulaos_vehicles_fields()` para sincronizar automaticamente campos derivados da vitrine:
  * `identifier` -> Gerado automaticamente como `'Trinix-Auto-id' || id`.
  * `store` -> Nome da loja resolvido em tempo real da tabela `formulaos_stores`.
  * `active` e `sold` -> Mapeados a partir de `status` ('Publicado' e 'Vendido').
  * `main_image` -> Mapeado a partir de `image_path`.
  * `exchange` -> Mapeado a partir de `transmission`.
  * `fuel_text` -> Mapeado a partir de `fuel`.
  * `km` -> Convertido para inteiro a partir do texto `mileage` (removendo pontos e texto).
  * `brand` e `model` -> Extraídos por divisão do campo `name`.

### 2. Camada do Cliente de Banco de Dados (Backend)
* Atualizado o arquivo [db.py](file:///c:/ProjetosMLDB/ASF-3/backend/db.py):
  * **Conexão PostgreSQL:** Adicionado suporte ao `psycopg2` se `DATABASE_URL` estiver configurado no `.env`.
  * **Fallback do Ambiente de Testes:** Prioriza o SQLite local se `SQLITE_PATH` estiver definido, permitindo que a suíte de testes continue rodando offline e de forma veloz.
  * **Tradução de Queries Dinâmica:**
    * Substituição de placeholders de `?` para `%s`.
    * Auto-prefixação transparente das tabelas do banco de dados (ex: `vehicles` -> `formulaos_vehicles`).
    * Tradução de expressões SQLite (`INSERT OR IGNORE` -> `ON CONFLICT DO NOTHING`).
    * Emulação da propriedade `lastrowid` para inserções usando `RETURNING id`.
    * Delegação de propriedades como `rowcount` e `description` do cursor PostgreSQL.

### 3. Cliente da Vitrine Pública (Backend)
* Atualizado o arquivo [supabase_client.py](file:///c:/ProjetosMLDB/ASF-3/backend/supabase_client.py):
  * Atualizada a constante `VEHICLES` para apontar para a nova tabela unificada `formulaos_vehicles`.

---

## O Que Foi Testado e Resultados

### 1. Testes Automatizados (SQLite Fallback)
* Executada a suíte de testes com sucesso usando o comando:
  ```bash
  python -m pytest
  ```
* **Resultado:** **61 testes aprovados (100% de sucesso)**, garantindo que as modificações no `db.py` mantiveram a retrocompatibilidade perfeita com o banco SQLite em ambiente de teste.

### 2. Validação Manual do Supabase & Triggers
* Executado o script de verificação `verify_supabase.py` com o `DATABASE_URL` configurado, conectando-se diretamente ao Supabase PostgreSQL:
  * Inserido um veículo usando comandos SQLite tradicionais no backend.
  * O ID de inserção (`lastrowid`) foi recuperado corretamente como `1`.
  * Validada a sincronização automática dos triggers do PostgreSQL. Todos os campos foram testados e validados:
    * `identifier` -> `Trinix-Auto-id1`
    * `store` -> `Betania Automoveis`
    * `active` -> `True`
    * `km` -> `5200`
    * `brand` -> `Ferrari`
    * `model` -> `Portofino V8 Turbo`
* **Resultado:** Todas as asserções de sincronização passaram sem falhas!

### 3. Configurações de Variáveis no Backend
* Atualizado o arquivo [settings.py](file:///c:/ProjetosMLDB/ASF-3/backend/settings.py) para aceitar automaticamente as variáveis `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` caso `SUPABASE_URL` e `SUPABASE_ANON_KEY` não estejam explicitamente declarados no `.env`. Isso simplifica e garante o funcionamento local imediato.

### 4. Importação e Sincronização de Dados de Veículos (vehicles → formulaos_vehicles)
* Criado e executado o script de importação [migrate_vehicles_data.py](file:///c:/ProjetosMLDB/ASF-3/scratch/migrate_vehicles_data.py).
* **Normalização de Lojas:** O script remove códigos DDD (ex: `65`) e números de telefone no fim do texto de origem utilizando expressões regulares. Ele normaliza os caracteres removendo acentos e espaços para associar as chaves corretamente às lojas catalogadas em `formulaos_stores`.
* **Resultado do Import:**
  * **857 veículos** importados com sucesso da tabela original `vehicles` para a tabela integrada `formulaos_vehicles`.
  * Das 20 lojas de origem, 19 foram associadas com sucesso após normalização (apenas `F Motors` caiu no fallback da loja administrativa por não existir no CRM).
* **Segurança e RLS:** Foi criada e executada uma política de segurança em [create_policy.py](file:///c:/ProjetosMLDB/ASF-3/scratch/create_policy.py):
  * `CREATE POLICY "read active vehicles" ON formulaos_vehicles FOR SELECT TO public USING (active = true)`
  * Isso habilita a leitura pública anônima da tabela via PostgREST do Supabase usando a chave anon pública para a vitrine.
* **Teste de Integração da Vitrine:**
  * Executado teste de rota via TestClient FastAPI chamando o endpoint de vitrine pública `/api/public/vehicles?limit=5`.
  * **Resultado:** Sucesso completo. Retornou status `200` com um total de **322 veículos ativos** filtrados e serializados perfeitamente com os dados das lojas normalizadas e campos derivados (km, status, price_int, etc.) providos pelos triggers.

