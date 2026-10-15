# 🔐 Credenciais de Acesso dos Lojistas — Auto Shopping Fórmula

Tabela de usuários gerada automaticamente para os lojistas cadastrados em `formulaos_stores`.

- **Domínio padrão:** `@asformula.com`
- **Perfil de acesso (role):** `lojista`
- **Ambiente de autenticação:** Supabase PostgreSQL (`formulaos_users`) e SQLite local (`portal.sqlite3`)
- **Algoritmo de Hash:** PBKDF2-HMAC-SHA256 (600.000 iterações padrão OWASP)

---

### Tabela de Lojistas e Credenciais

| Loja ID | Nome da Loja | E-mail de Acesso | Senha Inicial | Perfil (Role) | Status |
| :---: | :--- | :--- | :--- | :---: | :---: |
| 2 | **Betania Automoveis** | `betaniaautomoveis@asformula.com` | `j0v2glbJ0X` | `lojista` | Criado |
| 3 | **GX Auto** | `gxauto@asformula.com` | `GpWo4YZdJY` | `lojista` | Criado |
| 4 | **Radar Automóveis** | `radarautomoveis@asformula.com` | `HlpKpYa7t7` | `lojista` | Criado |
| 5 | **JW Veiculos** | `jwveiculos@asformula.com` | `vqqjbBu3AI` | `lojista` | Criado |
| 6 | **Trinity Veículos** | `trinityveiculos@asformula.com` | `APgYuc1D3x` | `lojista` | Criado |
| 7 | **Betel Automóveis** | `betelautomoveis@asformula.com` | `TBCiioR4RS` | `lojista` | Criado |
| 8 | **Dani Multimarcas** | `danimultimarcas@asformula.com` | `UcZB7OoahS` | `lojista` | Criado |
| 9 | **EV Automóveis** | `evautomoveis@asformula.com` | `fbXgMr5qJf` | `lojista` | Criado |
| 10 | **Evidence Multimarcas** | `evidencemultimarcas@asformula.com` | `vlMQsgvt1E` | `lojista` | Criado |
| 11 | **Gilson Automóveis** | `gilsonautomoveis@asformula.com` | `FsAjPL3NRP` | `lojista` | Criado |
| 12 | **Global Automóveis** | `globalautomoveis@asformula.com` | `spZF7VgfIK` | `lojista` | Criado |
| 13 | **GR Car** | `grcar@asformula.com` | `UM7dQY2jS4` | `lojista` | Criado |
| 14 | **Kadosh Automóveis** | `kadoshautomoveis@asformula.com` | `uGGZcZl3wg` | `lojista` | Criado |
| 15 | **Kallicar Multimarcas** | `kallicarmultimarcas@asformula.com` | `4wyjB0KToL` | `lojista` | Criado |
| 16 | **Luan Multimarcas** | `luanmultimarcas@asformula.com` | `t2TS7Ih1uX` | `lojista` | Criado |
| 17 | **Meu Automóvel** | `meuautomovel@asformula.com` | `edsE8pO1KQ` | `lojista` | Criado |
| 18 | **Mundial Automóveis** | `mundialautomoveis@asformula.com` | `XH1b9k1apd` | `lojista` | Criado |
| 19 | **Neri Veículos** | `neriveiculos@asformula.com` | `SktHs2I8hD` | `lojista` | Criado |
| 20 | **Rocha Motors** | `rochamotors@asformula.com` | `vM0ZXlPpIr` | `lojista` | Criado |
| 21 | **RS Motors** | `rsmotors@asformula.com` | `X1Ez2OE5YN` | `lojista` | Criado |
| 22 | **Seminovos Movida** | `seminovosmovida@asformula.com` | `G9LPS8mVXZ` | `lojista` | Criado |
| 23 | **Tex Veículos** | `texveiculos@asformula.com` | `Z5PwKdKGds` | `lojista` | Criado |

---

### 🏢 Acesso da Gestão do Shopping (Perfil Shopping / Gestor)

| Tenant ID | Loja ID / Entidade | Nome do Usuário | E-mail de Acesso | Senha Inicial | Perfil (Role) | Status |
| :---: | :---: | :--- | :--- | :--- | :---: | :---: |
| 2 | 1 | **Miriam** | `miriam@asformula.com` | `UqVxIf1oTw` | `shopping` | Criado |

---

> [!NOTE]
> Os usuários acima têm acesso ao **Portal Administrativo** (`/admin/`) e ao **Painel de Atendimento PWA** (`/atendimento.html`).
> A senha pode ser alterada a qualquer momento pelo usuário através do menu **"Meu Perfil"** no cabeçalho ou menu lateral.
