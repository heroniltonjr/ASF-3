// =========================================================================
// Portal público Auto Shopping Fórmula — cliente JS compartilhado
// =========================================================================

const API = '';  // mesmo domínio: /api/public/*

// --- Utilidades ----------------------------------------------------------
async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

function formatPrice(p) {
  if (!p) return '—';
  return p.startsWith('R$') ? p : `R$ ${p}`;
}

function toast(message, kind = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

// Imagem fallback (carros) — usa stock genérico se o veículo não tem foto.
const STOCK_PHOTOS = [
  'https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1552519507-da3b142c6e3d?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1494976388531-d1058494cdd8?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1605559424843-9e4c228bf1c2?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1542362567-b07e54358753?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1583121274602-3e2820c69888?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1617469767053-d3b523a0b982?auto=format&fit=crop&w=900&q=80',
];

function imageFor(vehicle) {
  if (vehicle.image && !vehicle.image.startsWith('assets/')) return vehicle.image;
  // Fallback baseado no id pra ficar estável entre reloads.
  return STOCK_PHOTOS[(vehicle.id || 0) % STOCK_PHOTOS.length];
}

// --- Renderiza card de veículo ------------------------------------------
function vehicleCardHTML(v) {
  const img = imageFor(v);
  return `
    <a class="vehicle-card" href="/portal/veiculo.html?id=${v.id}">
      <div class="vehicle-photo">
        <img src="${img}" alt="${v.name}" loading="lazy" />
        <span class="badge">Publicado</span>
      </div>
      <div class="vehicle-body">
        <span class="vehicle-store">${v.store_name || 'Loja parceira'}</span>
        <h3 class="vehicle-name">${v.name}</h3>
        <div class="vehicle-meta">
          ${v.mileage ? `<span>📍 ${v.mileage}</span>` : ''}
          ${v.transmission ? `<span>⚙️ ${v.transmission}</span>` : ''}
          ${v.fuel ? `<span>⛽ ${v.fuel}</span>` : ''}
        </div>
        <div class="vehicle-price">${formatPrice(v.price)}</div>
      </div>
    </a>
  `;
}

// --- Header: mobile menu toggle -----------------------------------------
window.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('.mobile-toggle');
  const links = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', () => links.classList.toggle('open'));
  }

  // marca link ativo
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href && (path === href || (href !== '/portal/' && path.startsWith(href)))) {
      a.classList.add('active');
    }
  });
});

// --- Home: carrega destaques --------------------------------------------
async function loadHighlights() {
  const container = document.querySelector('#highlights');
  const totals = document.querySelector('#totals');
  if (!container) return;
  try {
    const data = await fetchJSON('/api/public/highlights');
    if (totals) {
      totals.querySelectorAll('[data-total]').forEach(el => {
        const key = el.dataset.total;
        el.textContent = data.totals[key] || 0;
      });
    }
    container.innerHTML = data.latest.map(vehicleCardHTML).join('');
  } catch (err) {
    console.error(err);
    container.innerHTML = '<div class="empty-state">Não foi possível carregar os destaques agora.</div>';
  }
}

// --- Home: grid de lojas ------------------------------------------------
async function loadStoresGrid(selector, limit = 12) {
  const container = document.querySelector(selector);
  if (!container) return;
  try {
    const data = await fetchJSON('/api/public/stores');
    const stores = data.items.slice(0, limit);
    container.innerHTML = stores.map(s => `
      <a class="store-card" href="/portal/estoque.html?store=${s.id}">
        <div class="store-logo">${s.name.charAt(0)}</div>
        <h3>${s.name}</h3>
        <p>${s.type === 'Shopping' ? 'Shopping consolidador' : 'Loja parceira'}</p>
        <div class="store-count">${s.active_vehicles} ${s.active_vehicles === 1 ? 'veículo' : 'veículos'}</div>
      </a>
    `).join('');
  } catch (err) {
    console.error(err);
    container.innerHTML = '<div class="empty-state">Não foi possível listar as lojas agora.</div>';
  }
}

// --- Catálogo: filtros + listagem ---------------------------------------
async function initCatalogo() {
  const grid = document.querySelector('#catalogo-grid');
  const countEl = document.querySelector('#results-count');
  const form = document.querySelector('#filter-form');
  const storeSelect = document.querySelector('#filter-store');
  if (!grid || !form) return;

  // popula select de lojas
  try {
    const stores = await fetchJSON('/api/public/stores');
    storeSelect.innerHTML = '<option value="">Todas as lojas</option>' +
      stores.items.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  } catch (err) { console.error(err); }

  // se vier ?store=ID na URL, pré-seleciona
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('store')) storeSelect.value = urlParams.get('store');
  if (urlParams.get('q')) form.querySelector('[name=q]').value = urlParams.get('q');

  async function runQuery() {
    const fd = new FormData(form);
    const qs = new URLSearchParams();
    for (const [k, v] of fd.entries()) {
      if (v) qs.set(k, v);
    }
    qs.set('limit', '60');
    try {
      grid.innerHTML = '<div class="empty-state">Buscando…</div>';
      const data = await fetchJSON(`/api/public/vehicles?${qs.toString()}`);
      countEl.textContent = `${data.total} ${data.total === 1 ? 'veículo' : 'veículos'} encontrados`;
      if (!data.items.length) {
        grid.innerHTML = '<div class="empty-state">Nenhum veículo encontrado com esses filtros. Tente reduzir os critérios.</div>';
      } else {
        grid.innerHTML = data.items.map(vehicleCardHTML).join('');
      }
    } catch (err) {
      console.error(err);
      grid.innerHTML = '<div class="empty-state">Erro ao carregar veículos.</div>';
    }
  }

  form.addEventListener('submit', e => { e.preventDefault(); runQuery(); });
  form.addEventListener('change', runQuery);
  runQuery();
}

// --- Detalhe do veículo --------------------------------------------------
async function initVehicleDetail() {
  const root = document.querySelector('#veh-root');
  if (!root) return;
  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    root.innerHTML = '<div class="empty-state">Veículo não especificado.</div>';
    return;
  }
  try {
    const data = await fetchJSON(`/api/public/vehicles/${id}`);
    const v = data.vehicle;
    document.title = `${v.name} — Auto Shopping Fórmula`;
    const img = imageFor(v);
    root.innerHTML = `
      <div class="veh-detail">
        <div>
          <div class="veh-gallery"><img src="${img}" alt="${v.name}" /></div>
        </div>
        <div class="veh-sidebar">
          <span class="vehicle-store">${v.store_name}</span>
          <h1>${v.name}</h1>
          <div class="price">${formatPrice(v.price)}</div>
          <div class="veh-specs">
            ${v.mileage    ? `<div class="spec"><small>Quilometragem</small><strong>${v.mileage}</strong></div>` : ''}
            ${v.transmission ? `<div class="spec"><small>Câmbio</small><strong>${v.transmission}</strong></div>` : ''}
            ${v.fuel       ? `<div class="spec"><small>Combustível</small><strong>${v.fuel}</strong></div>` : ''}
            <div class="spec"><small>Status</small><strong>${v.status}</strong></div>
          </div>
          <div class="veh-store-tag">
            <span>Vendido por <strong>${v.store_name}</strong></span>
            <a href="/portal/estoque.html?store=${v.store_id}">Ver estoque</a>
          </div>
          <a class="btn btn-whatsapp" href="${v.whatsapp_link}" target="_blank" rel="noopener">
            💬 Falar agora no WhatsApp
          </a>
          <button class="btn btn-outline" id="open-lead-form">Receber proposta por aqui</button>
        </div>
      </div>
      <div id="lead-form-area" style="display:none; max-width: 720px; margin: 0 auto 60px;">
        ${leadFormHTML(v.id, v.store_id, v.name)}
      </div>
    `;
    document.querySelector('#open-lead-form').addEventListener('click', () => {
      const area = document.querySelector('#lead-form-area');
      area.style.display = 'block';
      area.scrollIntoView({ behavior: 'smooth' });
    });
    bindLeadForm();
  } catch (err) {
    console.error(err);
    root.innerHTML = '<div class="empty-state">Veículo indisponível.</div>';
  }
}

// --- Formulário de captura de lead --------------------------------------
function leadFormHTML(vehicleId, storeId, contextName) {
  return `
    <form class="lead-form" id="lead-form" data-vehicle="${vehicleId || ''}" data-store="${storeId || ''}">
      <h3>Receber proposta do ${contextName || 'consultor'}</h3>
      <p class="form-notice">Preencha que um consultor da loja entra em contato em até 30 minutos pelo WhatsApp.</p>
      <div class="field">
        <label>Nome completo</label>
        <input name="name" required placeholder="Como podemos te chamar?" />
      </div>
      <div class="field">
        <label>WhatsApp (DDD + número)</label>
        <input name="phone" required placeholder="(65) 99999-0000" />
      </div>
      <div class="field">
        <label>Faixa de orçamento (opcional)</label>
        <input name="budget" placeholder="Ex: R$ 80 mil" />
      </div>
      <div class="field">
        <label>Mensagem (opcional)</label>
        <textarea name="message" rows="3" placeholder="Conta um pouco do que você procura"></textarea>
      </div>
      <button class="btn btn-primary" type="submit">Quero receber proposta</button>
      <div id="lead-result"></div>
    </form>
  `;
}

function bindLeadForm() {
  const form = document.querySelector('#lead-form');
  if (!form) return;
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {
      name: fd.get('name'),
      phone: fd.get('phone'),
      message: fd.get('message'),
      budget: fd.get('budget'),
      vehicle_id: form.dataset.vehicle ? Number(form.dataset.vehicle) : null,
      store_id: form.dataset.store ? Number(form.dataset.store) : null,
    };
    const result = form.querySelector('#lead-result');
    result.innerHTML = '';
    try {
      const data = await fetchJSON('/api/public/leads', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      result.innerHTML = `<div class="form-success">
        ✅ Recebemos seu contato! O consultor da loja vai te chamar no WhatsApp em breve.
        <br><small>Protocolo: lead #${data.lead_id} • conversa #${data.conversation_id}</small>
      </div>`;
      form.querySelectorAll('input, textarea').forEach(el => el.value = '');
      toast('Pedido enviado! Aguarde nosso WhatsApp.');
    } catch (err) {
      result.innerHTML = `<div class="form-error">❌ ${err.message}</div>`;
    }
  });
}

// --- Página /lojas/ ------------------------------------------------------
async function initLojasPage() {
  const container = document.querySelector('#lojas-grid');
  if (!container) return;
  try {
    const data = await fetchJSON('/api/public/stores');
    container.innerHTML = data.items.map(s => `
      <a class="store-card" href="/portal/estoque.html?store=${s.id}">
        <div class="store-logo">${s.name.charAt(0)}</div>
        <h3>${s.name}</h3>
        <p>${s.type === 'Shopping' ? 'Shopping consolidador' : 'Loja parceira'} • Plano ${s.plan}</p>
        <div class="store-count">${s.active_vehicles} ${s.active_vehicles === 1 ? 'veículo no estoque' : 'veículos no estoque'}</div>
      </a>
    `).join('');
  } catch (err) {
    console.error(err);
    container.innerHTML = '<div class="empty-state">Lojas indisponíveis no momento.</div>';
  }
}

// --- Dispatcher: roda iniciadores baseado em data-page ------------------
window.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  if (page === 'home') {
    loadHighlights();
    loadStoresGrid('#stores-grid', 8);
  }
  if (page === 'estoque') initCatalogo();
  if (page === 'veiculo') initVehicleDetail();
  if (page === 'lojas') initLojasPage();
  if (page === 'vender' || page === 'contato') bindLeadForm();
});
