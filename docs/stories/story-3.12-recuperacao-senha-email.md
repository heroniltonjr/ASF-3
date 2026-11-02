# Story 3.12: Recuperação de Senha ("Esqueci minha senha") via E-mail

## Status: Completed

## Description
Como usuário cadastrado no Formula OS,
Eu quero ter a opção "Esqueci minha senha" no popup de login para redefinir minha senha de acesso,
Para que o sistema gere uma nova senha e a envie com segurança para o e-mail cadastrado no meu perfil, permitindo que eu recupere o acesso à conta de forma autônoma.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Serviço de Envio de E-mail)**:
  - Criar `backend/services/email_service.py` configurável via variáveis de ambiente (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SSL`, `SMTP_TLS`).
  - Implementar fallback resiliente: se os dados de SMTP não estiverem configurados, gravar a mensagem em log com aviso e salvar o e-mail em arquivo de log/auditoria (`backend/data/emails_sent.log`), garantindo que o fluxo não quebre em ambiente local/desenvolvimento.

- [x] **AC2 (Endpoint `POST /api/forgot-password`)**:
  - Receber `email` do usuário.
  - Validar formato e buscar o usuário correspondente no banco (com case-insensitive e suporte a `.com` / `.com.br`).
  - Se o usuário existir:
    - Gerar uma nova senha segura de 10 caracteres alfanuméricos com símbolos.
    - Atualizar a senha com `auth.hash_password` no banco de dados.
    - Invalidar sessões anteriores do usuário (`auth.invalidate_user_sessions`).
    - Disparar e-mail com a nova senha para o endereço do usuário.
  - Se o usuário não existir:
    - Retornar mensagem genérica de sucesso (ex: "Se o e-mail estiver cadastrado, as instruções foram enviadas") para evitar enumeração de contas por atacantes.

- [x] **AC3 (Frontend - Popup de Login)**:
  - No card de login (`#loginLayer`), adicionar botão/link "Esqueci minha senha".
  - Abrir sub-vista ou modal com campo para digitar o e-mail cadastrado e botão "Enviar nova senha".
  - Exibir feedback visual de carregamento e mensagem de sucesso/alerta.
  - Fornecer botão para voltar à tela de login tradicional.

- [x] **AC4 (Testes Automatizados)**:
  - Testes em `tests/test_forgot_password.py` cobrindo:
    - Solicitação de reset para e-mail existente (geração de senha, hash atualizado no banco).
    - Login subsequente bem-sucedido com a nova senha recebida.
    - Solicitação para e-mail inexistente com resposta uniforme sem vazar existência de usuário.
    - Rejeição de payload com e-mail inválido.

---

## Tasks & Checklist

- [x] **Task 1**: Criar `backend/services/email_service.py` com suporte a SMTP e fallback seguro.
- [x] **Task 2**: Implementar `POST /api/forgot-password` em `backend/routes/auth_routes.py`.
- [x] **Task 3**: Criar e rodar testes em `tests/test_forgot_password.py`.
- [x] **Task 4**: Atualizar `index.html`, `app.js` e `styles.css` com a interface de recuperação de senha.
