# Plan para Importação de Veículos do Supabase para formulaos_vehicles

Este plano detalha o mapeamento de campos e a estratégia de importação dos **857 registros** da tabela pública `vehicles` para a nova tabela unificada e integrada `formulaos_vehicles` no Supabase, garantindo a integridade dos dados e o preenchimento de todos os vínculos relacionais do CRM.

## Mapeamento de Campos e Análise de Lacunas

Abaixo está a análise detalhada de como cada campo da tabela de destino `formulaos_vehicles` será preenchido:

| Campo de Destino (`formulaos_vehicles`) | Campo de Origem (`vehicles`) | Regra de Mapeamento / Preenchimento |
| :--- | :--- | :--- |
| **`id`** | - | Gerado automaticamente via sequência autoincremento (`SERIAL`). |
| **`store_id`** | `store` (texto) | Resolvido comparando o nome da loja via normalização (removendo acentos, espaços e maiúsculas). Caso não encontre, vincula à loja administradora (ID `1` - Auto Shopping Formula). |
| **`name`** | `name` | Copiado diretamente. |
| **`price`** | `price` (numeric) | Copiado diretamente. |
| **`mileage`** | `km` (int) | Gerado como `km || ' km'` (ex: `"52000 km"`). |
| **`transmission`** | `exchange` | Copiado diretamente. |
| **`fuel`** | `fuel_text` | Copiado diretamente. |
| **`image_path`** | `main_image` | Copiado diretamente. |
| **`status`** | `active`, `sold` | Se `sold` for `True` -> `'Vendido'`. Se `active` for `True` -> `'Publicado'`. Caso contrário -> `'Rascunho'`. |
| **`created_at`** | `synced_at` | Mapeado de `synced_at` ou `NOW()` caso nulo. |
| **`updated_at`** | `synced_at` | Mapeado de `synced_at` ou `NOW()` caso nulo. |
| **`identifier`** | `identifier` | Copiado diretamente. |
| **Campos de Vitrine (Brand, Model, etc.)** | Mesmo nome | Copiados diretamente da tabela de origem: `brand`, `model`, `version`, `fabrication_year`, `model_year`, `color`, `km`, `exchange`, `fuel_text`, `pictures`, `main_image`, `sold`, `active`, `in_transit`, `new_vehicle`, `featured`, `shielded`, `synced_at`, `batch_id`, `raw`, `embedding`, `item_list`, `unit_id`, `plate`, `category`, `note`, `doors`, `kind`. |

### Campos que podem ficar vazios (NULL)
Os campos adicionais da vitrine pública que não são obrigatórios e que não constam ou estão nulos em algum veículo de origem (como `plate`, `embedding`, `item_list`, `unit_id`, `category`, `note`, `doors`, `kind`) permanecerão nulos/vazios na tabela de destino, mantendo a compatibilidade original.

---

## Normalização e Resolução de Lojas (`store_id`)

Os nomes das lojas na tabela pública de veículos estão em formatos variados (geralmente em letras maiúsculas e sem acentos, ex: `BETEL AUTOMOVEIS`), enquanto no CRM estão normalizados (ex: `Betel Automóveis`). 

Implementaremos um algoritmo de comparação tolerante a acentos, caixa (maiúsculas/minúsculas) e caracteres não-alfanuméricos:
* **Filtro de Telefones/Números:** Qualquer sequência de dígitos (como DDDs `65` ou números de telefone `984311111`) presente no nome da loja de origem será removida através de expressões regulares antes da normalização. Somente o nome textual da loja será considerado.
* **Exemplos de Resolução:**
  1. `BETEL AUTOMOVEIS` -> Normaliza para `betelautomoveis` -> Casa com `Betel Automóveis` (normalizado para `betelautomoveis`).
  2. `EV AUTOMÓVEIS` -> Normaliza para `evautomoveis` -> Casa com `EV Automóveis` (normalizado para `evautomoveis`).
  3. `RADAR AUTOMÓVEIS 65 984311111` -> Remove números -> `RADAR AUTOMÓVEIS` -> Normaliza para `radarautomoveis` -> Casa com `Radar Automóveis` (normalizado para `radarautomoveis`).
  4. Lojas não catalogadas (ex: `F Motors` ou valores vazios) serão direcionadas para o ID `1` (`Auto Shopping Formula`) para triagem manual.

---

## Proposed Changes

### Script de Migração

#### [NEW] [migrate_vehicles_data.py](file:///c:/ProjetosMLDB/ASF-3/scratch/migrate_vehicles_data.py)
* Criar script em Python para:
  1. Conectar ao Supabase PostgreSQL via `DATABASE_URL`.
  2. Buscar todas as lojas existentes em `formulaos_stores` para mapeamento de cache em memória.
  3. Buscar todos os registros da tabela `vehicles` de origem.
  4. Executar o mapeamento e normalização linha por linha.
  5. Inserir os registros convertidos na tabela `formulaos_vehicles` dentro de uma transação.
  6. Imprimir estatísticas de importação e alertas de lojas não mapeadas que caíram no fallback do shopping.

---

## Verification Plan

### Manual Verification
1. **Visualização de Estatísticas de Importação:**
   * Executar o script de migração e validar que todos os 857 registros foram importados.
2. **Inspeção na Tabela de Destino:**
   * Rodar consultas rápidas no Supabase para verificar se a coluna `store_id` foi preenchida corretamente para lojas como `Betania Automoveis` e `GX Auto`.
   * Verificar se o trigger disparou e ajustou os campos de forma consistente.
3. **Teste na Vitrine Pública:**
   * Acessar o catálogo público da vitrine pelo navegador/FastAPI (`/api/public/vehicles`) e confirmar se a listagem exibe todos os veículos importados corretamente.
