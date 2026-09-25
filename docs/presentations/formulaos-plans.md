Searched for "planos"
Searched for "assinatura"
Searched for "plan"
Viewed app.js:600-660
Searched for "plan"
Viewed test_rbac.py:30-52
Viewed seed.py:1-100
Searched for "Enterprise"
Viewed app.js:1450-1485
Searched for "1290"
Viewed app.js:750-820
Viewed stores.py:1-70
Viewed billing.py:1-70
Searched for ""Start""
Searched for "FormulaOS"

No ecossistema do **FormulaOS (ASF-3)**, os planos de assinatura para lojistas estão modelados em **3 níveis** (configurados no cadastro de lojas, no seed e no módulo de billing):

---

### 💳 Tabela de Planos de Assinatura

| Plano | Mensalidade | Perfil Recomendado / Elegibilidade | Custo Operacional Médio (WhatsApp + IA) | Margem da Plataforma |
| :--- | :---: | :--- | :---: | :---: |
| **Start** | **Gratuito (R$ 0,00)** | **Padrão para todas as lojas da rede**. Nenhuma loja aderiu ao Pro ainda; 100% da rede opera neste plano de entrada. | ~R$ 150 a R$ 250 / mês (absorvido pelo shopping) | N/A (modelo de atração de rede) |
| **Pro** | **R$ 1.500,00 / mês** | Lojas com alto volume de vendas que desejam suporte dedicado e recursos premium. | ~R$ 420 a R$ 510 / mês | ~66% |
| **Enterprise** | **R$ 18.400,00 / mês** | **Exclusivo para Tenants / Shoppings** (Auto Shopping Fórmula central). Proibido para lojistas individuais. | ~R$ 3.840 / mês | ~79% |

---

### 📦 O Que Está Incluído nos Planos

1. **Vendedor Virtual 24/7 (Agente SDR Rafael via WhatsApp):**
   * Atendimento imediato em menos de 5 segundos.
   * Consulta dinâmica de estoque em tempo real (RAG leve via SQL, sem alucinações).
   * Transcrição de áudio nativa (OpenAI Whisper) e recebimento de fotos para avaliação de troca.
   * Trava anti-spam de leads duplicados (`POS_ATENDIMENTO`).

2. **Multiatendimento e CRM Móvel (Web App):**
   * Painel de atendimento em tempo real via Server-Sent Events (SSE).
   * Transbordo humano em 1 clique (pausa automática do robô).
   * Temporizador de auto-reativação da IA (evita que o cliente fique sem resposta se o vendedor demorar).
   * Drawer de ficha do lead: histórico de buscas, veículo de interesse, valor de entrada e carro na troca.

3. **Vitrine Digital & Gestão de Estoque:**
   * Publicação dos veículos na vitrine do portal (`/estoque.html`).
   * Pipeline de fotos com CDN Cloudflare (8 resoluções automáticas otimizadas para mobile e desktop).

4. **Distribuição de Leads:**
   * **Modo Normal:** Leads diretos do anúncio da loja caem direto para o vendedor dela.
   * **Modo Feirão:** Participação no algoritmo de rodízio e distribuição justa entre os lojistas ativos da rede.

---

### 📊 Unit Economics & Consumo
* **Custo estimado por lead qualificado:** ~**R$ 12,00** (incluindo processamento de tokens LLM e tráfego de mensagens WhatsApp).
* **Tarifação transparente:** O painel administrativo agrega o consumo por loja (`/api/billing/summary`), permitindo ao shopping/operador controlar os custos de API e a lucratividade de cada lojista parceiro.