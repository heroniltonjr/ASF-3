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
    <a class="vehicle-card" href="/veiculo.html?id=${v.id}">
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
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      links.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!links.contains(e.target) && !toggle.contains(e.target)) {
        links.classList.remove('open');
      }
    });
    links.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => links.classList.remove('open'));
    });
  }

  // marca link ativo
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href && (path === href || (href !== '/' && path.startsWith(href)))) {
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

// --- Card de loja (compartilhado home + página /lojas) ------------------
function storeCardHTML(s) {
  const logo = s.logo
    ? `<div class="store-logo has-img" style="overflow:hidden;"><img src="${s.logo}" alt="${s.name}" loading="lazy" style="height:40px;max-height:40px;width:auto;max-width:100%;object-fit:contain;display:block;" /></div>`
    : `<div class="store-logo">${s.name.charAt(0)}</div>`;
  const sub = s.city || (s.type === 'Shopping' ? 'Shopping consolidador' : 'Loja parceira');
  const label = s.active_vehicles === 1 ? 'veículo no estoque' : 'veículos no estoque';
  return `
    <a class="store-card" href="/estoque.html?store=${encodeURIComponent(s.id)}">
      ${logo}
      <h3>${s.name}</h3>
      <p>${sub}</p>
      <div class="store-count">${s.active_vehicles} ${label}</div>
    </a>
  `;
}

// --- Home: grid de lojas ------------------------------------------------
async function loadStoresGrid(selector, limit = 12) {
  const container = document.querySelector(selector);
  if (!container) return;
  try {
    const data = await fetchJSON('/api/public/stores');
    container.innerHTML = data.items.slice(0, limit).map(storeCardHTML).join('');
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
  const filterBtn = document.querySelector('#mobileFilterBtn');
  const filtersAside = document.querySelector('#filtersAside') || document.querySelector('.filters');
  if (!grid || !form) return;

  if (filterBtn && filtersAside) {
    filterBtn.addEventListener('click', () => {
      filtersAside.classList.toggle('is-open');
      filterBtn.classList.toggle('active');
    });
  }

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

      // No mobile, recolhe os filtros ao atualizar para focar nos resultados
      if (window.innerWidth <= 960 && filtersAside && filtersAside.classList.contains('is-open')) {
        filtersAside.classList.remove('is-open');
        if (filterBtn) filterBtn.classList.remove('active');
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
    const images = (Array.isArray(v.images) && v.images.length) ? v.images : [imageFor(v)];
    root.innerHTML = `
      <div class="veh-detail">
        <div>
          ${galleryHTML(images, v.name)}
        </div>
        <div class="veh-sidebar">
          <span class="vehicle-store">${v.store_name}</span>
          <h1>${v.name}</h1>
          <div class="price">${formatPrice(v.price)}</div>
          <div class="veh-specs">
            ${v.year       ? `<div class="spec"><small>Ano</small><strong>${v.year}</strong></div>` : ''}
            ${v.mileage    ? `<div class="spec"><small>Quilometragem</small><strong>${v.mileage}</strong></div>` : ''}
            ${v.transmission ? `<div class="spec"><small>Câmbio</small><strong>${v.transmission}</strong></div>` : ''}
            ${v.fuel       ? `<div class="spec"><small>Combustível</small><strong>${v.fuel}</strong></div>` : ''}
            ${v.color      ? `<div class="spec"><small>Cor</small><strong>${v.color}</strong></div>` : ''}
            <div class="spec"><small>Status</small><strong>${v.status}</strong></div>
          </div>
          <div class="veh-store-tag">
            ${v.store_logo ? `<img class="veh-store-logo" src="${v.store_logo}" alt="${v.store_name}" />` : ''}
            <div class="veh-store-info">
              <span>Vendido por <strong>${v.store_name}</strong></span>
              ${v.store_city ? `<small>${v.store_city}</small>` : ''}
            </div>
            <a href="/estoque.html?store=${encodeURIComponent(v.store_id)}">Ver estoque</a>
          </div>
          ${simulatorHTML(v.price)}
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
    bindSimulator(v.price);
    bindGallery(images);
  } catch (err) {
    console.error(err);
    root.innerHTML = '<div class="empty-state">Veículo indisponível.</div>';
  }
}

// --- Galeria de fotos do veículo (carrossel) ----------------------------
function galleryHTML(images, name) {
  const safeName = (name || 'Veículo').replace(/"/g, '&quot;');
  const fallback = STOCK_PHOTOS[0];
  const onErr = `this.onerror=null;this.src='${fallback}'`;
  const multi = images.length > 1;
  const nav = multi ? `
    <button type="button" class="veh-gallery-nav prev" aria-label="Foto anterior">‹</button>
    <button type="button" class="veh-gallery-nav next" aria-label="Próxima foto">›</button>
    <span class="veh-gallery-counter"><span id="veh-gallery-pos">1</span> / ${images.length}</span>
  ` : '';
  const thumbs = multi ? `
    <div class="veh-thumbs" id="veh-thumbs">
      ${images.map((src, i) => `
        <button type="button" class="veh-thumb${i === 0 ? ' active' : ''}" data-idx="${i}" aria-label="Foto ${i + 1}">
          <img src="${src}" alt="${safeName} — foto ${i + 1}" loading="lazy" onerror="${onErr}" />
        </button>
      `).join('')}
    </div>
  ` : '';
  return `
    <div class="veh-gallery-wrap" id="veh-gallery" tabindex="0">
      <div class="veh-gallery">
        <img id="veh-gallery-main" src="${images[0]}" alt="${safeName}" onerror="${onErr}" />
        ${nav}
      </div>
      ${thumbs}
    </div>
  `;
}

function bindGallery(images) {
  const wrap = document.getElementById('veh-gallery');
  if (!wrap || images.length < 2) return;
  const main = document.getElementById('veh-gallery-main');
  const pos = document.getElementById('veh-gallery-pos');
  const thumbs = [...wrap.querySelectorAll('.veh-thumb')];
  let idx = 0;

  const show = (n) => {
    idx = (n + images.length) % images.length;
    main.src = images[idx];
    thumbs.forEach((t, i) => t.classList.toggle('active', i === idx));
    if (pos) pos.textContent = idx + 1;
    const active = thumbs[idx];
    if (active) active.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
  };

  thumbs.forEach(t => t.addEventListener('click', () => show(Number(t.dataset.idx))));
  const prev = wrap.querySelector('.veh-gallery-nav.prev');
  const next = wrap.querySelector('.veh-gallery-nav.next');
  if (prev) prev.addEventListener('click', () => show(idx - 1));
  if (next) next.addEventListener('click', () => show(idx + 1));
  wrap.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); show(idx - 1); }
    if (e.key === 'ArrowRight') { e.preventDefault(); show(idx + 1); }
  });
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

// --- Simulador de Financiamento -----------------------------------------
function simulatorHTML(priceVal) {
  return `
    <div class="simulator-box" id="financing-simulator">
      <h3>Simular Financiamento</h3>
      
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
        <div class="field" style="margin: 0;">
          <label style="font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase;">Entrada (R$)</label>
          <input type="number" id="sim-entry-input" placeholder="Ex: 20000" style="width: 100%; padding: 10px; border: 1px solid var(--asf-border-strong); border-radius: var(--radius-sm); font-size: 14px;" />
        </div>
        <div class="field" style="margin: 0;">
          <label style="font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase;">Taxa (% a.m.)</label>
          <input type="number" step="0.01" id="sim-rate-input" value="1.59" style="width: 100%; padding: 10px; border: 1px solid var(--asf-border-strong); border-radius: var(--radius-sm); font-size: 14px;" />
        </div>
      </div>
      
      <label style="display: block; font-size: 11px; font-weight: 700; color: #555; text-transform: uppercase; margin-bottom: 8px;">Prazo</label>
      <div class="simulator-terms">
        <button type="button" class="sim-term-btn" data-term="12">12x</button>
        <button type="button" class="sim-term-btn" data-term="24">24x</button>
        <button type="button" class="sim-term-btn" data-term="36">36x</button>
        <button type="button" class="sim-term-btn active" data-term="48">48x</button>
        <button type="button" class="sim-term-btn" data-term="60">60x</button>
      </div>

      <div class="simulator-result-box">
        <div class="sim-res-label">Sua parcela estimada:</div>
        <div class="sim-res-value" id="sim-result-pmt">--</div>
        <div class="sim-res-notice" id="sim-notice">Sujeito a análise de crédito.</div>
      </div>
    </div>
  `;
}

function bindSimulator(priceStr) {
  const sim = document.getElementById('financing-simulator');
  if (!sim) return;

  const parseCurrencyToFloat = (val) => {
    if (typeof val === 'number') return val;
    if (!val) return 0;
    const clean = val.toString().replace(/[R$\s\.]/g, '').replace(',', '.');
    return parseFloat(clean) || 0;
  };
  
  const formatBRL = (num) => {
    return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  };

  const vehiclePrice = parseCurrencyToFloat(priceStr);

  const entryInput = document.getElementById('sim-entry-input');
  const rateInput = document.getElementById('sim-rate-input');
  const termBtns = document.querySelectorAll('.sim-term-btn');
  const resultPmt = document.getElementById('sim-result-pmt');

  // Inicializa a entrada com 30% do valor do veículo
  entryInput.value = vehiclePrice ? Math.floor(vehiclePrice * 0.3) : 0;

  let currentTerm = 48;

  const calculate = () => {
    if (!vehiclePrice) return;
    
    // Limita a entrada entre 0 e o valor total do carro
    let downPayment = parseFloat(entryInput.value) || 0;
    if (downPayment < 0) downPayment = 0;
    if (downPayment > vehiclePrice) downPayment = vehiclePrice;
    
    const pv = vehiclePrice - downPayment;

    if (pv <= 0) {
      resultPmt.innerHTML = '<strong>À vista</strong>';
      return;
    }

    const rateVal = parseFloat(rateInput.value) || 0;
    const i = rateVal / 100;
    const n = currentTerm;

    if (i <= 0) {
      const pmt = pv / n;
      resultPmt.innerHTML = `${n}x de <strong>${formatBRL(pmt)}</strong>`;
      return;
    }

    // Tabela Price: PMT = PV * [ i * (1+i)^n ] / [ (1+i)^n - 1 ]
    const factor = (i * Math.pow(1 + i, n)) / (Math.pow(1 + i, n) - 1);
    const pmt = pv * factor;

    resultPmt.innerHTML = `${n}x de <strong>${formatBRL(pmt)}</strong>`;
  };

  entryInput.addEventListener('input', calculate);
  rateInput.addEventListener('input', calculate);
  
  termBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      termBtns.forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      currentTerm = parseInt(e.target.dataset.term, 10);
      calculate();
    });
  });

  calculate(); // init
}

// --- Página /lojas/ ------------------------------------------------------
async function initLojasPage() {
  const container = document.querySelector('#lojas-grid');
  if (!container) return;
  try {
    const data = await fetchJSON('/api/public/stores');
    container.innerHTML = data.items.map(storeCardHTML).join('');
  } catch (err) {
    console.error(err);
    container.innerHTML = '<div class="empty-state">Lojas indisponíveis no momento.</div>';
  }
}

// --- Botão Flutuante do WhatsApp ----------------------------------------
function initFloatingWhatsApp() {
  if (document.querySelector('.asf-whatsapp-float')) return;

  const a = document.createElement('a');
  a.className = 'asf-whatsapp-float';
  a.href = 'https://wa.me/556592156577';
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.setAttribute('aria-label', 'Falar no WhatsApp');
  a.title = 'Falar no WhatsApp';
  a.innerHTML = `
    <span class="whatsapp-tooltip">Falar no WhatsApp</span>
    <svg width="34" height="34" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91C2.13 13.66 2.59 15.36 3.45 16.86L2.05 22L7.3 20.62C8.75 21.41 10.38 21.83 12.04 21.83C17.5 21.83 21.95 17.38 21.95 11.92C21.95 9.27 20.92 6.78 19.05 4.91C17.18 3.03 14.69 2 12.04 2ZM12.05 20.16C10.57 20.16 9.12 19.76 7.85 19L7.55 18.82L4.43 19.64L5.26 16.6L5.06 16.29C4.24 14.98 3.8 13.47 3.8 11.91C3.8 7.37 7.5 3.67 12.05 3.67C14.25 3.67 16.31 4.53 17.87 6.09C19.42 7.65 20.28 9.72 20.28 11.92C20.28 16.46 16.58 20.16 12.05 20.16ZM16.57 14.45C16.32 14.33 15.1 13.73 14.88 13.65C14.65 13.57 14.49 13.53 14.32 13.78C14.16 14.03 13.69 14.58 13.55 14.74C13.41 14.9 13.26 14.92 13.02 14.8C12.77 14.68 11.98 14.42 11.04 13.58C10.31 12.92 9.82 12.11 9.68 11.87C9.54 11.62 9.66 11.49 9.79 11.36C9.9 11.25 10.03 11.07 10.15 10.93C10.28 10.79 10.32 10.69 10.4 10.52C10.48 10.36 10.44 10.22 10.38 10.1C10.32 9.98 9.82 8.76 9.62 8.27C9.42 7.79 9.22 7.85 9.07 7.85C8.93 7.84 8.76 7.84 8.6 7.84C8.44 7.84 8.17 7.9 7.95 8.15C7.72 8.39 7.09 8.98 7.09 10.2C7.09 11.42 7.98 12.59 8.1 12.75C8.22 12.92 9.85 15.42 12.33 16.49C12.92 16.75 13.38 16.9 13.73 17.02C14.32 17.2 14.86 17.18 15.29 17.11C15.77 17.04 16.76 16.51 16.97 15.93C17.17 15.36 17.17 14.87 17.11 14.77C17.05 14.66 16.89 14.59 16.57 14.45Z"/>
    </svg>
  `;
  document.body.appendChild(a);
}

// --- Dispatcher: roda iniciadores baseado em data-page ------------------
window.addEventListener('DOMContentLoaded', () => {
  initFloatingWhatsApp();
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
