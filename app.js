// Formula OS — frontend conectado à API REST + cookie de sessão.

const ROLE_LABELS = {
  master: {
    label: "Master",
    eyebrow: "Camada Master",
    title: "Comando comercial do ecossistema",
    heroKicker: "COLLAB / Arara Azul",
    heroTitle: "A visão do dono da plataforma: tenants, receita, custos e saúde da IA.",
    heroText:
      "Acompanhamento executivo de todos os clientes, lojistas futuros, consumo de WhatsApp, billing, margem e qualidade do SDR.",
    search: "Buscar tenant, lojista, lead ou custo",
    nav: {
      overview: "Cockpit master",
      crm: "Leads globais",
      inbox: "Auditoria de atendimento",
      vehicles: "Inventário global",
      stores: "Tenants",
      billing: "Billing e custos",
    },
    allowedViews: ["overview", "crm", "inbox", "vehicles", "stores", "billing"],
    commands: [
      ["Controle financeiro", "Margem por cliente, cobrança recorrente, inadimplência e custo variável do WhatsApp.", "Abrir billing"],
      ["Saúde da IA", "Taxa de qualificação, transferência para humano, retrabalho e leads perdidos por tenant.", "Ver métricas"],
      ["Expansão comercial", "Compare performance do shopping com lojistas que podem virar assinantes diretos.", "Mapear oportunidades"],
    ],
    decisions: [
      ["Tenant com custo acima da média", "Radar Automóveis consumiu 22% mais conversas por lead. Revisar prompt de qualificação."],
      ["Cobrança próxima do vencimento", "4 lojistas com fatura aberta para renovação automática."],
      ["Oportunidade de expansão", "GX Auto tem 91% dos leads respondidos em menos de 5 minutos."],
    ],
  },
  shopping: {
    label: "Gestor",
    eyebrow: "Camada Auto Shopping",
    title: "Gestão do shopping, lojistas e atendimento",
    heroKicker: "Auto Shopping Formula",
    heroTitle: "A sala de comando do shopping: estoque, lojistas, CRM e atendimento humano.",
    heroText:
      "O gestor acompanha todos os leads do SDR, performance das lojas, fila de atendimento, veículos publicados e gargalos da operação.",
    search: "Buscar lead, carro ou lojista",
    nav: {
      overview: "Panorama",
      crm: "Governança de leads",
      inbox: "Auditoria de atendimento",
      vehicles: "Estoque central",
      stores: "Lojistas assinantes",
      team: "Equipe do Shopping",
      billing: "Monetização",
    },
    allowedViews: ["overview", "crm", "inbox", "vehicles", "stores", "billing", "team"],
    commands: [
      ["Fila humana", "Atendentes assumem conversas quando o SDR identifica negociação, troca ou dúvida sensível.", "Abrir inbox"],
      ["Performance por lojista", "Veja quem gera mais leads, quem responde melhor e quem está deixando oportunidade esfriar.", "Comparar lojas"],
      ["Estoque vivo", "O cadastro dos lojistas alimenta o site, o agente e o CRM em uma única base.", "Ver veículos"],
    ],
    decisions: [
      ["Fila humana crescendo", "Conversas pedem atendente para negociação de troca."],
      ["Loja com baixa atualização", "Algumas lojas estão há dias sem renovar estoque."],
      ["Modelo em alta", "Honda City gerou leads qualificados na semana."],
    ],
  },
  lojista: {
    label: "Lojista",
    eyebrow: "Camada Lojista",
    title: "Seus carros, seus leads e seu vendedor virtual",
    heroKicker: "Minha loja",
    heroTitle: "O painel do lojista: publicar veículos, receber leads e conectar o WhatsApp.",
    heroText: "O lojista vê somente sua loja, seus atendimentos e seus resultados. Nada de dados dos concorrentes.",
    search: "Buscar meu lead ou meu carro",
    nav: {
      overview: "Minha loja",
      crm: "Meus leads",
      inbox: "Minhas conversas",
      vehicles: "Meus veículos",
      stores: "Minha loja",
      team: "Minha equipe",
      billing: "WhatsApp agente",
    },
    allowedViews: ["overview", "crm", "inbox", "vehicles", "billing", "team"],
    commands: [
      ["QR Code do agente", "Conecte seu WhatsApp para o SDR vender como assistente virtual da sua loja.", "Gerar QR"],
      ["Cadastro rápido", "Fotos, preço, versão, quilometragem e condições entram no estoque do shopping.", "Cadastrar carro"],
      ["Leads protegidos", "Você enxerga somente os leads gerados para sua loja, com histórico completo da conversa.", "Ver meus leads"],
    ],
    decisions: [
      ["Lead quente sem retorno", "Há leads com Score >= 90 aguardando contato."],
      ["QR Code expira em breve", "Renove a sessão para manter o agente ativo."],
      ["Preço competitivo", "Verifique se seus modelos estão alinhados com a média do shopping."],
    ],
  },
};

const STAGES = ["Novo", "Qualificado", "Humano", "Visita", "Fechado"];

let currentUser = null;
let stores = [];
let vehicles = [];
let leads = [];
let conversations = [];
let currentConversationId = null;
let funnelData = { metrics: {}, total_leads: 0 };
let teamData = [];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

// ---------- API helpers ----------
async function api(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = isFormData
    ? { ...(options.headers || {}) }
    : { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(path, {
    credentials: "same-origin",
    headers,
    ...options,
  });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (err) {
    if (!response.ok) {
      const httpErr = new Error(text || `Erro HTTP ${response.status}`);
      httpErr.status = response.status;
      throw httpErr;
    }
  }
  if (!response.ok) {
    const err = new Error(payload.error || payload.detail || text || `Erro ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return payload;
}

// ---------- Normalização (aliases legados para reuso de renderers) ----------
function normalizeLead(lead) {
  let displayStage = lead.stage;
  if (displayStage === "Em atendimento") displayStage = "Humano";
  if (displayStage === "Em negociação") displayStage = "Visita";
  if (displayStage === "Perdido" || displayStage === "Vácuo") displayStage = "Fechado";
  return { ...lead, car: lead.car_interest, store: lead.store_name, stage: displayStage, original_stage: lead.stage };
}
function normalizeVehicle(v) {
  return {
    ...v,
    store: v.store_name,
    img: v.image_path,
    meta: [v.mileage, v.transmission, v.fuel].filter(Boolean),
  };
}
function normalizeStore(s) {
  return {
    ...s,
    response: s.response_time || "—",
    cost: s.monthly_cost,
    revenue: s.monthly_revenue,
  };
}
function normalizeConversation(c) {
  return {
    ...c,
    lead: c.lead_name || c.customer_phone || "Lead",
    store: c.store_name,
    messages: c.messages ? c.messages.map((m) => ({
      type: m.sender === "agent" ? "agent" : m.sender === "human" ? "human" : "lead",
      text: m.body,
    })) : null,
  };
}

function currentRole() { return currentUser?.role || "master"; }

function myStoreName() {
  if (currentUser?.store_id) {
    const store = stores.find((s) => s.id === currentUser.store_id);
    return store?.name || "Minha loja";
  }
  return "Minha loja";
}

// ---------- DOM refs ----------
const metricsGrid = $("#metricsGrid");
const decisionList = $("#decisionList");
const pipelineBars = $("#pipelineBars");
const roleCommandGrid = $("#roleCommandGrid");
const kanban = $("#kanban");
const storeFilter = $("#storeFilter");
const sellerFilter = $("#sellerFilter");
const stageFilter = $("#stageFilter");
const conversationList = $("#conversationList");
const messagesEl = $("#messages");
const leadDetails = $("#leadDetails");
const vehicleGrid = $("#vehicleGrid");
const storeTable = $("#storeTable");
const costList = $("#costList");
const toast = $("#toast");
const modalLayer = $("#modalLayer");
const loginLayer = $("#loginLayer");
const sessionButton = $("#sessionButton");

// ---------- Carga / refresh ----------
async function fetchAll() {
  const [s, v, l, c, f, t] = await Promise.all([
    api("/api/stores"),
    api("/api/vehicles"),
    api("/api/leads"),
    api("/api/conversations"),
    api("/api/dashboard/funnel"),
    api("/api/dashboard/team").catch(() => ({ team: [] })),
  ]);
  stores = (s.stores || []).map(normalizeStore);
  vehicles = (v.vehicles || []).map(normalizeVehicle);
  leads = (l.leads || []).map(normalizeLead);
  funnelData = f || { metrics: {}, total_leads: 0 };
  teamData = t.team || [];
  const baseConvs = c.conversations || [];

  conversations = baseConvs.map(normalizeConversation);
  if (!conversations.find((conv) => conv.id === currentConversationId)) {
    currentConversationId = conversations[0]?.id ?? null;
  }
}

async function refreshAndRender() {
  await fetchAll();
  renderEverything();
}

// ---------- Filtros por papel (RBAC já é server-side; client só esconde UI) ----------
function allowedLeads() { return leads; }
function allowedVehicles() { return vehicles; }
function allowedConversations() { return conversations; }

// ---------- Setup de papel após login ----------
function applyRole() {
  const role = currentRole();
  const config = ROLE_LABELS[role];

  $("#roleEyebrow").textContent = config.eyebrow;
  $("#pageTitle").textContent = config.title;
  $("#heroKicker").textContent = role === "lojista" ? myStoreName() : config.heroKicker;
  $("#heroTitle").textContent = config.heroTitle;
  $("#heroText").textContent = config.heroText;
  $("#globalSearch").placeholder = config.search;
  sessionButton.textContent = currentUser ? `${currentUser.name} · Sair` : "Entrar";
  sessionButton.title = currentUser ? "Clique para sair da conta e alternar de perfil" : "Entrar no portal";

  updateNavigation(config);

  const activeView = $(".view.active")?.id;
  if (!config.allowedViews.includes(activeView)) showView("overview");
}

function updateNavigation(config) {
  $$("[data-view]").forEach((btn) => {
    const view = btn.dataset.view;
    const label = btn.querySelector(".nav-label");
    label.textContent = config.nav[view] || btn.dataset.navDefault;
    const allowed = config.allowedViews.includes(view);
    btn.hidden = !allowed;
    btn.disabled = !allowed;
    btn.classList.toggle("is-locked", !allowed);
  });
}

function showView(viewId) {
  const config = ROLE_LABELS[currentRole()];
  const target = config.allowedViews.includes(viewId) ? viewId : "overview";
  $$("[data-view]").forEach((item) => item.classList.toggle("active", item.dataset.view === target));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === target));
}

// ---------- Render principal ----------
function renderEverything() {
  renderOverview();
  renderFilters();
  renderKanban();
  renderConversations();
  renderChat();
  renderVehicles();
  renderStores();
  renderTeam();
  renderCosts();
}

function renderOverview() {
  const config = ROLE_LABELS[currentRole()];
  const metrics = computeMetrics();
  const pipeline = computePipeline();

  metricsGrid.innerHTML = metrics
    .map(
      ([label, value, description, trend]) => `
    <article class="metric-card">
      <span class="eyebrow">${label}</span>
      <strong>${value}</strong>
      <p>${description}</p>
      <span class="trend">${trend}</span>
    </article>
  `
    )
    .join("");

  roleCommandGrid.innerHTML = config.commands
    .map(
      ([title, description, action]) => `
    <article class="command-card">
      <div>
        <span class="eyebrow">${config.label}</span>
        <h3>${title}</h3>
        <p>${description}</p>
      </div>
      <button class="ghost-button" type="button">${action}</button>
    </article>
  `
    )
    .join("");

  roleCommandGrid.querySelectorAll("button").forEach((button, index) => {
    button.addEventListener("click", () => handleCommand(config.commands[index][2]));
  });

  decisionList.innerHTML = config.decisions
    .map(
      ([title, description]) => `
    <div class="decision-item">
      <strong>${title}</strong>
      <p>${description}</p>
    </div>
  `
    )
    .join("");

  pipelineBars.innerHTML = pipeline
    .map(
      ([label, percent, total]) => `
    <div class="bar-row">
      <span>${label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${percent}%"></div></div>
      <strong>${total}</strong>
    </div>
  `
    )
    .join("");
}

function computeMetrics() {
  const role = currentRole();
  if (role === "master") {
    const recurringRevenue = stores.reduce((sum, s) => sum + (Number(s.revenue) || 0), 0);
    const whatsappCost = stores.reduce((sum, s) => sum + (Number(s.cost) || 0), 0);
    return [
      ["Tenants ativos", String(stores.filter((s) => s.status === "Ativo").length), "Clientes e lojistas com operação ligada", "+ operação viva"],
      ["MRR projetado", formatMoney(recurringRevenue), "Mensalidades, add-ons e setup", "+ receita"],
      ["Custo WhatsApp", formatMoney(whatsappCost), "Conversas, templates e handoff humano", "controlado"],
      ["NPS médio", "73", "Satisfação dos clientes atendidos", "+5 pts"],
    ];
  }
  if (role === "shopping") {
    return [
      ["Leads no funil", String(leads.length), "Todos os lojistas do shopping", "+ atualizado"],
      ["Tempo médio resposta", "3m 18s", "SDR + atendimento humano", "-41s"],
      ["Carros cadastrados", String(vehicles.length), "Estoque consolidado", "+ estoque vivo"],
      ["Lojistas ativos", String(stores.filter((s) => s.type === "Lojista" && s.status === "Ativo").length), "Com agente e CRM habilitados", "online"],
    ];
  }
  const aguardando = conversations.filter(c => !c.owner_name && c.status !== 'Arquivado').length;
  const concluidos = conversations.filter(c => c.status === 'Fechado' || c.archived).length;
  return [
    ["Aguardando", String(aguardando), "Atendimentos na fila", "+ urgentes"],
    ["Concluídos", String(concluidos), "Conversas encerradas", "+ sucesso"],
    ["Espera média", "2m 14s", "Tempo até o 1º contato", "-18s"],
    ["Atendimento", "14m 30s", "Duração média do chat", "estável"],
  ];
}

function computePipeline() {
  const total = Math.max(funnelData.total_leads, 1);
  return STAGES.map((stage) => {
    const count = funnelData.metrics[stage] || 0;
    return [stage, Math.round((count / total) * 100), String(count)];
  });
}

function handleCommand(action) {
  const n = action.toLowerCase();
  if (n.includes("cadastrar carro")) openVehicleModal();
  else if (n.includes("qr")) runQrAction();
  else if (n.includes("billing") || n.includes("tenant")) showView("billing");
  else if (n.includes("lead") || n.includes("métrica")) showView("crm");
  else if (n.includes("inbox")) showView("inbox");
  else if (n.includes("veículo") || n.includes("carro")) showView("vehicles");
  else if (n.includes("loja")) showView(currentRole() === "lojista" ? "overview" : "stores");
  if (!n.includes("qr") && !n.includes("cadastrar carro")) showToast(action);
}

function renderFilters() {
  const role = currentRole();
  const visible = role === "lojista"
    ? stores.filter((s) => s.id === currentUser?.store_id)
    : stores.filter((s) => s.type === "Lojista");
  const allLabel = role === "lojista" ? "Minha loja" : "Todos os lojistas";
  storeFilter.innerHTML =
    `<option value="todos">${allLabel}</option>` +
    visible.map((s) => `<option value="${s.name}">${s.name}</option>`).join("");

  if (sellerFilter) {
    if (role === "vendedor") {
      sellerFilter.hidden = true;
    } else {
      sellerFilter.hidden = false;
      const sellers = teamData || [];
      sellerFilter.innerHTML =
        `<option value="todos">Todos os vendedores</option>` +
        `<option value="unassigned">Sem vendedor atribuído</option>` +
        sellers.map((s) => `<option value="${s.id}">${s.name}</option>`).join("");
    }
  }
}

function renderKanban() {
  const selectedStore = storeFilter.value;
  const selectedStage = stageFilter.value;
  const selectedSeller = sellerFilter ? sellerFilter.value : "todos";
  
  const filtered = leads.filter((lead) => {
    const storeMatch = selectedStore === "todos" || lead.store === selectedStore;
    const stageMatch = selectedStage === "todos" || lead.stage === selectedStage;
    let sellerMatch = true;
    if (selectedSeller !== "todos") {
      if (selectedSeller === "unassigned") {
        sellerMatch = !lead.assigned_user_id;
      } else {
        sellerMatch = String(lead.assigned_user_id) === selectedSeller;
      }
    }
    return storeMatch && stageMatch && sellerMatch;
  });

  kanban.innerHTML = STAGES.map((stage) => {
    const stageLeads = filtered.filter((lead) => lead.stage === stage);
    const sum = stageLeads.reduce((acc, lead) => {
      if (lead.budget) {
         const valStr = lead.budget.replace(/[^\d.,]/g, '').replace(/\./g, '').replace(',', '.');
         const val = parseFloat(valStr);
         if (!isNaN(val)) return acc + val;
      }
      return acc;
    }, 0);
    const sumFormatted = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits:0 }).format(sum);
    return `
      <section class="kanban-column">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <h4>${stage}<span>${stageLeads.length}</span></h4>
        </div>
        <div style="font-size:13px; color:#16a34a; font-weight:700; margin-bottom:12px; background:#dcfce7; padding:4px 8px; border-radius:6px; display:inline-block;">Pipeline: ${sumFormatted}</div>
        ${stageLeads.map(renderLeadCard).join("") || '<p class="empty-note">Sem leads nesta etapa.</p>'}
      </section>
    `;
  }).join("");
}

function renderLeadCard(lead) {
  const stageIndex = STAGES.indexOf(lead.stage);
  const canAdvance = stageIndex < STAGES.length - 1;
  const nextStage = STAGES[Math.min(stageIndex + 1, STAGES.length - 1)];
  const conv = conversations.find(c => c.lead_id === lead.id);
  const displayName = lead.name || (conv ? conv.lead_name : lead.customer_phone) || 'Sem Nome';
  return `
    <article class="lead-card" style="border-left: 4px solid var(--brand); padding: 12px;">
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <strong style="font-size:13px; color:var(--text-soft); font-weight:600;">${displayName}</strong>
        ${lead.assigned_user_id ? `<span style="font-size:10px; background:#fef2f2; color:#b91c1c; padding:2px 6px; border-radius:4px; font-weight:700; white-space:nowrap; margin-left:4px;">👤 ${(teamData.find(t => t.id === lead.assigned_user_id)?.name || "Vend.").split(" ")[0]}</span>` : ""}
      </div>
      <div style="font-size:16px; font-weight:800; color:var(--text); margin-top:8px; line-height:1.2;">${lead.car || 'Veículo não informado'}</div>
      <div style="font-size:15px; font-weight:800; color:#16a34a; margin-top:4px;">${lead.budget || "—"}</div>
      <div class="lead-meta" style="margin-top:12px;">
        ${currentRole() !== "lojista" ? `<span class="pill">${lead.store}</span>` : ""}
        <span class="pill">Score ${lead.score}</span>
        <span class="pill">${lead.source || "—"}</span>
      </div>
      <div class="card-actions">
        ${canAdvance ? `<button class="mini-button" data-lead-action="advance" data-lead-id="${lead.id}" type="button">Mover para ${nextStage}</button>` : ""}
        <button class="mini-button" data-lead-action="human" data-lead-id="${lead.id}" type="button">Atendimento</button>
        ${conv ? `<a class="mini-button" href="atendimento.html?chat_id=${conv.id}" target="_blank" style="text-decoration:none; text-align:center;">Abrir Chat</a>` : ""}
      </div>
    </article>
  `;
}

function renderConversations() {
  const items = allowedConversations();
  conversationList.innerHTML = items
    .map(
      (conv) => `
    <article class="conversation-item ${conv.id === currentConversationId ? "active" : ""}" data-conversation="${conv.id}">
      <strong>${conv.lead}</strong>
      <p>${conv.intent || ""}</p>
      <span class="pill">${conv.status}</span>
    </article>
  `
    )
    .join("");

  conversationList.querySelectorAll("[data-conversation]").forEach((item) => {
    item.addEventListener("click", () => {
      currentConversationId = Number(item.dataset.conversation);
      renderConversations();
      renderChat();
    });
  });
}

async function renderChat() {
  const conv = conversations.find((c) => c.id === currentConversationId) || conversations[0];
  if (!conv) {
    messagesEl.innerHTML = '<div class="message">Nenhuma conversa disponível para este acesso.</div>';
    return;
  }
  $("#chatStore").textContent = currentRole() === "lojista" ? "Minha loja" : conv.store;
  $("#chatLead").textContent = conv.lead;
  $("#leadIntent").textContent = conv.intent || "";
  $("#replyInput").placeholder = currentRole() === "master" ? "Adicionar nota de auditoria" : "Responder como atendente humano";

  if (conv.messages === null) {
    messagesEl.innerHTML = '<div class="message">Carregando mensagens…</div>';
    try {
      const detailed = await api(`/api/conversations/${conv.id}`);
      if (detailed.conversation) {
        conv.messages = (detailed.conversation.messages || []).map((m) => ({
          type: m.sender === "agent" ? "agent" : m.sender === "human" ? "human" : "lead",
          text: m.body,
        }));
        if (detailed.conversation.details) conv.details = detailed.conversation.details;
      } else {
        conv.messages = [];
      }
    } catch (err) {
      console.error("Erro ao carregar mensagens da conversa", err);
      conv.messages = [];
    }
  }

  messagesEl.innerHTML = (conv.messages && conv.messages.length)
    ? conv.messages
        .map(
          (m) => `
    <div class="message ${m.type === "agent" ? "agent" : m.type === "human" ? "human" : ""}">
      ${escapeHtml(m.text)}
      <small>${m.type === "agent" ? "SDR IA" : m.type === "human" ? "Atendente" : conv.lead}</small>
    </div>
  `
        )
        .join("")
    : '<div class="message">Nenhuma mensagem registrada nesta conversa.</div>';

  leadDetails.innerHTML = Object.entries(conv.details || {})
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");

  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderVehicles(list = vehicles) {
  const role = currentRole();
  const heading = $("#vehicles .board-toolbar h3");
  heading.textContent =
    role === "lojista" ? "Meus veículos publicados" : role === "master" ? "Inventário global conectado" : "Cadastro central de veículos";
  $("#newVehicleButton").textContent = role === "lojista" ? "Cadastrar meu veículo" : "Cadastrar veículo";

  vehicleGrid.innerHTML = list.length
    ? list
        .map(
          (v) => `
    <article class="vehicle-card">
      <img src="${v.img || "assets/car-city.jpg"}" alt="${escapeHtml(v.name)}" />
      <div class="vehicle-body">
        <div>
          <strong>${escapeHtml(v.name)}</strong>
          <p>${role === "lojista" ? v.status : v.store}</p>
        </div>
        <span class="vehicle-price">${v.price}</span>
        <div class="vehicle-meta">
          ${v.meta.map((item) => `<span class="pill">${item}</span>`).join("")}
          <span class="pill">${v.status}</span>
        </div>
        <div class="card-actions">
          <button class="mini-button" data-vehicle-action="toggle" data-vehicle-id="${v.id}" type="button">${v.status === "Publicado" ? "Pausar" : "Publicar"}</button>
          <button class="mini-button" data-vehicle-action="edit" data-vehicle-id="${v.id}" type="button">Editar</button>
          <button class="mini-button danger" data-vehicle-action="delete" data-vehicle-id="${v.id}" type="button">Excluir</button>
        </div>
      </div>
    </article>
  `
        )
        .join("")
    : '<article class="panel empty-panel"><h3>Nenhum veículo encontrado</h3><p>Refine sua busca por modelo, loja ou característica.</p></article>';
}

function renderStores() {
  const role = currentRole();
  const title = $("#stores .board-toolbar h3");
  const button = $("#stores .board-toolbar .primary-button");
  const rows = role === "master" ? stores : stores.filter((s) => s.type === "Lojista");

  title.textContent = role === "master" ? "Tenants, planos e consumo" : "Rede de lojas e agentes vinculados";
  button.textContent = role === "master" ? "Novo tenant" : "Convidar lojista";

  // contagem viva a partir de leads/vehicles
  const leadsByStore = countBy(leads, "store_id");
  const vehiclesByStore = countBy(vehicles, "store_id");

  storeTable.innerHTML = `
    <div class="store-row store-head">
      <span>${role === "master" ? "Tenant" : "Lojista"}</span>
      <span>Plano</span>
      <span>Leads</span>
      <span>Veículos</span>
      <span>Resposta</span>
      <span>Status</span>
      <span>Ações</span>
    </div>
    ${rows
      .map(
        (s) => `
      <div class="store-row">
        <strong>${s.name}</strong>
        <span>${s.plan}</span>
        <span>${leadsByStore[s.id] || 0}</span>
        <span>${vehiclesByStore[s.id] || 0}</span>
        <span>${s.response}</span>
        <span class="store-status ${s.status === "Atenção" ? "warn" : ""}">${s.status}</span>
        <span class="row-actions">
          <button class="mini-button" data-store-action="toggle" data-store-id="${s.id}" type="button">${s.status === "Ativo" ? "Pausar" : "Ativar"}</button>
          <button class="mini-button danger" data-store-action="delete" data-store-id="${s.id}" type="button">Excluir</button>
        </span>
      </div>
    `
      )
      .join("")}
  `;
}

function renderTeam() {
  const table = document.getElementById("teamTable");
  if (!table) return;

  // Atualiza os mini-cards do topo
  const totalLeadsEl = document.getElementById("teamTotalLeads");
  const activeLeadsEl = document.getElementById("teamActiveLeads");
  const closedLeadsEl = document.getElementById("teamClosedLeads");
  
  if (totalLeadsEl && activeLeadsEl && closedLeadsEl) {
    let sumTotal = 0, sumActive = 0, sumClosed = 0;
    teamData.forEach(v => {
      sumTotal += v.total_leads || 0;
      sumActive += v.ativos || 0;
      sumClosed += v.fechados || 0;
    });
    totalLeadsEl.textContent = sumTotal;
    activeLeadsEl.textContent = sumActive;
    closedLeadsEl.textContent = sumClosed;
  }

  if (teamData.length === 0) {
    table.innerHTML = '<article class="panel empty-panel"><h3>Nenhuma equipe encontrada</h3><p>Clique em "Adicionar Vendedor" para cadastrar o primeiro membro.</p></article>';
    return;
  }

  table.innerHTML = `
    <div class="store-row store-head" style="grid-template-columns: 2fr 1.5fr 1fr 1fr 1fr 1fr !important">
      <span>Vendedor</span>
      <span>E-mail</span>
      <span>Ativos</span>
      <span>Fechados</span>
      <span>Conversão</span>
      <span>Ações</span>
    </div>
    ${teamData
      .map(
        (v) => {
          const total = v.total_leads || 0;
          const convRate = total > 0 ? Math.round((v.fechados / total) * 100) : 0;
          return `
      <div class="store-row" style="grid-template-columns: 2fr 1.5fr 1fr 1fr 1fr 1fr !important">
        <strong><span style="color:#22c55e; margin-right:4px; font-size:10px;">●</span>${v.name}</strong>
        <span style="color:var(--text-soft); font-size:13px">${v.email}</span>
        <span style="color:#b45309; font-weight:600">${v.ativos || 0}</span>
        <span style="color:#16a34a; font-weight:700">${v.fechados || 0}</span>
        <div style="display:flex; flex-direction:column; gap:4px; justify-content:center; padding-right: 16px;">
          <div style="font-size:12px; font-weight:600; color:var(--text);">${convRate}%</div>
          <div style="height:6px; width:100%; background:#e5e7eb; border-radius:3px; overflow:hidden;">
            <div style="height:100%; width:${convRate}%; background:var(--accent); border-radius:3px;"></div>
          </div>
        </div>
        <span class="row-actions">
          <button class="mini-button danger" data-seller-action="delete" data-seller-id="${v.id}" type="button">Remover</button>
        </span>
      </div>
    `})
      .join("")}
  `;

  table.querySelectorAll('[data-seller-action="delete"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sid = Number(btn.dataset.sellerId);
      const storeId = currentUser?.store_id;
      if (!storeId) return;
      if (!confirm("Remover este vendedor?")) return;
      try {
        await api(`/api/stores/${storeId}/sellers/${sid}`, { method: "DELETE" });
        const r = await api("/api/dashboard/team");
        teamData = r.team || [];
        renderTeam();
        showToast("Vendedor removido");
      } catch (err) { showToast(err.message); }
    });
  });
}

function openSellerModal() {
  const storeId = currentUser?.store_id;
  if (!storeId) { showToast("Sem loja vinculada ao seu usuário"); return; }
  const fields = [
    { label: "Nome do vendedor", name: "name", placeholder: "Ex: Carlos Silva", required: true },
    { label: "E-mail", name: "email", type: "email", placeholder: "carlos@loja.com", required: true },
    { label: "Senha inicial (mín. 6 caracteres)", name: "password", type: "password", placeholder: "••••••", required: true },
  ];
  openModal("Adicionar Vendedor", fields, "Criar Vendedor", async (data) => {
    const r = await api(`/api/stores/${storeId}/sellers`, {
      method: "POST",
      body: JSON.stringify(data),
    });
    const teamR = await api("/api/dashboard/team");
    teamData = teamR.team || [];
    renderTeam();
    showToast(`Vendedor ${r.seller.name} criado com sucesso!`);
  });
}

function renderCosts() {
  const role = currentRole();
  const costTitle = $("#billing .panel h3");
  const qrTitle = $(".qr-panel h3");
  const qrText = $(".qr-panel p");
  const qrButton = $(".qr-panel .primary-button");

  if (role === "master") {
    costTitle.textContent = "WhatsApp, IA e margem por tenant";
    qrTitle.textContent = "Provisionar conexão";
    qrText.textContent = "Gere conexão para novos tenants, acompanhe sessões ativas e controle custo de conversa por cliente.";
    qrButton.textContent = "Criar tenant";
  } else if (role === "shopping") {
    costTitle.textContent = "Uso do shopping e repasses";
    qrTitle.textContent = "Vincular WhatsApp de lojista";
    qrText.textContent = "O gestor pode convidar lojistas, gerar QR Code e liberar o agente para operar dentro da estrutura central.";
    qrButton.textContent = "Gerar QR de lojista";
  } else {
    costTitle.textContent = "Meu WhatsApp e meu plano";
    qrTitle.textContent = "Conectar meu WhatsApp";
    qrText.textContent = "Escaneie o QR Code para ativar o vendedor virtual da sua loja e receber leads qualificados no seu número.";
    qrButton.textContent = "Gerar meu QR";
  }

  const items =
    role === "master"
      ? [
          ["Receita recorrente", stores.reduce((s, x) => s + x.revenue, 0), "Mensalidade e add-ons"],
          ["Conversas WhatsApp", stores.reduce((s, x) => s + x.cost, 0), "Templates, sessões e handoff"],
          ["IA SDR", 2170, "Qualificação, resumo e roteamento"],
          ["Margem operacional", stores.reduce((s, x) => s + x.revenue - x.cost, 0), "Receita menos custos diretos"],
        ]
      : role === "shopping"
      ? [
          ["Conversas do shopping", stores.filter((s) => s.type === "Lojista").reduce((sum, x) => sum + x.cost, 0), "Custo agregado dos lojistas"],
          ["Leads enviados", leads.length, "Leads qualificados no mês"],
          ["Lojistas com agente", stores.filter((s) => s.type === "Lojista" && s.status === "Ativo").length, "WhatsApps conectados"],
          ["Custo por lead", Math.max(1, Math.round(stores.reduce((s, x) => s + x.cost, 0) / Math.max(leads.length, 1))), "WhatsApp + IA por oportunidade"],
        ]
      : [
          ["Meu plano", stores.find((s) => s.id === currentUser?.store_id)?.revenue || 1290, "Mensalidade do agente"],
          ["Conversas usadas", stores.find((s) => s.id === currentUser?.store_id)?.cost || 0, "Consumo estimado do mês"],
          ["Leads recebidos", leads.length, "Oportunidades qualificadas"],
          ["Custo por lead", 12, "Estimativa operacional"],
        ];

  costList.innerHTML = items
    .map(
      ([label, value, description]) => `
    <div class="cost-item">
      <div>
        <strong>${label}</strong>
        <span>${description}</span>
      </div>
      <div class="cost-value">${
        label.includes("Leads") || label.includes("Lojistas") || label.includes("Conversas usadas")
          ? value
          : formatMoney(value)
      }</div>
    </div>
  `
    )
    .join("");
}

// ---------- Modais ----------
function openModal(title, fields, submitLabel, onSubmit) {
  modalLayer.innerHTML = `
    <div class="modal-backdrop" data-modal-close="true"></div>
    <section class="modal-card" role="dialog" aria-modal="true" aria-label="${title}">
      <div class="modal-header">
        <div>
          <span class="eyebrow">Formula OS</span>
          <h3>${title}</h3>
        </div>
        <button class="icon-close" data-modal-close="true" type="button" aria-label="Fechar">×</button>
      </div>
      <form class="modal-form" id="modalForm">
        ${fields.map(renderField).join("")}
        <div class="modal-actions">
          <button class="ghost-button" data-modal-close="true" type="button">Cancelar</button>
          <button class="primary-button" type="submit">${submitLabel}</button>
        </div>
      </form>
    </section>
  `;
  modalLayer.classList.add("show");
  modalLayer.setAttribute("aria-hidden", "false");

  modalLayer.querySelector("#modalForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      await onSubmit(data);
      closeModal();
    } catch (err) {
      showToast(err.message || "Falha ao salvar");
    }
  });
}

function renderField(field) {
  const value = field.value ?? "";
  if (field.type === "select") {
    return `
      <label class="form-field">
        <span>${field.label}</span>
        <select name="${field.name}" ${field.required ? "required" : ""}>
          ${field.options.map((o) => `<option value="${o}" ${String(o) === String(value) ? "selected" : ""}>${o}</option>`).join("")}
        </select>
      </label>
    `;
  }
  if (field.type === "textarea") {
    return `
      <label class="form-field">
        <span>${field.label}</span>
        <textarea name="${field.name}" placeholder="${field.placeholder || ""}" ${field.required ? "required" : ""} rows="4">${escapeAttr(value)}</textarea>
      </label>
    `;
  }
  return `
    <label class="form-field">
      <span>${field.label}</span>
      <input name="${field.name}" type="${field.type || "text"}" value="${escapeAttr(value)}" placeholder="${field.placeholder || ""}" ${field.required ? "required" : ""} />
    </label>
  `;
}

function closeModal() {
  modalLayer.classList.remove("show");
  modalLayer.setAttribute("aria-hidden", "true");
  modalLayer.innerHTML = "";
}

function openVehicleModal(vehicle = null) {
  const role = currentRole();
  const lojistaStores = stores.filter((s) => s.type === "Lojista" || s.name);

  // Estado da galeria e fotos
  let picturesList = [];
  if (vehicle?.pictures && Array.isArray(vehicle.pictures) && vehicle.pictures.length > 0) {
    picturesList = vehicle.pictures.map((p) => ({
      remote_image_url: typeof p === "string" ? p : p.remote_image_url || p.url,
      is_uploading: false,
    }));
  } else if (vehicle?.image_path) {
    picturesList = [{ remote_image_url: vehicle.image_path, is_uploading: false }];
  }

  let coverUrl = vehicle?.main_image || vehicle?.image_path || (picturesList[0]?.remote_image_url || "");

  // Estado dos opcionais
  const DEFAULT_OPTIONS = [
    "Ar-condicionado", "Direção elétrica", "Vidros elétricos", "Travas elétricas",
    "Alarme", "Freios ABS", "Airbags frontais", "Airbags laterais",
    "Bancos de couro", "Central multimídia", "Apple CarPlay / Android Auto",
    "Câmera de ré", "Sensor de estacionamento", "Teto solar", "Rodas de liga leve",
    "Piloto automático", "Faróis em LED", "Computador de bordo",
    "Chave presencial / Start-Stop", "Controle de estabilidade", "Volante multifuncional"
  ];
  const selectedItems = new Set(Array.isArray(vehicle?.item_list) ? vehicle.item_list : []);

  const modalTitle = vehicle
    ? `Editar veículo: ${escapeHtml(vehicle.name)}`
    : role === "lojista"
    ? "Cadastrar meu veículo"
    : "Cadastro central de veículos";

  const submitLabel = vehicle ? "Salvar alterações" : "Publicar veículo";

  // Renderiza a casca do modal
  modalLayer.innerHTML = `
    <div class="modal-backdrop" data-modal-close="true"></div>
    <section class="modal-card modal-large" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
      <header class="modal-header">
        <h3 id="modalTitle">${modalTitle}</h3>
        <button class="icon-close" data-modal-close="true" type="button" aria-label="Fechar modal">×</button>
      </header>

      <form id="vehicleExpandedForm" class="vehicle-form-container">
        <!-- 1. Galeria de Fotos & CDN -->
        <section class="vehicle-section">
          <div class="vehicle-section-header">
            <span class="vehicle-section-title"><span class="section-icon">📷</span> Galeria de Fotos (Cloudflare R2)</span>
            <small style="color: var(--muted); font-size: 11px;">8 resoluções automáticas • Max 15MB por foto</small>
          </div>

          <div class="photo-dropzone" id="photoDropzone">
            <span class="dropzone-icon">☁️</span>
            <strong>Arraste fotos do veículo aqui ou clique para selecionar</strong>
            <span>Formatos suportados: JPEG, PNG e WEBP (otimização instantânea)</span>
            <input type="file" id="vehiclePhotoInput" multiple accept="image/jpeg,image/png,image/webp" style="display: none;" />
          </div>

          <div class="photo-gallery-grid" id="photoGalleryGrid"></div>
        </section>

        <!-- 2. Classificação Veicular -->
        <section class="vehicle-section">
          <span class="vehicle-section-title"><span class="section-icon">🚗</span> Classificação e Identificação</span>
          <div class="vehicle-form-grid grid-cols-3">
            <label class="form-field">
              <span>Marca *</span>
              <input name="brand" id="vehBrand" type="text" value="${escapeAttr(vehicle?.brand || "")}" placeholder="Ex: Toyota, Honda, Jeep" required />
            </label>
            <label class="form-field">
              <span>Modelo *</span>
              <input name="model" id="vehModel" type="text" value="${escapeAttr(vehicle?.model || "")}" placeholder="Ex: Corolla, Civic, Compass" required />
            </label>
            <label class="form-field">
              <span>Versão</span>
              <input name="version" id="vehVersion" type="text" value="${escapeAttr(vehicle?.version || "")}" placeholder="Ex: XEi 2.0 Direct Shift, Longitude" />
            </label>
          </div>

          <div class="vehicle-form-grid grid-cols-4">
            <label class="form-field">
              <span>Categoria</span>
              <select name="category" id="vehCategory">
                ${["Sedan", "Hatch", "SUV", "Picape", "Cupê", "Minivan", "Perua", "Utilitário", "Moto"].map(c => `
                  <option value="${c}" ${vehicle?.category === c ? "selected" : ""}>${c}</option>
                `).join("")}
              </select>
            </label>
            <label class="form-field">
              <span>Portas</span>
              <select name="doors">
                <option value="4" ${vehicle?.doors === 4 ? "selected" : ""}>4 portas</option>
                <option value="2" ${vehicle?.doors === 2 ? "selected" : ""}>2 portas</option>
                <option value="3" ${vehicle?.doors === 3 ? "selected" : ""}>3 portas</option>
                <option value="5" ${vehicle?.doors === 5 ? "selected" : ""}>5 portas</option>
              </select>
            </label>
            <label class="form-field">
              <span>Cor</span>
              <input name="color" type="text" value="${escapeAttr(vehicle?.color || "")}" placeholder="Ex: Branco Pérola, Preto" />
            </label>
            <label class="form-field">
              <span>Placa (Interno)</span>
              <input name="plate" type="text" value="${escapeAttr(vehicle?.plate || "")}" placeholder="Ex: BRA2E19" maxlength="8" style="text-transform: uppercase;" />
            </label>
          </div>

          <div class="vehicle-form-grid grid-cols-3">
            <label class="form-field" style="grid-column: span 2;">
              <span>Título Comercial (Vitrine) *</span>
              <input name="name" id="vehName" type="text" value="${escapeAttr(vehicle?.name || "")}" placeholder="Ex: Toyota Corolla XEi 2.0 2023" required />
            </label>
            <label class="form-field">
              <span>Código de Estoque / Unidade</span>
              <input name="unit_id" type="text" value="${escapeAttr(vehicle?.unit_id || "")}" placeholder="Ex: EST-1092" />
            </label>
          </div>
        </section>

        <!-- 3. Ano, KM, Mecânica e Valores -->
        <section class="vehicle-section">
          <span class="vehicle-section-title"><span class="section-icon">⚙️</span> Mecânica, Rodagem e Valores</span>
          <div class="vehicle-form-grid grid-cols-4">
            <label class="form-field">
              <span>Ano Fabricação</span>
              <input name="fabrication_year" id="vehFabYear" type="number" min="1950" max="2035" value="${escapeAttr(vehicle?.fabrication_year || "")}" placeholder="Ex: 2022" />
            </label>
            <label class="form-field">
              <span>Ano Modelo</span>
              <input name="model_year" id="vehModYear" type="number" min="1950" max="2035" value="${escapeAttr(vehicle?.model_year || "")}" placeholder="Ex: 2023" />
            </label>
            <label class="form-field">
              <span>Quilometragem (KM)</span>
              <input name="km" id="vehKm" type="text" value="${escapeAttr(vehicle?.km ?? (vehicle?.mileage ? vehicle.mileage.replace(/\D/g, '') : ''))}" placeholder="Ex: 48000" />
            </label>
            <label class="form-field">
              <span>Preço de Venda (R$) *</span>
              <input name="price" id="vehPrice" type="text" value="${escapeAttr(vehicle?.price || "")}" placeholder="Ex: 119900 ou R$ 119.900" required />
            </label>
          </div>

          <div class="vehicle-form-grid grid-cols-3">
            <label class="form-field">
              <span>Câmbio</span>
              <select name="transmission">
                ${["Automático", "Manual", "CVT", "Automatizado"].map(t => `
                  <option value="${t}" ${vehicle?.transmission === t || vehicle?.exchange === t ? "selected" : ""}>${t}</option>
                `).join("")}
              </select>
            </label>
            <label class="form-field">
              <span>Combustível</span>
              <select name="fuel">
                ${["Flex", "Gasolina", "Diesel", "Elétrico", "Híbrido", "GNV"].map(f => `
                  <option value="${f}" ${vehicle?.fuel === f || vehicle?.fuel_text === f ? "selected" : ""}>${f}</option>
                `).join("")}
              </select>
            </label>
            <label class="form-field">
              <span>Status</span>
              <select name="status">
                ${["Publicado", "Pausado", "Vendido", "Rascunho"].map(s => `
                  <option value="${s}" ${(vehicle?.status || "Publicado") === s ? "selected" : ""}>${s}</option>
                `).join("")}
              </select>
            </label>
          </div>

          ${role !== "lojista" ? `
            <div class="vehicle-form-grid grid-cols-2">
              <label class="form-field grid-col-full">
                <span>Lojista Proprietário do Veículo *</span>
                <select name="store_id" required>
                  ${lojistaStores.map(s => `
                    <option value="${s.id}" ${vehicle?.store_id === s.id ? "selected" : ""}>${escapeHtml(s.name)}</option>
                  `).join("")}
                </select>
              </label>
            </div>
          ` : ""}
        </section>

        <!-- 4. Badges Comerciais (Toggles) -->
        <section class="vehicle-section">
          <span class="vehicle-section-title"><span class="section-icon">🏷️</span> Destaques e Badges Comerciais</span>
          <div class="toggles-grid">
            <label class="toggle-card">
              <input type="checkbox" name="featured" ${vehicle?.featured ? "checked" : ""} />
              <span>★ Destaque na Vitrine</span>
            </label>
            <label class="toggle-card">
              <input type="checkbox" name="new_vehicle" ${vehicle?.new_vehicle ? "checked" : ""} />
              <span>0 km (Novo)</span>
            </label>
            <label class="toggle-card">
              <input type="checkbox" name="shielded" ${vehicle?.shielded ? "checked" : ""} />
              <span>🛡️ Blindado</span>
            </label>
            <label class="toggle-card">
              <input type="checkbox" name="in_transit" ${vehicle?.in_transit ? "checked" : ""} />
              <span>🚚 Em Trânsito</span>
            </label>
            <label class="toggle-card">
              <input type="checkbox" name="sold" ${vehicle?.sold ? "checked" : ""} />
              <span>Vendido</span>
            </label>
            <label class="toggle-card">
              <input type="checkbox" name="active" ${(vehicle?.active ?? true) ? "checked" : ""} />
              <span>Ativo no Estoque</span>
            </label>
          </div>
        </section>

        <!-- 5. Opcionais e Acessórios -->
        <section class="vehicle-section">
          <span class="vehicle-section-title"><span class="section-icon">✨</span> Opcionais e Itens de Série</span>
          <div class="chip-container">
            <div class="chip-grid" id="chipGrid"></div>
            <div class="chip-custom-input">
              <input type="text" id="customChipInput" placeholder="Adicionar outro opcional (ex: Som Harman Kardon) e pressione Enter..." />
              <button type="button" class="mini-button" id="addCustomChipBtn">+ Adicionar</button>
            </div>
          </div>
        </section>

        <!-- 6. Observações Comerciais -->
        <section class="vehicle-section">
          <span class="vehicle-section-title"><span class="section-icon">📝</span> Observações e Histórico</span>
          <label class="form-field">
            <textarea name="note" placeholder="Descreva revisões, garantias, estado de pneus, laudo cautelar e diferenciais deste veículo..." rows="3">${escapeAttr(vehicle?.note || "")}</textarea>
          </label>
        </section>

        <!-- Ações do Modal -->
        <div class="modal-actions" style="margin-top: 10px; display: flex; justify-content: flex-end; gap: 10px;">
          <button class="ghost-button" data-modal-close="true" type="button">Cancelar</button>
          <button class="primary-button" id="saveVehicleBtn" type="submit">${submitLabel}</button>
        </div>
      </form>
    </section>
  `;

  modalLayer.classList.add("show");
  modalLayer.setAttribute("aria-hidden", "false");

  // DOM Refs dentro do modal
  const form = modalLayer.querySelector("#vehicleExpandedForm");
  const dropzone = modalLayer.querySelector("#photoDropzone");
  const fileInput = modalLayer.querySelector("#vehiclePhotoInput");
  const galleryGrid = modalLayer.querySelector("#photoGalleryGrid");
  const chipGrid = modalLayer.querySelector("#chipGrid");
  const customChipInput = modalLayer.querySelector("#customChipInput");
  const addCustomChipBtn = modalLayer.querySelector("#addCustomChipBtn");

  const brandInput = modalLayer.querySelector("#vehBrand");
  const modelInput = modalLayer.querySelector("#vehModel");
  const versionInput = modalLayer.querySelector("#vehVersion");
  const modYearInput = modalLayer.querySelector("#vehModYear");
  const nameInput = modalLayer.querySelector("#vehName");

  // Auto-sugestão de título
  let userEditedTitle = Boolean(vehicle?.name);
  nameInput.addEventListener("input", () => {
    userEditedTitle = true;
  });

  function updateSuggestedTitle() {
    if (userEditedTitle) return;
    const parts = [
      brandInput.value.trim(),
      modelInput.value.trim(),
      versionInput.value.trim(),
      modYearInput.value.trim(),
    ].filter(Boolean);
    if (parts.length > 0) {
      nameInput.value = parts.join(" ");
    }
  }

  brandInput.addEventListener("input", updateSuggestedTitle);
  modelInput.addEventListener("input", updateSuggestedTitle);
  versionInput.addEventListener("input", updateSuggestedTitle);
  modYearInput.addEventListener("input", updateSuggestedTitle);

  // Renderizador da Galeria de Fotos
  function renderGallery() {
    if (picturesList.length === 0) {
      galleryGrid.innerHTML = `<p style="grid-column: 1 / -1; color: var(--muted); font-size: 13px; text-align: center; padding: 8px 0;">Nenhuma foto cadastrada ainda.</p>`;
      return;
    }

    galleryGrid.innerHTML = picturesList.map((pic, idx) => {
      const isCover = (pic.remote_image_url === coverUrl) || (!coverUrl && idx === 0);
      if (isCover && !coverUrl) coverUrl = pic.remote_image_url;

      return `
        <div class="photo-gallery-item ${isCover ? 'is-cover' : ''}" data-index="${idx}">
          <img src="${pic.remote_image_url}" alt="Foto ${idx + 1}" />
          ${isCover ? `<span class="photo-cover-badge">★ Capa</span>` : ""}
          ${pic.is_uploading ? `
            <div class="photo-uploading-overlay">
              <div class="upload-spinner"></div>
              <span>Enviando...</span>
            </div>
          ` : `
            <div class="photo-actions">
              <div style="display: flex; gap: 3px;">
                ${idx > 0 ? `<button type="button" class="photo-action-btn move-left" title="Mover para a esquerda" data-idx="${idx}">◀</button>` : ""}
                ${idx < picturesList.length - 1 ? `<button type="button" class="photo-action-btn move-right" title="Mover para a direita" data-idx="${idx}">▶</button>` : ""}
              </div>
              <div style="display: flex; gap: 3px;">
                ${!isCover ? `<button type="button" class="photo-action-btn set-cover" title="Definir como foto de capa" data-idx="${idx}">Capa</button>` : ""}
                <button type="button" class="photo-action-btn delete" title="Remover foto" data-idx="${idx}">×</button>
              </div>
            </div>
          `}
        </div>
      `;
    }).join("");

    // Eventos dos botões da galeria
    galleryGrid.querySelectorAll(".set-cover").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.idx);
        if (picturesList[idx]) {
          coverUrl = picturesList[idx].remote_image_url;
          renderGallery();
        }
      });
    });

    galleryGrid.querySelectorAll(".move-left").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.idx);
        if (idx > 0) {
          const item = picturesList.splice(idx, 1)[0];
          picturesList.splice(idx - 1, 0, item);
          renderGallery();
        }
      });
    });

    galleryGrid.querySelectorAll(".move-right").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.idx);
        if (idx < picturesList.length - 1) {
          const item = picturesList.splice(idx, 1)[0];
          picturesList.splice(idx + 1, 0, item);
          renderGallery();
        }
      });
    });

    galleryGrid.querySelectorAll(".delete").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.dataset.idx);
        const removed = picturesList.splice(idx, 1)[0];
        if (removed && removed.remote_image_url === coverUrl) {
          coverUrl = picturesList[0]?.remote_image_url || "";
        }
        renderGallery();
      });
    });
  }

  // Upload handler via FormData
  async function handleFilesUpload(files) {
    const validFiles = [];
    for (const f of files) {
      if (!f.type.startsWith("image/")) {
        showToast(`Arquivo ignorado (não é imagem): ${f.name}`);
        continue;
      }
      if (f.size > 15 * 1024 * 1024) {
        showToast(`Imagem excede 15MB: ${f.name}`);
        continue;
      }
      validFiles.push(f);
    }
    if (validFiles.length === 0) return;

    // Adiciona previews temporários na galeria
    const tempEntries = validFiles.map(f => {
      const tempUrl = URL.createObjectURL(f);
      const entry = { remote_image_url: tempUrl, is_uploading: true, file: f };
      picturesList.push(entry);
      return entry;
    });
    renderGallery();

    const formData = new FormData();
    for (const f of validFiles) {
      formData.append("files", f);
    }

    try {
      const res = await api("/api/vehicles/upload-photos", {
        method: "POST",
        body: formData,
      });

      const uploaded = res.photos || res.uploaded || [];
      if (uploaded.length > 0) {
        // Substitui os itens temporários pelas URLs permanentes da CDN
        tempEntries.forEach((entry, i) => {
          if (uploaded[i]) {
            entry.remote_image_url = uploaded[i].remote_image_url;
            entry.is_uploading = false;
          }
        });
        if (!coverUrl && picturesList[0]) {
          coverUrl = picturesList[0].remote_image_url;
        }
        showToast(`${uploaded.length} foto(s) enviada(s) para a CDN!`);
      }
    } catch (err) {
      // Remove entradas temporárias com erro
      tempEntries.forEach(entry => {
        const idx = picturesList.indexOf(entry);
        if (idx !== -1) picturesList.splice(idx, 1);
      });
      showToast(`Falha no upload de fotos: ${err.message}`);
    } finally {
      renderGallery();
    }
  }

  dropzone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleFilesUpload([...fileInput.files]);
      fileInput.value = "";
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer?.files?.length) {
      handleFilesUpload([...e.dataTransfer.files]);
    }
  });

  renderGallery();

  // Renderizador de Chips de Opcionais
  function renderChips() {
    const allChips = Array.from(new Set([...DEFAULT_OPTIONS, ...selectedItems]));
    chipGrid.innerHTML = allChips.map(item => {
      const active = selectedItems.has(item);
      return `
        <button type="button" class="chip ${active ? 'active' : ''}" data-chip="${escapeAttr(item)}">
          ${active ? "✓ " : "+ "}${escapeHtml(item)}
        </button>
      `;
    }).join("");

    chipGrid.querySelectorAll(".chip").forEach(btn => {
      btn.addEventListener("click", () => {
        const item = btn.dataset.chip;
        if (selectedItems.has(item)) {
          selectedItems.delete(item);
        } else {
          selectedItems.add(item);
        }
        renderChips();
      });
    });
  }

  function addCustomChip() {
    const val = customChipInput.value.trim();
    if (val) {
      selectedItems.add(val);
      customChipInput.value = "";
      renderChips();
    }
  }

  addCustomChipBtn.addEventListener("click", addCustomChip);
  customChipInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCustomChip();
    }
  });

  renderChips();

  // Submit Handler
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const stillUploading = picturesList.some(p => p.is_uploading);
    if (stillUploading) {
      showToast("Aguarde a finalização do upload das fotos antes de salvar.");
      return;
    }

    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    const activePics = picturesList.filter(p => !p.is_uploading && p.remote_image_url);
    const finalCover = coverUrl || (activePics[0]?.remote_image_url || "");

    const payload = {
      name: (data.name || "").trim(),
      brand: (data.brand || "").trim(),
      model: (data.model || "").trim(),
      version: (data.version || "").trim(),
      category: data.category || "Sedan",
      doors: data.doors ? Number(data.doors) : 4,
      color: (data.color || "").trim(),
      plate: (data.plate || "").trim().toUpperCase(),
      unit_id: (data.unit_id || "").trim(),
      fabrication_year: data.fabrication_year ? Number(data.fabrication_year) : null,
      model_year: data.model_year ? Number(data.model_year) : null,
      km: data.km ? Number(String(data.km).replace(/\D/g, "")) : null,
      price: (data.price || "").trim(),
      transmission: data.transmission || "Automático",
      exchange: data.transmission || "Automático",
      fuel: data.fuel || "Flex",
      fuel_text: data.fuel || "Flex",
      status: data.status || "Publicado",
      featured: form.querySelector("[name='featured']").checked,
      new_vehicle: form.querySelector("[name='new_vehicle']").checked,
      shielded: form.querySelector("[name='shielded']").checked,
      in_transit: form.querySelector("[name='in_transit']").checked,
      sold: form.querySelector("[name='sold']").checked,
      active: form.querySelector("[name='active']").checked,
      item_list: Array.from(selectedItems),
      note: (data.note || "").trim(),
      pictures: activePics.map(p => ({ remote_image_url: p.remote_image_url })),
      image_path: finalCover || "assets/car-city.jpg",
      main_image: finalCover || "assets/car-city.jpg",
    };

    if (role !== "lojista") {
      payload.store_id = Number(data.store_id);
    }

    try {
      if (vehicle) {
        await api(`/api/vehicles/${vehicle.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        showToast("Veículo atualizado com sucesso!");
      } else {
        await api("/api/vehicles", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showToast("Veículo publicado no estoque com sucesso!");
      }
      closeModal();
      await refreshAndRender();
      showView("vehicles");
    } catch (err) {
      showToast(err.message || "Erro ao salvar veículo");
    }
  });
}

function openStoreModal(store = null) {
  const isMaster = currentRole() === "master";
  const fields = [
    { label: isMaster ? "Nome do tenant" : "Nome da loja", name: "name", value: store?.name, placeholder: "Ex: Prime Motors", required: true },
    { label: "Plano", name: "plan", value: store?.plan || "Pro", type: "select", options: ["Start", "Pro", "Enterprise"], required: true },
    { label: "Status", name: "status", value: store?.status || "Ativo", type: "select", options: ["Ativo", "Atenção", "Pausado"], required: true },
    { label: "Instruções do SDR (Prompt IA)", name: "sdr_prompt", value: store?.sdr_prompt, type: "textarea", placeholder: "Regras específicas de atendimento e tom de voz" },
  ];
  openModal(store ? "Editar lojista" : isMaster ? "Adicionar tenant" : "Adicionar lojista", fields, store ? "Salvar" : "Adicionar", async (data) => {
    if (store) {
      await api(`/api/stores/${store.id}`, { method: "PATCH", body: JSON.stringify(data) });
      showToast("Cadastro atualizado");
    } else {
      const monthlyRevenue = data.plan === "Enterprise" ? 18400 : data.plan === "Pro" ? 1290 : 890;
      await api("/api/stores", {
        method: "POST",
        body: JSON.stringify({ ...data, type: "Lojista", monthly_revenue: monthlyRevenue }),
      });
      showToast(isMaster ? "Tenant adicionado" : "Lojista convidado");
    }
    await refreshAndRender();
    showView("stores");
  });
}

// ---------- Ações ----------
async function advanceLead(leadId) {
  try {
    const r = await api(`/api/leads/${leadId}/advance`, { method: "POST" });
    await refreshAndRender();
    showToast(`${r.lead.name} movido para ${r.lead.stage}`);
  } catch (err) {
    showToast(err.message);
  }
}
async function moveLeadToHuman(leadId) {
  try {
    await api(`/api/leads/${leadId}`, { method: "PATCH", body: JSON.stringify({ stage: "Humano" }) });
    await refreshAndRender();
    showView("inbox");
    showToast("Lead movido para atendimento humano");
  } catch (err) {
    showToast(err.message);
  }
}
async function toggleVehicle(vehicleId) {
  const v = vehicles.find((x) => x.id === vehicleId);
  if (!v) return;
  const next = v.status === "Publicado" ? "Pausado" : "Publicado";
  try {
    await api(`/api/vehicles/${vehicleId}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
    await refreshAndRender();
    showToast(`${v.name} ${next.toLowerCase()}`);
  } catch (err) {
    showToast(err.message);
  }
}
async function deleteVehicle(vehicleId) {
  try {
    await api(`/api/vehicles/${vehicleId}`, { method: "DELETE" });
    await refreshAndRender();
    showToast("Veículo excluído");
  } catch (err) {
    showToast(err.message);
  }
}
async function toggleStore(storeId) {
  const s = stores.find((x) => x.id === storeId);
  if (!s) return;
  const next = s.status === "Ativo" ? "Pausado" : "Ativo";
  try {
    await api(`/api/stores/${storeId}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
    await refreshAndRender();
    showToast(`${s.name} ${next.toLowerCase()}`);
  } catch (err) {
    showToast(err.message);
  }
}
async function deleteStore(storeId) {
  const s = stores.find((x) => x.id === storeId);
  if (!s) return;
  if (s.type === "Auto Shopping") { showToast("O cadastro do shopping não pode ser excluído"); return; }
  try {
    await api(`/api/stores/${storeId}`, { method: "DELETE" });
    await refreshAndRender();
    showToast(`${s.name} excluído`);
  } catch (err) {
    showToast(err.message);
  }
}

async function sendReply(text) {
  if (!currentConversationId) return;
  const r = await api(`/api/conversations/${currentConversationId}/send`, {
    method: "POST",
    body: JSON.stringify({ body: text }),
  });
  await refreshAndRender();
  if (r.delivery === "sent") {
    showToast("Mensagem enviada via WhatsApp ✓");
  } else if (r.delivery === "send_failed") {
    showToast("❌ Falha WhatsApp: " + (r.error_details || "Erro desconhecido"));
  } else {
    showToast("Mensagem salva (sem provider WhatsApp)");
  }
}

async function updateConversationStatus(status) {
  if (!currentConversationId) return;
  await api(`/api/conversations/${currentConversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  await refreshAndRender();
  showToast(status === "Encerrado" ? "Atendimento encerrado" : "Conversa assumida");
}

async function createLeadFromConversation() {
  const conv = conversations.find((c) => c.id === currentConversationId);
  if (!conv) return;
  const scoreStr = conv.details?.Score || "80";
  const score = parseInt(scoreStr, 10) || 80;
  await api("/api/leads", {
    method: "POST",
    body: JSON.stringify({
      name: conv.lead,
      car_interest: conv.intent || "A definir",
      store_id: conv.store_id,
      stage: "Humano",
      score,
      budget: conv.details?.Entrada || "A definir",
      source: "WhatsApp",
    }),
  });
  await refreshAndRender();
  showView("crm");
  showToast("Lead enviado para o CRM");
}

function runQrAction() {
  if (currentRole() === "master") {
    openStoreModal();
  } else {
    $(".qr-code").classList.toggle("qr-active");
    showToast(currentRole() === "lojista" ? "QR Code renovado para seu WhatsApp" : "QR Code de lojista gerado");
  }
}

// ---------- Auth ----------
async function loginWithCredentials(email, password) {
  const r = await api("/api/login", { method: "POST", body: JSON.stringify({ email, password }) });
  currentUser = r.user;
  loginLayer.classList.remove("show");
  await refreshAndRender();
  applyRole();
}

async function restoreSession() {
  try {
    const r = await api("/api/me");
    if (r.user) {
      currentUser = r.user;
      loginLayer.classList.remove("show");
      await refreshAndRender();
      applyRole();
      connectEventStream();
      return true;
    }
  } catch (_) {}
  return false;
}

let eventSource = null;
function connectEventStream() {
  if (eventSource) { try { eventSource.close(); } catch (_) {} }
  eventSource = new EventSource("/api/events");

  eventSource.addEventListener("conversation.updated", async (e) => {
    try {
      const evt = JSON.parse(e.data);
      await api("/api/conversations").then((r) => {
        conversations = r.conversations || [];
        renderConversations();
        if (currentConversationId === evt.conversation_id) renderChat();
      });
    } catch (err) {}
  });

  eventSource.addEventListener("lead.updated", async (e) => {
    try {
      await api("/api/leads").then((r) => {
        leads = (r.leads || []).map(normalizeLead);
        renderKanban();
      });
    } catch (err) {}
  });

  eventSource.addEventListener("message.created", async (e) => {
    try {
      const evt = JSON.parse(e.data);
      await Promise.all([
        api("/api/conversations").then((r) => {
          conversations = r.conversations || [];
          renderConversations();
        }),
        api("/api/dashboard/team").then((r) => {
          teamData = r.team || [];
          renderTeam();
        }).catch(e => console.error("Sem acesso à equipe", e)),
      ]);
      if (!currentConversationId && evt.conversation_id) {
        currentConversationId = evt.conversation_id;
      }
      renderChat();
      // toast discreto somente para mensagens de lead (entrada nova)
      if (evt.sender === "lead") showToast("Nova mensagem recebida");
    } catch (err) {
      console.warn("Falha ao processar evento SSE", err);
    }
  });
  eventSource.onerror = () => {
    // browser reconecta sozinho — apenas loga
    console.warn("SSE desconectado, browser tentará reconectar");
  };
}

async function logout() {
  try { await api("/api/logout", { method: "POST" }); } catch (_) {}
  currentUser = null;
  stores = []; vehicles = []; leads = []; conversations = []; currentConversationId = null;
  loginLayer.classList.add("show");
  sessionButton.textContent = "Entrar";
  sessionButton.title = "Entrar no portal";
}

// ---------- Utils ----------
function formatMoney(value) {
  return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}
function countBy(arr, key) {
  return arr.reduce((acc, item) => { acc[item[key]] = (acc[item[key]] || 0) + 1; return acc; }, {});
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}

// ---------- Event wiring ----------
$$("[data-view]").forEach((btn) => btn.addEventListener("click", () => showView(btn.dataset.view)));

$("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = $("#loginError");
  error.hidden = true;
  try {
    await loginWithCredentials($("#loginEmail").value.trim(), $("#loginPassword").value);
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});

sessionButton.addEventListener("click", () => logout());

storeFilter.addEventListener("change", renderKanban);
if (sellerFilter) sellerFilter.addEventListener("change", renderKanban);
stageFilter.addEventListener("change", renderKanban);

$("#replyForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#replyInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  try { await sendReply(text); } catch (err) { showToast(err.message); }
});

$("#newVehicleButton").addEventListener("click", () => openVehicleModal());
$("#newStoreButton").addEventListener("click", () => openStoreModal());
$("#newSellerButton").addEventListener("click", () => openSellerModal());
$("#qrActionButton").addEventListener("click", runQrAction);
$("#assumeConversationButton").addEventListener("click", () => updateConversationStatus("Em atendimento").catch((e) => showToast(e.message)));
$("#closeConversationButton").addEventListener("click", () => updateConversationStatus("Encerrado").catch((e) => showToast(e.message)));
$("#sendToCrmButton").addEventListener("click", () => createLeadFromConversation().catch((e) => showToast(e.message)));

modalLayer.addEventListener("click", (event) => {
  if (event.target.dataset.modalClose) closeModal();
});

kanban.addEventListener("click", (event) => {
  const button = event.target.closest("[data-lead-action]");
  if (!button) return;
  const id = Number(button.dataset.leadId);
  if (button.dataset.leadAction === "advance") advanceLead(id);
  else moveLeadToHuman(id);
});

vehicleGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-vehicle-action]");
  if (!button) return;
  const id = Number(button.dataset.vehicleId);
  if (button.dataset.vehicleAction === "toggle") toggleVehicle(id);
  if (button.dataset.vehicleAction === "edit") openVehicleModal(vehicles.find((v) => v.id === id));
  if (button.dataset.vehicleAction === "delete") deleteVehicle(id);
});

storeTable.addEventListener("click", (event) => {
  const button = event.target.closest("[data-store-action]");
  if (!button) return;
  const id = Number(button.dataset.storeId);
  if (button.dataset.storeAction === "toggle") toggleStore(id);
  if (button.dataset.storeAction === "delete") deleteStore(id);
});

$("#notificationButton").addEventListener("click", () => {
  const role = currentRole();
  const count = role === "lojista" ? 3 : role === "shopping" ? 8 : 12;
  showToast(`${count} eventos pedem atenção neste acesso`);
});

$("#globalSearch").addEventListener("input", (event) => {
  const term = event.target.value.trim().toLowerCase();
  if (!term) { renderVehicles(); return; }
  const matches = vehicles.filter((v) =>
    [v.name, v.store, v.status, ...v.meta].join(" ").toLowerCase().includes(term)
  );
  renderVehicles(matches);
});

// ---------- Boot ----------
(async function init() {
  const restored = await restoreSession();
  if (!restored) loginLayer.classList.add("show");
  
  if ('serviceWorker' in navigator) {
    try {
      await navigator.serviceWorker.register('/sw.js');
    } catch (e) {
      console.error('Falha ao registrar Service Worker', e);
    }
  }
})();
