# Especificação Técnica: Reestruturação dos Planos de Assinatura (Start, Pro, Enterprise)

## 1. Visão Geral
Esta especificação consolida a reestruturação da política de planos de assinatura do Formula OS (ASF-3), estabelecendo um catálogo enxuto e objetivo com **3 planos oficiais**, critérios rigorosos de elegibilidade por tipo de entidade e enquadramento inicial de **100% dos lojistas da rede no plano Start (Gratuito)**.

---

## 2. Catálogo Oficial de Planos

| Plano | Público Alvo / Entidade | Valor Mensal | Descrição e Recursos |
| :--- | :--- | :--- | :--- |
| **Start** | Lojista (`type = 'Lojista'`) | **R$ 0,00 / mês** *(Gratuito)* | **Plano padrão e universal** para todos os lojistas cadastrados na plataforma. Fornece acesso à vitrine, multi-atendimento básico e recepção de leads. Nenhuma loja aderiu ao plano Pro ainda, portanto 100% da rede inicia neste plano. |
| **Pro** | Lojista (`type = 'Lojista'`) | **R$ 1.500,00 / mês** | **Plano profissional** comercializado para lojistas que desejarem recursos avançados, priorização de leads, relatórios estendidos e automações sob medida do SDR. |
| **Enterprise** | Tenant / Shopping (`type IN ('Auto Shopping', 'Tenant')`) | **R$ 18.400,00 / mês** | **Plano exclusivo para a camada Master/Tenant**. Fornece governança de multi-tenancy, distribuição Feirão, analytics consolidado e rateio de custos de IA/WhatsApp. **Bloqueado para lojas individuais**. |

---

## 3. Regras de Negócio e Validações

1. **Exclusividade do Enterprise:**
   - Tentativas de cadastro (`POST /api/stores`) ou edição (`PATCH /api/stores/{id}`) atribuindo `plan = 'Enterprise'` a entidades com `type = 'Lojista'` devem ser sumariamente rejeitadas pelo backend com `HTTP 400` e mensagem `"O plano Enterprise é exclusivo para Tenants"`.
2. **Plano Padrão na Criação de Loja:**
   - Se o campo `plan` for omitido na criação de uma loja, o valor assumido será obrigatoriamente `"Start"`.
3. **Cálculo Automático de Receita Mensal (`monthly_revenue`):**
   - Caso `monthly_revenue` não seja fornecido explicitamente no payload:
     - `Enterprise` -> R$ 18.400,00
     - `Pro` -> R$ 1.500,00
     - `Start` -> R$ 0,00
4. **Migração do Ecossistema Existente:**
   - Todas as 21 lojas lojistas da base existente (incluindo lojas legadas como Seminovos Movida e Betania) passam para `plan = 'Start'` e `monthly_revenue = 0`.
   - Apenas o registro do tenant central ("Auto Shopping Formula") permanece como `Enterprise` (`monthly_revenue = 18400`).

---

## 4. Impacto em Componentes
- **Banco de Dados:** Migration `020_update_subscription_plans.sql` executada na inicialização.
- **Seed:** Atualização do dataset inicial em `backend/seed.py`.
- **API REST:** `backend/routes/stores.py` com validações de elegibilidade e cálculo de receita.
- **Frontend Admin:** `app.js` com opções restritas no formulário (`openStoreModal`) conforme o perfil, e exibição coerente em `renderCosts()`.
