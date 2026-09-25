# Relatório de Análise Técnica: Agente Rafael (n8n) & Mapeamento para o FormulaOS (ASF-3)

## 📌 1. Visão Geral do Agente Rafael
O **Agente Rafael** é um assistente virtual de vendas (SDR) criado para o Auto Shopping Fórmula. Sua função é atender clientes via WhatsApp, qualificar o interesse de compra de veículos, realizar buscas no catálogo em tempo real, coletar dados de pagamento e transferir a oportunidade para os consultores das lojas parceiras.

---

## 🏗️ 2. Estrutura dos Fluxos no n8n

### 2.1. Arquitetura Conversacional
- **Modelo LLM**: OpenAI `gpt-5-mini` com temperatura e histórico gerenciado via `Window Buffer Memory` (janela de 250 mensagens, chave `chatLid`).
- **Tratamento de Mídia**: O nó `Switch` diferencia a mensagem recebida:
  - **Texto**: Encaminhado diretamente para a memória e o agente.
  - **Voz (`Voice`)**: Baixado via `HTTP Request` e transcrito com OpenAI Whisper (`audio.transcribe`).
  - **Imagens e Documentos**: Desviados para rotas dedicadas.

---

## 🔄 3. Comparativo: Modo Normal vs. Modo Feirão

| Atributo | Modo Normal (`AgenteSDRWpp.json`) | Modo Feirão (`AgenteSDRWpp_Feirao.json`) |
| :--- | :--- | :--- |
| **Objetivo** | Atendimento direcionado para a loja específica do veículo. | Distribuição justa e qualificada durante feirões/eventos. |
| **Ferramenta de Loja** | `BuscaNumeroLoja` (`BuscaNumeroLojaV2.json`). | `SelecionaLoja` (`SelectStore_V2.json`). |
| **Lógica de Escolha** | Consulta SQL buscando o nome exato da loja do anúncio (`ILIKE`). | Algoritmo Round-Robin / Load Balancer baseado em menor quantidade de leads no mês e menor atividade recente. |
| **Encaminhamento** | Envia a mensagem para a loja dona do carro. | Envia a mensagem para a loja selecionada pelo rodízio do feirão. |

---

## 🛠️ 4. Detalhamento das Ferramentas (Sub-workflows)

### 4.1. `BuscaRapida` (`QuickSearchV3.json`)
- **Parâmetros**: `brand`, `model`, `category`, `year_from`, `year_to`, `price_min`, `price_max`.
- **Lógica SQL**:
  - Trata filtros vazios/nulos convertendo para wildcard (`_ALL_`).
  - Aplica limites padrão de ano (`1949` até ano atual) e preço (`R$ 20.000` a `R$ 300.000`).
  - Ordena por menor preço, ano mais recente, marca e modelo.
- **Saída**: Retorna lista com até 9 opções (`identifier`, `brand`, `name`, `version`, `model`, `store`, `model_year`, `km`, `price`, `exchange`, `fuel_text`, `color`, `doors`, `kind`, `item_list`, `plate`, `shielded`).

### 4.2. `BuscaNumeroLoja` (`BuscaNumeroLojaV2.json`)
- **Query**:
  ```sql
  WITH matched AS (
    SELECT * FROM stores s
    WHERE store_name ILIKE '%' || $1 || '%' OR store_focal ILIKE '%' || $1 || '%'
  )
  SELECT * FROM matched
  UNION ALL
  SELECT * FROM stores s WHERE s.store_name = 'AraraAzul' AND NOT EXISTS (SELECT 1 FROM matched);
  ```

### 4.3. `SelecionaLoja` (`SelectStore_V2.json`)
- **Query de Rodízio / Load Balancing**:
  ```sql
  SELECT * FROM public.stores
  WHERE store_active IS TRUE
  ORDER BY
      COALESCE(leads_this_month, 0) ASC,
      COALESCE(updated_at, '1970-01-01') ASC,
      COALESCE(total_leads, 0) ASC,
      random()
  LIMIT 1;
  ```

### 4.4. `SendMessage` (`SendMessageV2.json`)
- **Lógica de Execução**:
  1. Incrementa os contadores de lead da loja selecionada (`UPDATE public.stores SET total_leads = total_leads + 1, leads_this_month = leads_this_month + 1, updated_at = NOW()`).
  2. Registra o evento de envio na tabela `messages_sent`.
  3. Envia o resumo via Z-API para o número da loja destinatária e para o número da central/monitoramento.

---

## 🚦 5. Regras de Conduta & Trava de Duplicados
- **Linguagem Positiva**: Proibido responder "não tem" ou "não achei". Sempre oferecer alternativas e destacar cidades polo (Cuiabá e Várzea Grande).
- **Gatilhos de Autoridade**: Reforçar "30+ lojas", "15 anos de mercado", "Maior acervo do Centro-Oeste".
- **Trava de Lead Duplicado (`POS_ATENDIMENTO`)**: Após o envio bem-sucedido via `SendMessage`, o estado muda para `POS_ATENDIMENTO`. Mensagens de cortesia do cliente ("obrigado", "valeu") não disparam a ferramenta de envio novamente, evitando SPAM nos lojistas.

---

## 👥 6. Intervenção Humana & Pausa/Retomada da IA (Handoff no FormulaOS)

No **FormulaOS (ASF-3)**, o mecanismo de intervenção humana já possui suporte nativo e será integrado ao Agente Rafael da seguinte forma:

1. **Observação em Tempo Real**:
   - Todas as conversas são transmitidas em tempo real para a interface de multiatendimento via **Server-Sent Events (SSE)** através da rota `/api/events`. O operador vê novas mensagens do lead, respostas da IA e notas instantaneamente.
2. **Pausa Automática da IA ao Assumir**:
   - Quando o atendente envia uma mensagem pela plataforma (`POST /api/conversations/:id/send`) ou altera o status da conversa para `'Humano'` (`PATCH /api/conversations/:id`), a conversa ganha o status `'Humano'`.
   - No pipeline ([backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)), qualquer conversa com status `'Humano'` ou `'Encerrado'` **suspende automaticamente a execução da IA**, garantindo que o robô não interfira na conversa humana.
3. **Retomada da IA**:
   - O atendente humano pode devolver o controle para a IA a qualquer momento alterando o status da conversa para `'SDR ativo'` pelo painel. A partir do próximo recebimento de mensagem, a IA volta a responder automaticamente.

---

## 🎛️ 7. Controle da Modalidade do Agente (Interface & API)

Para permitir que gestores e administradores alternem com facilidade o comportamento do Agente Rafael no **FormulaOS**:

1. **Interface do Painel (`atendimento.html` / `app.js`)**:
   - Um botão/seletor visual (`Toggle Switch` / `Badge Interativo`) na barra de ferramentas do painel:
     - `🏢 Modo Normal`: Executa o lookup direto da loja proprietária do veículo (`BuscaNumeroLoja`).
     - `🎪 Modo Feirão`: Executa o algoritmo de distribuição justa / rodízio de leads (`SelecionaLoja`).
2. **Backend API (`PUT /api/stores/:id/sdr-mode`)**:
   - Atualiza a coluna `operation_mode` na tabela `stores`.
   - Mudança instantânea em tempo real sem necessidade de reiniciar a aplicação ou reconfigurar credenciais.

---

— Atlas, investigando a verdade 🔎


