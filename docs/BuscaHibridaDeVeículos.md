# Busca híbrida de veículos — guia de implementação

Oct 15, 2026 · @Milton Lima

## Visão geral

A busca híbrida substitui `ILIKE '%termo%'` por uma função no Postgres que combina similaridade de trigramas (`pg_trgm`) e similaridade vetorial (`pgvector` + OpenAI `text-embedding-3-small`), fundidas por Reciprocal Rank Fusion (RRF). Está em produção desde 13/10/2026 na tabela `vehicles` (projeto Supabase Locks), atendendo o agente AgenteSDRWpp\_Feirao via webhook QuickSearchV4.

**O problema que resolve.** A busca antiga filtrava `brand`, `model` e `category` com `ILIKE`, o que falhava em três situações:

- Erros de digitação e variações: "onyx", "hb 20", "corola", "volks".
- Marcas sem padrão: "VW - VolksWagen", "GM - Chevrolet", "HONDA" e "Honda", "Kia Motors".
- Veículos sem marca, modelo ou categoria: 106 de 311 ativos (34%) tinham esses campos vazios. A informação existia só em `name` e em `raw->>'note'`.

**Por que híbrida e não só vetorial.** Embeddings são fracos para nomes curtos e typos: "Onyx" e "Onix" podem ficar distantes no espaço vetorial. Trigramas resolvem typos, mas não entendem intenção ("SUV econômico para família"). Cada método cobre a fraqueza do outro.

**Resultados medidos na `vehicles`:**

| Busca | ILIKE (V3) | Híbrida (V4) |
| --- | --- | --- |
| brand=Chevrolet, model=Onyx | 0 resultados | 15 Onix, incluindo os 3 sem marca cadastrada |
| query="picape diesel 4x4" | não suportado | Hilux, Toro, S10, Amarok, todas diesel |
| "corola" | 0 | Corolla e Corolla Cross (match exato, trgm 0,86) |
| "hb 20" | 0 | HB20S de 3 lojas |
| sem texto, só filtros | ordenado por preço | idêntico ao V3 |

## Arquitetura

&#91;embedded content: arquitetura · indexação em cima, busca embaixo\]

A indexação (linha de cima) roda em segundo plano e mantém os textos e os embeddings em dia. A busca (linha de baixo) faz uma única chamada à OpenAI, para o embedding da consulta, e uma única consulta ao banco. Na `vehicles`, o worker e a API são workflows n8n (Vehicles\_Embeddings e QuickSearchV4); aqui, os dois viram código Python.

## Banco de dados

Na `formulaos_vehicles`, a recomendação é guardar os embeddings numa tabela separada, e não na coluna `embedding` que já existe. O motivo: a tabela tem a trigger `trg_sync_formulaos_vehicles_fields`, que reescreve `synced_at` em todo UPDATE. Gravar o embedding na própria linha faria o worker sujar o `synced_at` de todo o estoque a cada execução. Na `vehicles` isso não aconteceu porque ela não tem essa trigger.

As extensões `vector` (0.8.0), `pg_trgm` e `unaccent` já estão instaladas no schema `public` do projeto Locks.

### Colunas, tabela de embeddings e índices

```sql
alter table public.formulaos_vehicles
  add column if not exists search_text text,      -- texto normalizado para trigramas
  add column if not exists embedding_text text;   -- texto descritivo enviado ao modelo de embedding

create table if not exists public.formulaos_vehicle_embeddings (
  vehicle_id  integer primary key references public.formulaos_vehicles(id) on delete cascade,
  embedding   vector(1536) not null,
  source_hash text not null,   -- md5(embedding_text) no momento em que o embedding foi gerado
  model       text not null default 'text-embedding-3-small',
  embedded_at timestamptz not null default now()
);
alter table public.formulaos_vehicle_embeddings enable row level security;
-- sem policies: só o backend (conexão direta ou service_role) lê e escreve

create index if not exists formulaos_vehicles_search_text_trgm
  on public.formulaos_vehicles using gin (search_text gin_trgm_ops);
create index if not exists formulaos_vehicle_embeddings_hnsw
  on public.formulaos_vehicle_embeddings using hnsw (embedding vector_cosine_ops);
```

O `source_hash` substitui o "zerar o embedding quando o texto muda" usado na `vehicles`: um veículo está pendente quando não tem linha na tabela de embeddings ou quando `md5(embedding_text)` difere do hash gravado. Trocar de modelo também dispara o reprocessamento, via coluna `model`.

### Trigger que monta os textos de busca

`unaccent()` não é `IMMUTABLE`, então não pode ser usada numa coluna gerada. Por isso os textos são montados por trigger.

Duas melhorias em relação à versão da `vehicles`:

- **Filtro do `note`.** Na `formulaos_vehicles`, o `note` costuma trazer texto de marketing da loja ("GARANTIA 3 MES DA LOJA!", "Empresa especializada em seminovos"). Só o formato do Trinix ("FIAT - CRONOS - 1.0 FIREFLY... - 2024/2025Cor: ...") traz marca e modelo, então a trigger só aproveita o `note` quando ele segue esse padrão.
- **Ordem das triggers.** O Postgres dispara triggers `BEFORE` do mesmo evento em ordem alfabética de nome. O prefixo `trg_zz_` garante que esta rode depois de `trg_sync_formulaos_vehicles_fields`, que preenche `exchange` e `fuel_text` a partir de `transmission` e `fuel`.

```sql
create or replace function public.formulaos_vehicles_build_search_fields()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_note  text := coalesce(new.note, new.raw->>'note', '');
  v_head  text := '';
  v_base  text;
  v_alias text := '';
begin
  -- só o formato do Trinix: "MARCA - MODELO - VERSÃO - ano/anoCor: ..."
  if v_note ~ '^[^-]{2,30} - [^-]{1,40} - ' then
    v_head := trim(split_part(v_note, 'Cor:', 1));
  end if;

  v_base := lower(unaccent(concat_ws(' ',
    new.brand, new.model, new.version, new.name, new.category, v_head)));

  -- aliases de marca comuns no WhatsApp
  if v_base ~ '(volkswagen|\mvw\M|volks)' then v_alias := v_alias || ' volkswagen vw volks'; end if;
  if v_base ~ '(chevrolet|\mgm\M)'        then v_alias := v_alias || ' chevrolet gm chevy'; end if;
  if v_base ~ 'mercedes'                  then v_alias := v_alias || ' mercedes benz'; end if;
  if v_base ~ 'land rover'                then v_alias := v_alias || ' landrover'; end if;
  if v_base ~ 'chery'                     then v_alias := v_alias || ' caoa chery'; end if;

  new.search_text := v_base || v_alias;

  new.embedding_text := concat_ws('. ',
    'Veículo: ' || nullif(trim(concat_ws(' ', nullif(new.brand,''), nullif(new.model,''), nullif(new.version,''))), ''),
    'Descrição: ' || nullif(new.name, ''),
    nullif(v_head, ''),
    'Categoria: '   || nullif(new.category, ''),
    'Câmbio: '      || nullif(new.exchange, ''),
    'Combustível: ' || nullif(new.fuel_text, ''),
    'Portas: '      || nullif(new.doors, 0)::text,
    'Tipo: '        || nullif(new.kind, '')
  );

  return new;
end $$;

drop trigger if exists trg_zz_formulaos_vehicles_search on public.formulaos_vehicles;
create trigger trg_zz_formulaos_vehicles_search
  before insert or update on public.formulaos_vehicles
  for each row execute function public.formulaos_vehicles_build_search_fields();
```

### Backfill sem sujar o `synced_at`

O UPDATE de backfill dispara todas as triggers da tabela. Desative a trigger de sync durante a carga para não reescrever o `synced_at` dos 946 veículos:

```sql
begin;
alter table public.formulaos_vehicles disable trigger trg_sync_formulaos_vehicles_fields;
update public.formulaos_vehicles set id = id;   -- dispara só a trg_zz_
alter table public.formulaos_vehicles enable trigger trg_sync_formulaos_vehicles_fields;
commit;
```

A coluna `formulaos_vehicles.embedding` (vazia, `vector(1536)`) pode ser removida depois que tudo estiver no ar, para não confundir quem ler o schema.

## Função de busca

Toda a lógica de ranking fica numa função SQL. O backend só gera o embedding da consulta e chama a função, então o n8n, o Python ou qualquer outro cliente obtêm exatamente o mesmo resultado.

### Como o ranking funciona

1. **Filtros rígidos primeiro:** `active`, não vendido, tenant, lojas, faixa de ano e faixa de preço. Só o que passa aqui é pontuado.
2. **Trigramas por token:** a consulta normalizada é quebrada em palavras de 2 ou mais letras. Cada palavra recebe `word_similarity(palavra, search_text)` e o score do veículo é a média. Entram os veículos com média de pelo menos `p_min_trgm`. A média por palavra evita que "Chevrolet Onix Hatchback" falhe só porque o carro não tem categoria cadastrada.
3. **Vetorial:** similaridade de cosseno entre o embedding da consulta e o do veículo. Entram os 50 mais próximos com similaridade de pelo menos `p_min_cos`.
4. **Fusão por RRF:** cada lista vira um ranking e o score final soma o inverso das posições. Um veículo bem colocado nas duas listas sobe; um que aparece só numa ainda entra, mais abaixo.

```latex
\text{score}(v) = \frac{1}{60 + \text{rank}_{\text{trgm}}(v)} + \frac{1}{60 + \text{rank}_{\text{vetor}}(v)}
```

O 60 é a constante padrão do RRF e suaviza a diferença entre as primeiras posições. RRF usa só posições, não os scores brutos, então não é preciso normalizar trigrama (0 a 1) contra cosseno (que, nesse modelo, fica entre 0,3 e 0,6).

5. **Classificação:** `match_type` é `exato` quando o score de trigramas é de pelo menos 0,8, `similar` nos demais casos e `filtro` quando não houve texto de busca.

Sem texto e sem embedding, a função se comporta como a busca antiga: aplica só os filtros e ordena por preço.

### Parâmetros

| Parâmetro | Tipo | Padrão | Uso |
| --- | --- | --- | --- |
| `p_query` | text | null | Texto livre já concatenado (query + marca + modelo + categoria) |
| `p_query_embedding` | vector(1536) | null | Embedding de `p_query`; null = só trigramas |
| `p_tenant_id` | int | null | Filtra por `formulaos_stores.tenant_id` |
| `p_store_ids` | int\[\] | null | Restringe a lojas específicas |
| `p_year_from`, `p_year_to` | int | 1949, ano atual | Usa `fabrication_year`, ou `model_year` quando vazio |
| `p_price_min`, `p_price_max` | numeric | 0, 100.000.000 | Faixa de preço |
| `p_limit` | int | 15 | Máximo de resultados |
| `p_min_trgm` | real | 0,45 | Corte do score médio de trigramas |
| `p_min_cos` | real | 0,30 | Corte da similaridade de cosseno |

### SQL

```sql
create or replace function public.search_formulaos_vehicles(
  p_query           text         default null,
  p_query_embedding vector(1536) default null,
  p_tenant_id       int          default null,
  p_store_ids       int[]        default null,
  p_year_from       int          default 1949,
  p_year_to         int          default extract(year from now())::int,
  p_price_min       numeric      default 0,
  p_price_max       numeric      default 100000000,
  p_limit           int          default 15,
  p_min_trgm        real         default 0.45,
  p_min_cos         real         default 0.30
)
returns table (
  id int, identifier text, brand text, model text, name text, version text,
  category text, store_id int, store text, model_year int, fabrication_year int,
  km int, price numeric, exchange text, fuel_text text, color text, doors int,
  main_image text, plate text, shielded boolean,
  score double precision, trgm_score real, vector_score double precision, match_type text
)
language sql
stable
set search_path = public
as $$
with params as (
  select nullif(trim(lower(unaccent(coalesce(p_query, '')))), '') as q
),
filtered as (
  select v.*,
         e.embedding as emb,
         case when coalesce(v.note, '') ~ '^[^-]{2,30} - [^-]{1,40} - '
              then trim(split_part(v.note, 'Cor:', 1)) else '' end as note_head
  from formulaos_vehicles v
  left join formulaos_vehicle_embeddings e on e.vehicle_id = v.id
  left join formulaos_stores s on s.id = v.store_id
  where v.active
    and not coalesce(v.sold, false)
    and (p_tenant_id is null or s.tenant_id = p_tenant_id)
    and (p_store_ids is null or v.store_id = any(p_store_ids))
    and coalesce(v.fabrication_year, v.model_year) between p_year_from and p_year_to
    and v.price between p_price_min and p_price_max
),
tokens as (
  select t from regexp_split_to_table((select q from params), '\s+') t
  where length(t) >= 2
),
trg_r as (
  select f.id,
         avg(word_similarity(tk.t, f.search_text))::real as s,
         row_number() over (order by avg(word_similarity(tk.t, f.search_text)) desc) as r
  from filtered f cross join tokens tk
  group by f.id
  having avg(word_similarity(tk.t, f.search_text)) >= p_min_trgm
),
vec_r as (
  select f.id,
         1 - (f.emb <=> p_query_embedding) as s,
         row_number() over (order by f.emb <=> p_query_embedding) as r
  from filtered f
  where p_query_embedding is not null
    and f.emb is not null
    and 1 - (f.emb <=> p_query_embedding) >= p_min_cos
  order by f.emb <=> p_query_embedding
  limit 50
),
fused as (
  select coalesce(t.id, vv.id) as id,
         coalesce(1.0 / (60 + t.r), 0) + coalesce(1.0 / (60 + vv.r), 0) as score,
         t.s as trgm_score,
         vv.s as vector_score
  from trg_r t
  full outer join vec_r vv on vv.id = t.id
)
select f.id, f.identifier,
       coalesce(nullif(f.brand, ''), initcap(split_part(f.note_head, ' - ', 1))),
       coalesce(nullif(f.model, ''), initcap(split_part(f.note_head, ' - ', 2))),
       f.name, coalesce(nullif(f.version, ''), f.name), f.category, f.store_id, f.store,
       f.model_year, f.fabrication_year, f.km, f.price, f.exchange, f.fuel_text,
       f.color, f.doors, f.main_image, f.plate, f.shielded,
       x.score, x.trgm_score, x.vector_score,
       case when x.trgm_score >= 0.8 then 'exato' else 'similar' end
from fused x
join filtered f on f.id = x.id
where (select q from params) is not null or p_query_embedding is not null
union all
select f.id, f.identifier,
       coalesce(nullif(f.brand, ''), initcap(split_part(f.note_head, ' - ', 1))),
       coalesce(nullif(f.model, ''), initcap(split_part(f.note_head, ' - ', 2))),
       f.name, coalesce(nullif(f.version, ''), f.name), f.category, f.store_id, f.store,
       f.model_year, f.fabrication_year, f.km, f.price, f.exchange, f.fuel_text,
       f.color, f.doors, f.main_image, f.plate, f.shielded,
       null, null, null, 'filtro'
from filtered f
where (select q from params) is null and p_query_embedding is null
order by score desc nulls last, price asc
limit p_limit;
$$;
```

O veículo sem marca cadastrada volta com marca e modelo extraídos do cabeçalho do `note` ("FIAT - CRONOS - ..." vira Fiat / Cronos), para o agente ou o front exibirem algo legível.

**Escala.** A função calcula a distância sobre o conjunto já filtrado, sem usar o índice HNSW. Com cerca de 400 veículos ativos isso leva poucos milissegundos e dá recall exato. Acima de algumas dezenas de milhares de linhas, vale reescrever `vec_r` para ordenar direto pelo índice (`order by embedding <=> q limit k`) com `set hnsw.iterative_scan = relaxed_order`, recurso do pgvector 0.8.

## Worker de embeddings (Python)

Um único worker cobre a carga inicial e as atualizações: ele busca os veículos pendentes, gera os embeddings em lote numa chamada à OpenAI e faz upsert na tabela de embeddings. Na `vehicles`, esse papel é do workflow n8n Vehicles\_Embeddings, que roda a cada 15 minutos.

Dependências: `psycopg[binary]`, `psycopg-pool`, `pgvector`, `numpy`, `openai`.

```python
# embeddings_worker.py
import os
import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from openai import OpenAI

DSN = os.environ["DATABASE_URL"]          # conexão direta ou pooler do Supabase (porta 5432)
MODEL = "text-embedding-3-small"          # 1536 dimensões, igual à coluna vector(1536)
BATCH = 200                               # a API aceita até 2048 textos por chamada

client = OpenAI()                         # lê OPENAI_API_KEY do ambiente

PENDING_SQL = """
select v.id, v.embedding_text
from formulaos_vehicles v
left join formulaos_vehicle_embeddings e on e.vehicle_id = v.id
where v.active
  and coalesce(v.embedding_text, '') <> ''
  and (e.vehicle_id is null
       or e.source_hash <> md5(v.embedding_text)
       or e.model <> %(model)s)
order by v.updated_at desc nulls last
limit %(limit)s
"""

UPSERT_SQL = """
insert into formulaos_vehicle_embeddings (vehicle_id, embedding, source_hash, model, embedded_at)
values (%s, %s, md5(%s), %s, now())
on conflict (vehicle_id) do update
  set embedding   = excluded.embedding,
      source_hash = excluded.source_hash,
      model       = excluded.model,
      embedded_at = now()
"""


def run_once(conn: psycopg.Connection) -> int:
    """Processa um lote. Retorna quantos veículos foram atualizados."""
    rows = conn.execute(PENDING_SQL, {"model": MODEL, "limit": BATCH}).fetchall()
    if not rows:
        return 0

    texts = [text for _, text in rows]
    resp = client.embeddings.create(model=MODEL, input=texts)

    with conn.cursor() as cur:
        cur.executemany(
            UPSERT_SQL,
            [
                (vehicle_id, np.array(item.embedding, dtype=np.float32), text, MODEL)
                for (vehicle_id, text), item in zip(rows, resp.data)  # resp.data vem na ordem do input
            ],
        )
    conn.commit()
    return len(rows)


def run_until_done() -> int:
    total = 0
    with psycopg.connect(DSN) as conn:
        register_vector(conn)
        while (n := run_once(conn)) > 0:
            total += n
    return total


if __name__ == "__main__":
    print(f"embeddings atualizados: {run_until_done()}")
```

Pontos de projeto:

- **O hash é calculado no banco** (`md5(%s)` no upsert e `md5(v.embedding_text)` na busca de pendentes). Calcular em Python com `hashlib.md5` também funciona, mas qualquer diferença de encoding faria o veículo ficar pendente para sempre.
- **Idempotente:** rodar duas vezes seguidas não gera chamadas extras, porque o segundo `PENDING_SQL` volta vazio.
- **Concorrência:** se mais de uma instância puder rodar ao mesmo tempo, adicione `for update of v skip locked` ao `PENDING_SQL` ou use um advisory lock (`select pg_try_advisory_lock(42)`) no início de `run_until_done`.

### Quando rodar

| Gatilho | Como | Latência até o carro ser encontrado pela via vetorial |
| --- | --- | --- |
| Agendado | cron, APScheduler ou Celery beat a cada 5 a 15 min | até o próximo ciclo |
| Após o sync do estoque | chamar `run_until_done()` no fim do job que importa os veículos | segundos |
| Após edição pelo painel | enfileirar uma tarefa ou usar `BackgroundTasks` do FastAPI | segundos |

A via de trigramas não depende do worker: `search_text` é atualizado pela trigger no mesmo UPDATE. Um carro recém-importado já é encontrado por nome ou modelo antes de ganhar embedding.

## Endpoint de busca (FastAPI)

O endpoint replica o que o QuickSearchV4 faz no n8n, em três passos:

1. Normaliza a entrada.
2. Gera o embedding da consulta. Se a OpenAI falhar, segue só com trigramas.
3. Chama `search_formulaos_vehicles`.

O `tenant_id` vem da autenticação, nunca do corpo da requisição.

```python
# search_api.py
import os
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal

import numpy as np
from async_lru import alru_cache
from fastapi import Depends, FastAPI
from openai import AsyncOpenAI
from pgvector.psycopg import register_vector_async
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

MODEL = "text-embedding-3-small"
openai_client = AsyncOpenAI(timeout=5.0, max_retries=1)


async def _configure(conn):
    await register_vector_async(conn)


pool = AsyncConnectionPool(
    os.environ["DATABASE_URL"], open=False, configure=_configure,
    kwargs={"row_factory": dict_row},
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str | None = None      # texto livre: "SUV automático econômico"
    brand: str | None = None
    model: str | None = None
    category: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    store_ids: list[int] | None = None
    limit: int = Field(15, ge=1, le=50)


class VehicleHit(BaseModel):
    id: int
    identifier: str | None
    brand: str | None
    model: str | None
    version: str | None
    category: str | None
    store_id: int | None
    store: str | None
    model_year: int | None
    km: int | None
    price: Decimal | None
    exchange: str | None
    fuel_text: str | None
    color: str | None
    main_image: str | None
    score: float | None
    match_type: str               # exato | similar | filtro


def build_search_text(req: SearchRequest) -> str:
    """Mesma regra do n8n: junta os campos de texto, ignorando vazios e '_ALL_'."""
    parts = [req.query, req.brand, req.model, req.category]
    clean = [" ".join(p.split()) for p in parts if p and p.strip() and p.strip() not in ("null", "_ALL_")]
    return " ".join(clean)


@alru_cache(maxsize=2048)
async def embed(text: str) -> np.ndarray | None:
    try:
        resp = await openai_client.embeddings.create(model=MODEL, input=text)
        return np.array(resp.data[0].embedding, dtype=np.float32)
    except Exception:
        return None               # degrada para só trigramas


SEARCH_SQL = """
select * from search_formulaos_vehicles(
  p_query           => %(q)s,
  p_query_embedding => %(emb)s::vector,
  p_tenant_id       => %(tenant_id)s,
  p_store_ids       => %(store_ids)s,
  p_year_from       => %(year_from)s,
  p_year_to         => %(year_to)s,
  p_price_min       => %(price_min)s,
  p_price_max       => %(price_max)s,
  p_limit           => %(limit)s
)
"""


async def current_tenant_id() -> int:
    ...  # extrair do JWT / sessão do FormulaOS


@app.post("/vehicles/search", response_model=list[VehicleHit])
async def search_vehicles(req: SearchRequest, tenant_id: int = Depends(current_tenant_id)):
    q = build_search_text(req)
    emb = await embed(q.lower()) if q else None

    params = {
        "q": q or None,
        "emb": emb,
        "tenant_id": tenant_id,
        "store_ids": req.store_ids,
        "year_from": req.year_from or 1949,
        "year_to": req.year_to or date.today().year,
        "price_min": req.price_min or 0,
        "price_max": req.price_max or 100_000_000,
        "limit": req.limit,
    }
    async with pool.connection() as conn:
        cur = await conn.execute(SEARCH_SQL, params)
        return await cur.fetchall()
```

Decisões do endpoint:

- **Cache de embeddings:** `alru_cache` (pacote `async-lru`) evita chamar a OpenAI de novo para consultas repetidas. Em produção com vários processos, troque por Redis com chave `md5(texto)`.
- **`::vector` no SQL:** com `emb = None`, o psycopg envia um NULL sem tipo. O cast resolve a ambiguidade, e o array numpy passa pelo adapter do pgvector.
- **Argumentos nomeados (`=>`):** o SQL continua válido se a função ganhar parâmetros novos no fim da lista.
- **Timeout curto (5 s, 1 retry):** a busca nunca fica presa esperando a OpenAI. No pior caso, responde só com trigramas.
- **Supabase:** use a conexão direta ou o pooler em modo *session* (porta 5432). O modo *transaction* (porta 6543) não suporta prepared statements, então nele é preciso passar `prepare_threshold=None` nos `kwargs` do pool.

### Exemplo de chamada

```json
POST /vehicles/search
{ "brand": "Chevrolet", "model": "Onyx", "price_max": 90000 }
```

```json
[
  { "id": 512, "brand": "GM - Chevrolet", "model": "ONIX", "version": "ONIX HATCH LT 1.0 12V Flex 5p Mec.",
    "store": "MUNDIAL AUTOMOVEIS", "model_year": 2024, "price": 76900.00, "score": 0.0317, "match_type": "similar" }
]
```

Os valores do exemplo de resposta são ilustrativos; os campos são os de `VehicleHit`.

## Diferenças entre as tabelas e checklist

A `formulaos_vehicles` tem a mesma estrutura de negócio da `vehicles`, mas difere em chave, gatilhos e multi-tenancy. Cada diferença abaixo mudou uma decisão da implementação.

| Aspecto | `vehicles` (n8n, em produção) | `formulaos_vehicles` (backend Python) |
| --- | --- | --- |
| Chave | `identifier` (text) | `id` (int); `identifier` é único, mas secundário |
| Veículos ativos | 311 de 944 | 371 de 946 (status `Publicado`) |
| Sem marca cadastrada | 106 ativos | 139 ativos |
| Triggers existentes | nenhuma | `trg_sync_formulaos_vehicles_fields` reescreve `synced_at` e mapeia `status` para `active`/`sold` |
| Onde fica o embedding | coluna `vehicles.embedding` | tabela `formulaos_vehicle_embeddings`, para não disparar a trigger de sync |
| Como detecta texto alterado | trigger zera o embedding | `source_hash` = `md5(embedding_text)` |
| `note` | quase sempre no formato Trinix | mistura Trinix com marketing da loja; filtrado por regex |
| Multi-tenant | não | `store_id` leva a `formulaos_stores.tenant_id`; filtro `p_tenant_id` |
| Geração de embeddings | workflow n8n a cada 15 min | worker Python (agendado ou após o sync) |
| Cliente da busca | webhook QuickSearchV4 | endpoint FastAPI `/vehicles/search` |

### Checklist de implantação

O SQL das seções de banco e de função foi validado na `formulaos_vehicles` em 15/10/2026, numa transação desfeita em seguida: o backfill preencheu `search_text` em todas as 946 linhas, não alterou nenhum `synced_at` e descartou o texto de marketing das lojas.

- [ ] Aplicar a migration de colunas, tabela de embeddings e índices
- [ ] Criar a função e a trigger `trg_zz_formulaos_vehicles_search`
- [ ] Rodar o backfill com a trigger de sync desativada
- [ ] Conferir: `select count(*) from formulaos_vehicles where coalesce(search_text, '') = ''` deve voltar 0
- [ ] Criar a função `search_formulaos_vehicles`
- [ ] Rodar o worker uma vez (`run_until_done`) e conferir que todos os ativos têm embedding
- [ ] Agendar o worker ou chamá-lo no fim do job de sync
- [ ] Subir o endpoint com o `tenant_id` vindo da autenticação
- [ ] Rodar os casos de teste da próxima seção e ajustar os limiares se necessário
- [ ] Remover a coluna vazia `formulaos_vehicles.embedding`
- [ ] Rodar `get_advisors` (segurança) no Supabase: a tabela nova tem RLS ativo e nenhuma policy, o que bloqueia acesso via API pública, como pretendido

## Testes, calibração e operação

Os limiares padrão (`p_min_trgm` 0,45 e `p_min_cos` 0,30) vieram dos testes na `vehicles` e são um bom ponto de partida para a `formulaos_vehicles`, que tem o mesmo tipo de dado.

### Casos de teste

Cada caso cobre uma falha conhecida do `ILIKE`. Vale transformá-los em testes automatizados (pytest) contra um banco de staging.

| Entrada | O que verifica | Esperado |
| --- | --- | --- |
| `brand=Chevrolet, model=Onyx` | typo + marca sem padrão | só Onix no topo, incluindo os sem marca cadastrada |
| `query=corola` | typo | Corolla com `match_type = exato` |
| `query=hb 20` | espaço no nome | HB20 e HB20S |
| `query=volks polo` | alias de marca | Polo, marca "VW - VolksWagen" |
| `query=cronos` | veículo sem marca (só no `note`) | Cronos da Kadosh, com marca Fiat extraída |
| `query=picape diesel 4x4` | intenção (via vetorial) | só picapes diesel |
| `query=SUV automático econômico` | intenção sem nome de modelo | SUVs automáticos, `match_type = similar` |
| sem texto, `year_from=2020, price_max=80000` | comportamento antigo | lista por preço, `match_type = filtro` |
| texto qualquer com OpenAI fora do ar | degradação | resultados só por trigramas, sem erro 500 |

### Calibrar os limiares

Para ver onde cortar, rode a consulta com limiares zerados e observe os scores dos acertos e dos erros:

```sql
select brand, model, version, trgm_score, vector_score, match_type
from search_formulaos_vehicles(
  p_query    => 'onyx',
  p_min_trgm => 0,      -- tudo entra; olhe onde os acertos terminam
  p_limit    => 30
);
```

- **Muitos falsos positivos** (um Cruze aparecendo na busca por Onix): suba `p_min_trgm` para 0,5. O custo é perder alguns typos.
- **Typos sumindo** ("onyx" sozinho tem trigrama de 0,40 contra "onix"): hoje quem salva esse caso é a via vetorial. Se aparecer um typo que nenhuma das vias pega, baixe `p_min_trgm` para 0,40 em vez de mexer no cosseno.
- **Intenção trazendo lixo** ("SUV" retornando hatches): suba `p_min_cos` para 0,35. Nesse modelo, acertos ficam entre 0,50 e 0,60 e o ruído abaixo de 0,40.

### Monitoramento

```sql
-- veículos ativos sem embedding atualizado (deve tender a 0 depois de cada ciclo do worker)
select count(*)
from formulaos_vehicles v
left join formulaos_vehicle_embeddings e on e.vehicle_id = v.id
where v.active
  and (e.vehicle_id is null or e.source_hash <> md5(v.embedding_text));
```

Vale logar, por busca, o texto, a quantidade de resultados e se o embedding falhou. Buscas com zero resultados mostram vocabulário que falta nos aliases da trigger.

### Custo

O `text-embedding-3-small` custa cerca de US$ 0,02 por milhão de tokens (preço de tabela da OpenAI, aproximado; confira antes de orçar). A carga inicial de 371 veículos tem perto de 30 mil tokens, ou menos de 1 centavo de dólar. Cada busca gasta de 4 a 10 tokens, e o cache elimina as repetidas.

### Problemas comuns

| Sintoma | Causa provável | Correção |
| --- | --- | --- |
| Veículo novo não aparece | não está `active` ou não passou nos filtros de ano e preço | conferir `status = 'Publicado'` e as faixas padrão |
| Busca por intenção devolve vazio | veículos sem embedding | rodar o worker e a consulta de monitoramento |
| `search_text` vazio após insert | trigger com nome que roda antes da de sync | manter o prefixo `trg_zz_` |
| `synced_at` mudando sem sync real | algum processo está gravando embedding na própria `formulaos_vehicles` | gravar só em `formulaos_vehicle_embeddings` |
| `operator does not exist: vector <=> unknown` | embedding enviado sem cast ou sem `register_vector` | usar `%(emb)s::vector` e registrar o adapter no pool |
| Erro de prepared statement no Supabase | pooler em modo transaction (6543) | usar 5432 ou `prepare_threshold=None` |
| Carros vendidos na resposta | sync do estoque parado | o sync da `vehicles` está parado desde 03/09/2026; verificar o da `formulaos_vehicles` (último em 16/09/2026) |
