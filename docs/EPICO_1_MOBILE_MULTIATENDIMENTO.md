# SPEC TÉCNICA — ÉPICO 1
## Multiatendimento Mobile Responsivo + Quick Wins Fase 1 Tex

> Documento de execução técnica para Claude Code.
> Prazo: 5-7 dias úteis a partir de 02/06/2026.
> Cliente-piloto: Tex (lojista Auto Shopping Fórmula).

---

## 1. OBJETIVO

Entregar à Tex (Fernando como gestor, Cauê como vendedor) a Fase 1 do sistema: multiatendimento operável 100% pelo celular, com tags funcionais e sincronização básica entre CRM e conversas. Resolve o problema central da reunião: perda de visibilidade do gestor sobre os leads pagos.

## 2. ESCOPO DA FASE 1

### Dentro do escopo (P0 — obrigatório)
- Layout mobile responsivo (375px-768px) do multiatendimento
- Lista de conversas com últimas mensagens visíveis
- Tela de conversa funcional com envio/recebimento em tempo real
- Envio de mensagem de texto
- Recebimento de mensagens em tempo real (Supabase Realtime)
- Indicador de mensagem não lida
- Sistema básico de tags (criar tag pessoal, aplicar na conversa/lead, filtrar lista por tag)
- Criação automática de lead no CRM quando conversa nova entra
- Mudança de status do lead refletida na conversa
- Indicador visual de quem está atendendo a conversa
- Autenticação por usuário com isolamento por tenant

### Dentro do escopo (P1 — esforçar pra entregar)
- Envio de foto e áudio
- Aplicar tag inline na conversa (sem ir pro CRM)
- Visão filtrada: "minhas conversas" vs "todas" (gestor)
- Pesquisa por nome ou telefone do lead

### Fora do escopo (Fase 2)
- Envio de PDF e vídeo
- Notificações push
- PWA / offline
- Configuração avançada do Rafael
- Dashboard de funil
- Disparos em massa
- Análise IA de qualidade

---

## 3. ARQUITETURA TÉCNICA

### Stack
- **Frontend:** React (via Lovable como base, edição direta no código se necessário)
- **UI:** Tailwind CSS + shadcn/ui
- **Backend:** Supabase (PostgreSQL + Auth + Realtime + Storage)
- **Mensageria:** integração existente com WhatsApp (manter pipeline atual via N8N)
- **State:** Zustand para estado global (conversas, mensagens, usuário)

### Estrutura de pastas sugerida

```
src/
├── components/
│   ├── multiatendimento/
│   │   ├── ConversationList.tsx
│   │   ├── ConversationListItem.tsx
│   │   ├── ConversationView.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── MessageInput.tsx
│   │   ├── MediaUploader.tsx
│   │   ├── TagSelector.tsx
│   │   ├── StatusBadge.tsx
│   │   └── MobileShell.tsx
│   ├── crm/
│   │   ├── LeadCard.tsx
│   │   ├── LeadStatusSelect.tsx
│   │   └── TagPill.tsx
│   └── shared/
│       ├── Avatar.tsx
│       ├── Timestamp.tsx
│       └── UnreadBadge.tsx
├── hooks/
│   ├── useConversations.ts
│   ├── useMessages.ts
│   ├── useTags.ts
│   ├── useRealtimeMessages.ts
│   └── useAuth.ts
├── stores/
│   ├── conversationStore.ts
│   ├── messageStore.ts
│   └── authStore.ts
├── lib/
│   ├── supabase.ts
│   ├── whatsapp.ts
│   └── utils.ts
├── pages/
│   ├── Conversas.tsx          # rota principal mobile
│   ├── Conversa.tsx           # rota da conversa individual
│   ├── CRM.tsx
│   └── LeadDetalhe.tsx
└── types/
    └── index.ts
```

---

## 4. MODELO DE DADOS (SUPABASE)

### Tabelas principais

```sql
-- Tenants (Auto Shopping é o tenant pai; Lojistas são sub-tenants)
create table tenants (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  tipo text check (tipo in ('auto_shopping', 'lojista', 'master')),
  parent_tenant_id uuid references tenants(id),
  created_at timestamptz default now()
);

-- Usuários (vendedores, gestores)
create table users (
  id uuid primary key references auth.users(id),
  tenant_id uuid not null references tenants(id),
  nome text not null,
  email text not null,
  role text check (role in ('master', 'gestor', 'vendedor', 'lojista')),
  avatar_url text,
  ativo boolean default true,
  created_at timestamptz default now()
);

-- Leads
create table leads (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  lojista_id uuid references tenants(id),
  nome text,
  telefone text not null,
  email text,
  status text default 'novo' check (status in (
    'novo', 'em_atendimento', 'qualificado',
    'em_negociacao', 'fechado', 'perdido', 'vacuo'
  )),
  motivo_perda text,
  veiculo_interesse text,
  vendedor_id uuid references users(id),
  origem text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Conversas (uma por lead)
create table conversas (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  lead_id uuid not null references leads(id) on delete cascade,
  numero_whatsapp text not null,
  vendedor_id uuid references users(id),
  ultima_mensagem_em timestamptz default now(),
  ultima_mensagem_preview text,
  nao_lida_count int default 0,
  arquivada boolean default false,
  created_at timestamptz default now()
);

-- Mensagens
create table mensagens (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  conversa_id uuid not null references conversas(id) on delete cascade,
  direcao text check (direcao in ('entrada', 'saida')),
  tipo text check (tipo in ('texto', 'foto', 'audio', 'pdf', 'video', 'sistema')),
  conteudo text,
  mediaUrl text,
  enviado_por_id uuid references users(id),
  enviado_por_agente boolean default false,  -- true quando é o Rafael
  whatsapp_message_id text,
  status text default 'enviada' check (status in (
    'enviada', 'entregue', 'lida', 'falhou'
  )),
  created_at timestamptz default now()
);

-- Tags
create table tags (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  user_id uuid references users(id),  -- null = tag global do tenant
  nome text not null,
  cor text default '#3b82f6',
  created_at timestamptz default now(),
  unique(tenant_id, user_id, nome)
);

-- Relação lead ↔ tag
create table lead_tags (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads(id) on delete cascade,
  tag_id uuid not null references tags(id) on delete cascade,
  aplicada_por uuid references users(id),
  created_at timestamptz default now(),
  unique(lead_id, tag_id)
);

-- Anotações privadas do vendedor na ficha do lead
create table anotacoes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  lead_id uuid not null references leads(id) on delete cascade,
  user_id uuid not null references users(id),
  conteudo text not null,
  created_at timestamptz default now()
);
```

### Policies RLS (críticas)

```sql
-- Habilitar RLS em todas as tabelas
alter table leads enable row level security;
alter table conversas enable row level security;
alter table mensagens enable row level security;
alter table tags enable row level security;
alter table lead_tags enable row level security;
alter table anotacoes enable row level security;

-- Policy padrão: usuário vê apenas dados do seu tenant
create policy "tenant_isolation_leads" on leads
  for all using (
    tenant_id in (
      select tenant_id from users where id = auth.uid()
    )
  );

-- Vendedor vê apenas seus próprios leads; gestor vê todos do tenant
create policy "vendedor_sees_own_leads" on leads
  for select using (
    tenant_id in (select tenant_id from users where id = auth.uid())
    and (
      vendedor_id = auth.uid()
      or exists (
        select 1 from users
        where id = auth.uid() and role in ('gestor', 'master')
      )
    )
  );

-- Tags pessoais: vendedor só vê as suas; gestor vê todas
create policy "tags_visibility" on tags
  for select using (
    tenant_id in (select tenant_id from users where id = auth.uid())
    and (
      user_id = auth.uid()
      or user_id is null
      or exists (
        select 1 from users
        where id = auth.uid() and role in ('gestor', 'master')
      )
    )
  );
```

(Aplicar padrão similar nas demais tabelas)

---

## 5. FLUXOS PRINCIPAIS

### Fluxo 1: Vendedor recebe nova conversa

1. WhatsApp recebe mensagem nova (via webhook → N8N)
2. N8N detecta se telefone já tem lead → se não, cria lead novo
3. N8N cria conversa vinculada ao lead
4. N8N insere mensagem inicial
5. Rafael (agente IA) responde automaticamente
6. Quando Rafael atinge critério de qualificação ou tempo limite, atribui conversa a um vendedor via rodízio
7. Vendedor recebe conversa na lista (Supabase Realtime atualiza UI)
8. Mensagem aparece como "não lida" na lista do vendedor

### Fluxo 2: Vendedor responde no mobile

1. Vendedor toca na conversa na lista
2. Tela de conversa abre com histórico completo
3. Mensagens marcadas como lidas (update no `nao_lida_count`)
4. Vendedor digita resposta e envia
5. Frontend insere mensagem no Supabase com `direcao = 'saida'` e `status = 'enviada'`
6. Trigger ou edge function envia para API WhatsApp
7. Webhook da Meta confirma status (entregue, lida, falhou)
8. UI atualiza status em tempo real

### Fluxo 3: Vendedor aplica tag

1. Na ficha do lead OU na conversa, vendedor toca em "+ tag"
2. Modal/bottom sheet abre com tags existentes do vendedor + opção "criar nova"
3. Vendedor seleciona ou cria
4. Tag é aplicada (insert em `lead_tags`)
5. UI mostra a tag na ficha e na lista de conversas
6. Filtro de tag funcional na lista

### Fluxo 4: Gestor monitora atendimento

1. Gestor entra na tela "Todas as conversas" (visão consolidada)
2. Vê todas as conversas com nome do vendedor responsável
3. Pode filtrar por: vendedor, status do lead, tag, período
4. Toca em qualquer conversa para ver histórico completo (sem assumir)
5. Pode adicionar anotação privada à ficha do lead

---

## 6. COMPONENTES — ESPECIFICAÇÃO DETALHADA

### MobileShell

Container principal para mobile. Barra superior fixa com nome do usuário/tenant, navegação inferior (Conversas, CRM, Perfil).

**Props:** `{ children, currentTab }`

**Comportamento:**
- Detecta viewport < 768px e ativa modo mobile
- Navegação inferior sticky
- Header com 56px de altura, navegação 64px

### ConversationList

Lista de conversas com últimas mensagens.

**Layout mobile:**
- Avatar à esquerda (40px)
- Nome do lead em negrito + preview da última mensagem
- Timestamp à direita (relativo: "agora", "5 min", "ontem")
- Badge de não lidas se `nao_lida_count > 0`
- Tag colorida abaixo do nome se houver tag aplicada
- Status do lead como pequeno badge

**Filtros (top bar):**
- "Minhas" | "Todas" (visível só pra gestor)
- Busca por nome/telefone
- Filtro de tags (chips)
- Filtro de status (chips)

**Comportamento:**
- Pull to refresh
- Infinite scroll (carrega 30 por vez)
- Tap → abre conversa
- Long press → menu de ações (arquivar, marcar lida, ver lead)

### ConversationView

Tela de conversa individual.

**Layout mobile:**
- Header com avatar + nome do lead + status do lead (badge)
- Botão de voltar à esquerda
- Botão de "ver ficha" à direita (abre drawer/sheet com dados do lead)
- Área de mensagens com scroll automático para baixo
- Input fixo na parte inferior

**MessageBubble:**
- Recebidas à esquerda, enviadas à direita
- Bolhas com border-radius 12px, padding 10px 14px
- Timestamp pequeno abaixo da bolha
- Status (✓, ✓✓, ✓✓ azul) para mensagens enviadas
- Mensagens do Rafael com indicador "🤖 Rafael" pequeno
- Foto e áudio com player inline

**MessageInput:**
- TextField multiline com auto-resize (max 4 linhas)
- Botão de mídia (clip) → abre opções (câmera, galeria, áudio, doc)
- Botão de enviar (avião) ativo apenas com texto ou mídia
- Pressionar e segurar para gravar áudio

### TagSelector

Bottom sheet (mobile) ou popover (desktop) para selecionar/criar tag.

**Comportamento:**
- Lista tags existentes do vendedor + tags globais do tenant
- Campo de busca no topo
- Botão "+ Criar nova tag" abre input + color picker
- Multi-select (várias tags por lead)
- Aplicar ao tocar; confirmar com botão no rodapé

### LeadCard (CRM)

Card resumo do lead na lista do CRM.

**Mobile:**
- Nome + telefone
- Status badge
- Tags como pills
- Última mensagem (preview)
- Vendedor responsável
- Tap → abre LeadDetalhe

### LeadDetalhe

Página/sheet com dados completos do lead.

**Seções:**
- Cabeçalho: nome, telefone, status (com select para mudar)
- Tags aplicadas (com botão de + tag)
- Veículo de interesse
- Última interação
- Anotações privadas (vendedor + gestor podem ver)
- Histórico de mudanças de status
- Botão "Abrir conversa"

---

## 7. INTEGRAÇÃO COM WHATSAPP

### Pipeline atual (manter)
- Webhook da Meta → N8N → Supabase (`mensagens`)
- Frontend reage via Supabase Realtime

### Envio do mobile
- Frontend insere em `mensagens` com `direcao = 'saida'`
- Edge function do Supabase (ou N8N webhook) detecta insert e envia via API WhatsApp
- Resposta da API atualiza `whatsapp_message_id` e `status`

### Estrutura de mídia
- Mídia enviada do mobile vai para Supabase Storage primeiro
- URL pública (ou signed URL) é salva em `mensagens.mediaUrl`
- Edge function pega a URL e envia ao WhatsApp via API
- Bucket: `whatsapp-media`, com policy por tenant

---

## 8. SUPABASE REALTIME

Subscrições obrigatórias:

```typescript
// Em useConversations
supabase
  .channel('conversas-tenant')
  .on('postgres_changes', {
    event: '*',
    schema: 'public',
    table: 'conversas',
    filter: `tenant_id=eq.${tenantId}`
  }, handleConversationUpdate)
  .subscribe()

// Em useMessages (apenas conversa ativa)
supabase
  .channel(`mensagens-${conversaId}`)
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'mensagens',
    filter: `conversa_id=eq.${conversaId}`
  }, handleNewMessage)
  .subscribe()
```

**Atenção:** desinscrever ao desmontar componentes para evitar memory leak.

---

## 9. CRITÉRIOS DE ACEITAÇÃO (CHECKLIST)

### Funcionais
- [ ] Vendedor consegue logar pelo celular e ver suas conversas
- [ ] Lista de conversas carrega em < 2s em 4G
- [ ] Tap em conversa abre histórico completo em < 1s
- [ ] Vendedor envia mensagem de texto e recebe confirmação visual de envio
- [ ] Mensagem recebida aparece em tempo real (sem refresh)
- [ ] Badge de não lida atualiza corretamente
- [ ] Vendedor cria tag nova e aplica em conversa
- [ ] Filtro de lista por tag funciona
- [ ] Gestor entra em "Todas" e vê conversas de todos os vendedores
- [ ] Gestor pode adicionar anotação privada em qualquer ficha
- [ ] Lead novo é criado automaticamente quando conversa nova chega
- [ ] Status do lead mudado na ficha reflete na conversa (e vice-versa)

### Não funcionais
- [ ] Layout funcional em iPhone SE (375x667) e Android médio (360x640)
- [ ] Testado em Chrome mobile, Safari iOS, Android Chrome
- [ ] Sem erros no console em produção
- [ ] RLS validada: vendedor A não consegue acessar dados de vendedor B via API
- [ ] Tempo de envio (do toque ao recebido pela API) < 2s
- [ ] Lighthouse score mobile > 75 em performance

### P1 (se der tempo)
- [ ] Envio de foto funcional
- [ ] Envio de áudio funcional
- [ ] Busca por nome/telefone funcional

---

## 10. ORDEM SUGERIDA DE EXECUÇÃO (5-7 DIAS)

### Dia 1 — Base e dados
- Setup do projeto (se ainda não estiver pronto)
- Criação das tabelas no Supabase
- Habilitar RLS e criar policies
- Seed de dados de teste (2 vendedores, 1 gestor, 20 leads, 20 conversas, 100 mensagens)

### Dia 2 — Listagem mobile
- MobileShell com navegação
- ConversationList com filtros básicos
- Hook `useConversations` com Realtime
- Autenticação funcional

### Dia 3 — Tela de conversa
- ConversationView com histórico
- MessageBubble (texto)
- MessageInput (texto apenas)
- Hook `useMessages` com Realtime

### Dia 4 — Envio e sincronização
- Pipeline de envio (insert no Supabase → edge function → API WhatsApp)
- Status de mensagem (enviada, entregue, lida)
- Marcação de mensagens como lidas

### Dia 5 — Tags e CRM básico
- Tabelas e RLS de tags
- TagSelector
- Aplicação de tag e filtro
- LeadDetalhe básico

### Dia 6 — Polimento e gestão
- Visão de gestor ("Todas as conversas")
- Anotações privadas
- Indicador de quem está atendendo

### Dia 7 — Testes, P1 e deploy
- Testes em dispositivos reais (iPhone e Android)
- Envio de foto (P1)
- Bug fixes
- Deploy para staging com Tex testando

---

## 11. RISCOS E MITIGAÇÕES

| Risco | Mitigação |
|-------|-----------|
| Supabase Realtime não escalar com muitas conversas | Subscrição filtrada por tenant; teste de carga com 50 conversas simultâneas |
| Vídeo redondo (PTT) chega de cliente e quebra UI | Exibir como "tipo não suportado" no MessageBubble, com fallback de download |
| Lead duplicado quando telefone existe em outro tenant | Lead é único por (tenant_id + telefone). Validar no insert |
| Vendedor A acessa lead de Vendedor B via console | Validar RLS com testes automatizados antes do deploy |
| Edge function de envio falha silenciosamente | Logs estruturados + retry com backoff exponencial + alerta para admin |
| Mobile lento em 3G | Lazy load de mensagens antigas; cache de últimas 50 conversas em IndexedDB |

---

## 12. INSTRUÇÕES PARA O CLAUDE CODE

Ao executar este épico:

1. **Antes de qualquer query, confirme o `tenant_id` do usuário autenticado.** Nenhuma operação sem esse filtro.
2. **Toda nova tabela = RLS ativada + policy de tenant.** Sem exceção.
3. **Use Supabase Realtime de forma cirúrgica.** Não inscreva em tabelas inteiras — filtre por tenant ou por conversa ativa.
4. **Componentes shadcn/ui sempre.** Não crie do zero se já existe (Button, Input, Sheet, etc).
5. **Mobile-first nos CSS.** Estilize primeiro para 375px e progrida com `md:` `lg:`.
6. **Testes manuais em dispositivo real, não só DevTools mobile.** A diferença é grande.
7. **Edge functions do Supabase para integração WhatsApp.** Não chamar API externa direto do frontend.
8. **Logs estruturados em JSON** em todas as edge functions.
9. **Não tente substituir o pipeline N8N existente.** Apenas integre. O Rafael continua rodando lá.
10. **Cada PR/commit deve passar nos critérios de aceitação relevantes** antes do merge.

---

## 13. ENTREGÁVEIS DE FECHAMENTO DA FASE 1

Ao final da semana:

- [ ] URL de staging com sistema funcional
- [ ] Vídeo (Loom ou similar) de 3-5 min demonstrando os fluxos principais no celular
- [ ] Lista de bugs conhecidos e limitações documentadas
- [ ] Plano de teste para o Fernando e Cauê (passo a passo do que validar)
- [ ] Data marcada para sessão de validação com a Tex
- [ ] Cronograma da Fase 2 confirmado com a Tex

---

*Documento criado em: 29/05/2026*
*Sprint: 1 (Estabilização e Quick Wins)*
*Owner técnico: Hero + André*
