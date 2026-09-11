# Arquitetura Técnica: Cadastro de Veículos & Upload de Imagens na CDN Cloudflare

**Documento:** Especificação Arquitetural de Cadastro e Mídias  
**Autor:** Aria (Architect) — Antigravity / AIOX  
**Sistema:** Formula OS / Auto Shopping Fórmula (`ASF-3`)  
**Data:** 10 de Setembro de 2026  
**Status:** Proposto / Em Avaliação  

---

## 1. Visão Geral e Objetivos

O sistema atual de cadastro de veículos no portal administrativo (`app.js` / tela do perfil Gestor/Lojista) apresenta um formulário simplificado com apenas 7 campos básicos (`name`, `price`, `mileage`, `store_id`, `transmission`, `fuel`, `status`) e imagem estática fixa (`assets/car-city.jpg`).

Por outro lado, a tabela de banco de dados do Supabase/PostgreSQL (`public.formulaos_vehicles`) possui **41 colunas** estruturadas para suportar catálogo automotivo profissional, com múltiplos atributos mecânicos, classificação detalhada (marca, modelo, versão, ano), badges comerciais (`featured`, `new_vehicle`, `shielded`, `in_transit`), lista de opcionais (`item_list`), observações comerciais (`note`) e galeria completa de imagens em formato JSON (`pictures`) com foto de capa (`image_path` / `main_image`).

Este documento estabelece:
1. O **mapeamento completo de campos** da tabela `formulaos_vehicles` e a reestruturação da interface do formulário de cadastro.
2. A **arquitetura do pipeline de upload e processamento de imagens** integrado à **CDN Cloudflare** (`https://cdn.autoshoppingformula.com.br`).
3. As especificações de contratos de API, schema de dados e plano de implementação incremental.

---

## 2. Análise Comparativa: Tela Atual vs. Esquema da Tabela

### 2.1 Matriz de Campos da Tabela `formulaos_vehicles`

| Coluna na Tabela | Tipo Postgres | Campo na Tela Atual? | Proposta para a Nova Tela de Cadastro |
| :--- | :--- | :---: | :--- |
| `id` | `serial` (PK) | Auto | Gerado pelo banco |
| `identifier` | `text` (Unique) | Auto | Gerado pela trigger `trg_set_formulaos_vehicles_identifier` |
| `store_id` | `integer` (FK) | ✅ Sim (select) | Select de lojas (perfil Gestor/Master) ou travado na loja do usuário (Lojista) |
| `store` | `text` | Não | Preenchido automaticamente com o nome da loja selecionada |
| `name` | `text` | ✅ Sim (livre) | Título comercial (gerado via sugestão: Marca + Modelo + Versão + Ano, editável) |
| `brand` | `text` | ❌ Não | **Select com autocomplete de marcas** (ex: Chevrolet, Fiat, Honda, Toyota, etc.) |
| `model` | `text` | ❌ Não | **Input/Select de modelo** (ex: Civic, Corolla, Onix, Compass) |
| `version` | `text` | ❌ Não | **Input de versão** (ex: Touring 1.5 Turbo CVT, XEi 2.0) |
| `category` | `text` | ❌ Não | **Select de categoria** (SUV, Sedan, Hatchback, Picape, Cupê, Minivan, Moto, etc.) |
| `kind` | `text` | ❌ Não | Categoria de veículo (Carro, Moto, Caminhão, etc.) |
| `doors` | `integer` | ❌ Não | **Select/Radio de portas** (2, 3, 4, 5) |
| `color` | `text` | ❌ Não | **Select/Input de cor** (Branco, Preto, Prata, Cinza, Vermelho, Azul, etc.) |
| `plate` | `text` | ❌ Não | **Input de placa** (opcional, uso interno para auditoria/rastreamento da loja) |
| `fabrication_year` | `integer` | ❌ Não | **Select/Input de ano de fabricação** (ex: 2021) |
| `model_year` | `integer` | ❌ Não | **Select/Input de ano modelo** (ex: 2022) |
| `price` | `numeric` | ✅ Sim (texto) | **Input numérico com máscara monetária pt-BR** (`R$ 119.900,00`) |
| `km` | `integer` | ❌ Não | **Input numérico de KM** (ex: `48000`) |
| `mileage` | `text` | ✅ Sim (texto) | Formatado automaticamente pela trigger/backend (`48.000 km`) |
| `transmission` | `text` | ✅ Sim (select) | Select (Automático, Manual, CVT, Automatizado) |
| `exchange` | `text` | ❌ Não | Sincronizado automaticamente via trigger com `transmission` |
| `fuel` | `text` | ✅ Sim (select) | Select (Flex, Gasolina, Diesel, Elétrico, Híbrido, GNV) |
| `fuel_text` | `text` | ❌ Não | Sincronizado automaticamente via trigger com `fuel` |
| `status` | `text` | ✅ Sim (select) | Select ("Publicado", "Pausado", "Rascunho", "Vendido") |
| `active` | `boolean` | ❌ Não | Switch/Toggle de visibilidade ativa no estoque |
| `sold` | `boolean` | ❌ Não | Switch/Toggle de veículo vendido |
| `featured` | `boolean` | ❌ Não | **Switch de "Veículo em Destaque"** (vitrine principal) |
| `new_vehicle` | `boolean` | ❌ Não | **Switch de "Veículo 0 km"** |
| `shielded` | `boolean` | ❌ Não | **Switch de "Blindado"** |
| `in_transit` | `boolean` | ❌ Não | **Switch de "Em Trânsito / Chegando"** |
| `item_list` | `text[]` | ❌ Não | **Seletor de Opcionais/Itens de Série** (chips com seleção múltipla) |
| `note` | `text` | ❌ Não | **Textarea de Observações Comerciais** (revisões, cautelar, garantias) |
| `image_path` | `text` | ❌ Falso fixo | **URL da Foto Principal (Capa)** na CDN |
| `main_image` | `text` | ❌ Não | Sincronizado automaticamente com `image_path` |
| `pictures` | `jsonb` | ❌ Não | **Galeria de Fotos** (Array JSON de objetos com `remote_image_url`) |
| `unit_id` | `text` | ❌ Não | Código interno de estoque da loja (opcional) |
| `raw` | `jsonb` | ❌ Não | Metadados internos e integrações |
| `embedding` | `vector` | Auto | Vetor de IA para busca semântica (gerado em background) |
| `batch_id` | `timestamp` | Auto | Controle de lotes de importação |
| `created_at` / `updated_at` | `timestamp` | Auto | Gerados pelo banco |
| `synced_at` | `timestamp` | Auto | Gerado pelo banco/syncer |

---

## 3. Arquitetura da Estratégia de Fotos na CDN Cloudflare

### 3.1 Padrão Existente de Armazenamento e Matriz de 8 Resoluções

A CDN opera com uma estrutura organizada de multi-resolução para atender desde thumbnails e cards móveis até visualizações ampliadas de alta definição. 

- **URL Base:** `https://cdn.autoshoppingformula.com.br`
- **Padrão de Caminho:** `/storage/webdisco/{YYYY}/{MM}/{DD}/{RESOLUCAO}/{HASH_MD5}.jpg`
- **Diretório Físico de Origem no Servidor:** `/opt/formulaos_photos/storage/webdisco/{YYYY}/{MM}/{DD}/`

#### Matriz Oficial de Resoluções e Casos de Uso:

| Resolução | Proporção | Dimensões (Px) | Caso de Uso Principal no Ecossistema |
| :--- | :---: | :---: | :--- |
| **`original`** | Nativa | Variável | Arquivo fonte enviado pelo lojista (backup sem perda para reprocessamentos futuros) |
| **`1200x900`** | 4:3 | 1200 x 900 | **Resolução padrão gravada em `image_path` e `pictures`**; visualização detalhada / desktop |
| **`800x600`** | 4:3 | 800 x 600 | Visualização intermediária / Lightbox / Telas de tablets |
| **`560x420`** | 4:3 | 560 x 420 | Cards de veículos na vitrine/estoque do portal (desktop) |
| **`370x278`** | 4:3 | 370 x 278 | Cards de veículos na visualização mobile (smartphones) |
| **`270x203`** | 4:3 | 270 x 203 | Miniaturas laterais de veículos recomendados / listas compactas |
| **`120x120`** | 1:1 | 120 x 120 | Avatar quadrado recortado no centro (Multiatendimento WhatsApp, CRM, leads) |
| **`80x60`** | 4:3 | 80 x 60 | Carrossel de miniaturas na página interna de detalhes do veículo |

### 3.2 Estrutura do Campo `pictures` (JSONB)
O campo `pictures` na tabela `formulaos_vehicles` armazena a lista de fotos apontando para a resolução base `1200x900`:
```json
[
  {
    "remote_image_url": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/03/1200x900/0da349ff7d245abbbe11a9e2cc7111f97.jpg"
  },
  {
    "remote_image_url": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/03/1200x900/4b0c8fbac43ba57c5d26eed58def2d3d.jpg"
  }
]
```
> **Vantagem Arquitetural:** Como o `{HASH_MD5}.jpg` é idêntico em todas as pastas, qualquer componente cliente (frontend do portal, CRM ou mobile) pode derivar qualquer uma das outras 7 resoluções de forma puramente determinística (ex: substituindo `/1200x900/` por `/370x278/` ou `/120x120/`), viabilizando `srcset` HTML responsivo nativo sem consultas adicionais ao banco.

### 3.3 Estrutura do Campo `image_path` (e `main_image`)
Armazena a URL completa da foto marcada como Principal/Capa:
`https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/03/1200x900/0da349ff7d245abbbe11a9e2cc7111f97.jpg`

---

### 3.4 Pipeline Automatizado de Processamento (FastAPI + Pillow)

```mermaid
flowchart TD
    UI["Frontend Admin (Gestor / Lojista)"] -->|1. Upload Multipart de Fotos| API["POST /api/vehicles/upload-photos"]
    
    subgraph Processamento no Backend (formula-os)
        API --> Val["Valida Arquivo (MIME: JPEG, PNG, WEBP; Max 15MB)"]
        Val --> Hash["Calcula Hash MD5 dos bytes do arquivo original"]
        Hash --> Orig["Grava original: .../storage/webdisco/YYYY/MM/DD/original/{hash}.jpg"]
        
        Orig --> Fork["Fork de Processamento Paralelo (Pillow ImageOps)"]
        
        Fork --> R1200["1200x900 (Fit 4:3, JPEG q=88, Lanczos)"]
        Fork --> R800["800x600 (Fit 4:3, JPEG q=85)"]
        Fork --> R560["560x420 (Fit 4:3, JPEG q=85)"]
        Fork --> R370["370x278 (Fit 4:3, JPEG q=85)"]
        Fork --> R270["270x203 (Fit 4:3, JPEG q=82)"]
        Fork --> R120["120x120 (Crop 1:1 centralizado, JPEG q=80)"]
        Fork --> R80["80x60 (Fit 4:3, JPEG q=80)"]
    end
    
    subgraph Distribuição & CDN
        R1200 & R800 & R560 & R370 & R270 & R120 & R80 --> Storage["Armazenamento no Servidor (/opt/formulaos_photos/...)"]
        Storage --> Caddy["Caddy (cdn.autoshoppingformula.com.br)"]
        Caddy --> Cloudflare["Cloudflare Edge Cache"]
    end
    
    Cloudflare -->|2. Retorna URLs 1200x900 da CDN| UI
    UI -->|3. Salva Veículo| DB[("formulaos_vehicles")]
```

### 3.5 Integração de Infraestrutura (Caddy + Cloudflare)
Para que a CDN pública responda com altíssima performance:
1. **Volume Compartilhado:** No `docker-compose.yml`, montamos `/opt/formulaos_photos:/opt/formulaos_photos` tanto no container `formula-os` (com permissão de escrita para salvar os uploads processados) quanto no container `formula-caddy` (leitura).
2. **Bloco Caddyfile:**
   ```caddyfile
   cdn.autoshoppingformula.com.br {
       tls /etc/caddy/certs/autoshopping.crt /etc/caddy/certs/autoshopping.key
       root * /opt/formulaos_photos
       file_server {
           precompressed gzip
       }
       header {
           Cache-Control "public, max-age=31536000, immutable"
           Access-Control-Allow-Origin "*"
       }
   }
   ```
3. **Cloudflare CDN Edge:** Com a rota ativa no Caddy e Cloudflare no proxy (nuvem laranja), todos os acessos das imagens são cacheados nas bordas da Cloudflare por até 1 ano, garantindo tráfego quase nulo no servidor de origem para visualização pública de estoque.

---

## 4. Design da Nova Experiência de Cadastro (UI/UX)

Para acomodar os dados de forma profissional e sem sobrecarregar o usuário, o modal ou tela de cadastro será dividido em **seções estruturadas**:

### 4.1 Seção 1: Galeria de Fotos (Upload Drag & Drop)
- **Área de Dropzone:** Aceita arrastar múltiplos arquivos ou selecionar da galeria/câmera.
- **Grid de Miniaturas Interativo:**
  - Visualização imediata das fotos enviadas.
  - **Drag & Drop para reordenar:** A ordem definida no grid determina a ordem do array no `pictures`.
  - **Identificador de Foto de Capa:** Badge dourada "★ Foto Principal" na primeira foto, com botão para definir qualquer outra foto como principal com 1 clique.
  - Botão de exclusão (lixeira) em cada miniatura.
  - Indicador de upload com barra de progresso.

### 4.2 Seção 2: Identificação do Veículo
- Linha 1 (Grid 3 colunas):
  - **Marca** (`brand`): Autocomplete com as marcas principais (Chevrolet, Fiat, Ford, Honda, Hyundai, Jeep, Nissan, Renault, Toyota, Volkswagen, etc.).
  - **Modelo** (`model`): Input textual (ex: Civic, Corolla, Onix, Compass, Renegade).
  - **Versão** (`version`): Input textual (ex: Touring 1.5 Turbo CVT, Longitude 1.3 T270).
- Linha 2 (2 colunas):
  - **Título Comercial** (`name`): Preenchido automaticamente sugerindo `[Marca] [Modelo] [Versão] [Ano]`, mantendo edição livre caso o lojista queira personalizar.
  - **Categoria** (`category`): Select (SUV, Sedan, Hatch, Picape, Cupê, Utilitário, Moto, Outro).
- Linha 3 (3 colunas):
  - **Cor** (`color`): Select/Input (Branco, Preto, Prata, Cinza, Vermelho, Azul, Outra).
  - **Portas** (`doors`): Select (2, 3, 4, 5).
  - **Placa** (`plate`): Input com máscara Mercosul (ex: `BRA-2E19`).

### 4.3 Seção 3: Ano, Quilometragem e Mecânica
- Linha 1 (4 colunas):
  - **Ano Fabricação** (`fabrication_year`): Select de anos (ex: 2021).
  - **Ano Modelo** (`model_year`): Select de anos (ex: 2022).
  - **Quilometragem (KM)** (`km`): Input numérico com formatação automática em tempo real (`48.000 km`).
  - **Preço de Venda** (`price`): Input monetário com formatação `R$ 119.900,00`.
- Linha 2 (2 colunas):
  - **Câmbio** (`transmission`): Select (Automático, Manual, CVT, Automatizado).
  - **Combustível** (`fuel`): Select (Flex, Gasolina, Diesel, Híbrido, Elétrico, GNV).

### 4.4 Seção 4: Lojista e Badges Comerciais
- Linha 1:
  - **Loja Parceira** (`store_id`): Select de lojas (visível e editável apenas para perfis Gestor e Master).
  - **Status** (`status`): Select ("Publicado", "Pausado", "Rascunho", "Vendido").
- Linha 2 (Cards de Badges / Switches Toggle):
  - `[ ] Destaque na Vitrine` (`featured`) — Exibe com prioridade na Home do portal.
  - `[ ] Veículo 0 km` (`new_vehicle`) — Selo de veículo novo.
  - `[ ] Blindado` (`shielded`) — Selo de blindagem com documentação.
  - `[ ] Em Trânsito` (`in_transit`) — Veículo em preparação/transporte.
  - `[ ] Vendido` (`sold`) — Marca como indisponível sem excluir do histórico.

### 4.5 Seção 5: Opcionais e Acessórios (`item_list`)
Interface com chips clicáveis com os opcionais mais buscados pelo mercado:
- `[+] Ar Condicionado`
- `[+] Direção Elétrica / Hidráulica`
- `[+] Vidros e Travas Elétricas`
- `[+] Airbags Frontais e Laterais`
- `[+] Freios ABS / EBD`
- `[+] Bancos em Couro`
- `[+] Central Multimídia / Apple CarPlay / Android Auto`
- `[+] Câmera de Ré e Sensor de Estacionamento`
- `[+] Teto Solar Panorâmico`
- `[+] Piloto Automático / Controle de Cruzeiro`
- `[+] Rodas de Liga Leve`
- `[+] Faróis de LED / Xênon`
- `[+] Chave Presencial / Partida por Botão`
- Campo para digitar itens adicionais personalizados.

### 4.6 Seção 6: Observações do Anúncio (`note`)
- Textarea expansível com informações comerciais, laudo cautelar aprovado, histórico de revisões na concessionária e garantia de fábrica ou loja.

---

## 5. Especificação dos Contratos de API (Endpoints)

### 5.1 Endpoint de Upload de Fotos
`POST /api/vehicles/upload-photos`
- **Autenticação:** Sessão ativa (roles: `master`, `gestor`, `lojista`).
- **Content-Type:** `multipart/form-data`
- **Body:** `files: UploadFile[]` (múltiplas imagens)
- **Resposta (200 OK):**
```json
{
  "uploaded": [
    {
      "remote_image_url": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/84027a6fe265b4bf532a5d3bcf630e39.jpg",
      "filename": "84027a6fe265b4bf532a5d3bcf630e39.jpg",
      "width": 1200,
      "height": 900,
      "size": 142850
    }
  ]
}
```

### 5.2 Endpoint de Criação/Atualização do Veículo
`POST /api/vehicles` / `PATCH /api/vehicles/{id}`
- **Body JSON:**
```json
{
  "store_id": 12,
  "name": "Honda Civic Touring 1.5 Turbo 2022",
  "brand": "Honda",
  "model": "Civic",
  "version": "Touring 1.5 Turbo",
  "category": "Sedan",
  "doors": 4,
  "color": "Branco Perolizado",
  "plate": "BRA2E19",
  "fabrication_year": 2021,
  "model_year": 2022,
  "price": 119900.00,
  "km": 48000,
  "mileage": "48.000 km",
  "transmission": "CVT",
  "exchange": "CVT",
  "fuel": "Gasolina",
  "fuel_text": "Gasolina",
  "status": "Publicado",
  "active": true,
  "featured": true,
  "new_vehicle": false,
  "shielded": false,
  "in_transit": false,
  "sold": false,
  "item_list": [
    "Ar condicionado digital",
    "Bancos em couro",
    "Teto solar",
    "Piloto automático adaptativo",
    "Central multimídia"
  ],
  "note": "Veículo periciado com laudo cautelar 100% aprovado. Único dono, todas as revisões feitas na concessionária.",
  "image_path": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/84027a6fe265b4bf532a5d3bcf630e39.jpg",
  "main_image": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/84027a6fe265b4bf532a5d3bcf630e39.jpg",
  "pictures": [
    {
      "remote_image_url": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/84027a6fe265b4bf532a5d3bcf630e39.jpg"
    },
    {
      "remote_image_url": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/9e0420eef6c32bf5ad8093feac8806b8.jpg"
    }
  ]
}
```

---

## 6. Plano de Implementação Sugerido

Recomendamos dividir a execução em 3 stories incrementais:

1. **Story 2.1 — Pipeline de Fotos e Storage CDN:**
   - Implementação do serviço de processamento e redimensionamento de fotos (`1200x900`) com hash MD5 e gerador de diretório por data.
   - Endpoint `POST /api/vehicles/upload-photos`.
   - Suporte ao storage via Cloudflare R2 e fallback em volume local com reverse-proxy CDN.

2. **Story 2.2 — Backend CRUD Expandido para `formulaos_vehicles`:**
   - Atualização de `backend/routes/vehicles.py` para aceitar todas as novas colunas (`brand`, `model`, `version`, `fabrication_year`, `model_year`, `km`, `pictures`, `item_list`, `note`, `category`, `doors`, `color`, `plate`, `featured`, `new_vehicle`, `shielded`, `in_transit`).
   - Adaptação das queries de banco e regras de validação.
   - Testes unitários do CRUD completo.

3. **Story 2.3 — Interface Moderna de Cadastro no Admin Portal:**
   - Criação do novo modal/painel com suporte a abas/seções em [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js) e [index.html](file:///c:/ProjetosMLDB/ASF-3/index.html).
   - Componente de galeria com drag & drop, preview imediato e seleção da foto de capa.
   - Componente de chips de opcionais (`item_list`) e máscaras monetárias/KM.
   - Testes de ponta a ponta com perfis Gestor e Lojista.

---

— Aria, arquitetando o futuro 🏗️
