Me conta como foi feita a implementação do agente de atendimento whatsapp no projeto ASF-3

Searched for "whatsapp"
Listed directory whatsapp
Listed directory backend
Viewed CLAUDE.md:1-100
Viewed ingest.py:1-150
Viewed ingest.py:151-291
Viewed sdr.py:1-203
Viewed base.py:1-53
Viewed registry.py:1-39
Listed directory routes
Viewed whatsapp.py:1-100

Com base na análise técnica do código fonte do projeto **ASF-3**, aqui está o mapeamento detalhado da implementação do agente de atendimento via WhatsApp e SDR de IA.

---

### 1. Visão Geral da Arquitetura

O sistema foi desenhado como uma plataforma SaaS multi-tenant para shoppings de veículos e concessionárias. O agente opera como um **SDR (Sales Development Representative) virtual**, responsável por recepcionar o lead no WhatsApp, responder dúvidas com base no estoque real da loja, qualificar o cliente e realizar o transbordo para um vendedor humano.

---

### 2. Camada de Provedores WhatsApp (Adapter Pattern Híbrido)

Para permitir flexibilidade entre APIs oficiais e não-oficiais, a comunicação é desacoplada usando o padrão **Adapter/Registry**:

- **Interface Base**: [backend/whatsapp/base.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/base.py) define o contrato assíncrono padrão (`Provider`), padronizando o envio de mensagens e o parse de payloads brutos em um objeto normalizado `InboundMessage`.
- **Implementações**:
  - **Meta Cloud API (Oficial)**: [backend/whatsapp/meta.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/meta.py) com suporte a verificação de Webhook (`verify_token`) e envio oficial via Meta Graph API.
  - **Evolution API (Não-oficial)**: [backend/whatsapp/evolution.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/evolution.py) com suporte a instâncias dedicadas via API Key.
  - **Z-API (Não-oficial)**: [backend/whatsapp/zapi.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/zapi.py).
- **Registro por Loja**: [backend/whatsapp/registry.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/registry.py) carrega a configuração ativa de cada loja gravada na tabela `whatsapp_providers`.

---

### 3. Pipeline de Ingestão e Orquestração ([backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py))

Quando um evento de mensagem chega pelos endpoints em [backend/routes/whatsapp.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py), o método `handle_inbound` executa a seguinte sequência:

1. **Gestão do Lead e Conversa**:
   - Identifica ou cria o **Lead** (`leads`) e a **Conversa** (`conversations`) atrelados ao número de telefone e à loja (`store_id`).
   - Persiste a mensagem de entrada na tabela `messages`.
   - Loga o evento em `whatsapp_events` e contabiliza a métrica de consumo (`whatsapp_message_in`) na tabela `billing_events`.
2. **Atualização em Tempo Real**:
   - Publica o evento no barramento interno ([backend/events.py](file:///c:/ProjetosMLDB/ASF-3/backend/events.py)) enviando notificações via **SSE (Server-Sent Events)** para atualizar o painel de atendimento web instantaneamente.
3. **Checagem de Intervenção Humana**:
   - Se a conversa estiver com status `'Humano'`, `'Encerrado'`, ou se for identificada uma resposta direta do vendedor pelo celular, a execução do SDR é interrompida.

---

### 4. Inteligência da IA e Consulta ao Estoque ([backend/sdr.py](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py))

Para responder ao lead de forma contextualizada:

1. **Injeção de Estoque**: O pipeline busca no banco de dados SQLite todos os veículos com status `'Publicado'` pertencentes à loja e formata uma lista compacta contendo modelo, preço, quilometragem, transmissão e combustível.
2. **Engenharia de Prompt**: O prompt de sistema define que o agente deve:
   - Ser cordial, coloquial (PT-BR) e usar no máximo um emoji.
   - Limitar as respostas ao ritmo do WhatsApp (até 3 frases).
   - Coletar informações essenciais (orçamento, forma de pagamento, veículo na troca).
   - Incorporar regras e tom de voz específicos configurados por loja (`store_sdr_prompt`).
3. **Execução no OpenRouter**: A requisição é enviada ao OpenRouter API (utilizando o modelo configurado, como `openai/gpt-5-mini`), passando o sistema, o estoque, as instruções da loja e o histórico da conversa.

---

### 5. Qualificação e Transbordo (`[TRANSFERIR]`)

- O prompt instrui o modelo a encerrar a mensagem com a tag obrigatoria `[TRANSFERIR]` quando todas as perguntas de qualificação forem respondidas ou quando o cliente solicitar falar com um atendente.
- Ao detectar `[TRANSFERIR]` na resposta do SDR:
  - A tag é removida antes de enviar a mensagem ao cliente.
  - O status da conversa é alterado automaticamente para `'Humano'`.
  - O estágio do lead no CRM avança para `'Qualificado'`.
  - Um evento SSE é disparado para alertar a equipe humana de vendas.

---

### 6. Armazenamento, Envio e Auditoria

1. **Resiliência de Envio**: A resposta da IA é primeiro salva no banco de dados. Em seguida, o envio ao WhatsApp é tentado pelo provider. Se a API externa falhar, a mensagem permanece preservada no histórico interno.
2. **Telemetria e Custos**: Os tokens consumidos e o custo estimado da API OpenRouter são convertidos para BRL e gravados na tabela `billing_events`.
3. **Auditoria de Qualidade (QA)**: O módulo traz também a função `evaluate_conversation` no [backend/sdr.py](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py), que pode analisar a transcrição de um atendimento humano finalizado e gerar uma nota de 0 a 100 com análise crítica em JSON.

— Atlas, investigando a verdade 🔎