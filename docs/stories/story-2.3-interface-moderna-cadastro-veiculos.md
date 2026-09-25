# Story 2.3: Interface Moderna de Cadastro e Edição de Veículos com Galeria Drag & Drop no Portal Admin

## Status: Done

## Description
Como gestor ou lojista parceiro operando no Portal Administrativo (`/admin`),
Eu quero uma interface moderna, organizada e intuitiva para cadastrar e editar veículos,
Para que eu possa subir fotos com pré-visualização instantânea, reordenar a galeria, escolher a foto de capa, selecionar opcionais em chips e preencher todos os dados automotivos sem complexidade.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)

---

## Acceptance Criteria

- [x] **AC1 (Dropzone e Galeria de Fotos - Two-Phase Upload)**:
  - O modal de cadastro deve conter uma área de upload drag & drop aceitando múltiplos arquivos de imagem (`accept="image/*"`).
  - Ao soltar os arquivos, miniaturas locais devem aparecer imediatamente no grid com barra de progresso individual enquanto o upload para `POST /api/vehicles/upload-photos` ocorre em segundo plano.
  - O lojista deve conseguir reordenar as miniaturas arrastando-as (drag & drop), definindo a ordem do array no campo `pictures`.
  - A primeira foto deve possuir destaque visual (badge dourada "★ Foto de Capa"), com botão em cada foto para alternar qual é a foto de capa (`image_path`).
  - Cada miniatura deve possuir botão de exclusão para remoção imediata.
- [x] **AC2 (Classificação Veicular Estruturada)**:
  - Campos separados para Marca (`brand`), Modelo (`model`) e Versão (`version`).
  - Campo "Título Comercial" (`name`) preenchido dinamicamente com base em `[Marca] [Modelo] [Versão] [Ano]`, permitindo edição livre pelo usuário.
  - Dropdown de Categoria (`category`: SUV, Sedan, Hatch, Picape, Cupê, Utilitário, Moto, etc.).
  - Portas (`doors`: 2, 3, 4, 5), Cor (`color`) e Placa (`plate`).
- [x] **AC3 (Ano, KM e Valores com Máscaras)**:
  - Ano Fabricação (`fabrication_year`) e Ano Modelo (`model_year`).
  - Quilometragem com máscara em tempo real (`km` / `mileage`).
  - Preço de Venda com máscara monetária pt-BR (`price`).
  - Câmbio (`transmission`: Automático, Manual, CVT, Automatizado) e Combustível (`fuel`: Flex, Gasolina, Diesel, Elétrico, Híbrido, GNV).
- [x] **AC4 (Badges Comerciais - Toggles)**:
  - Cards ou switches compactos para os booleanos:
    - `featured`: "Destaque na Vitrine"
    - `new_vehicle`: "Veículo 0 km"
    - `shielded`: "Blindado"
    - `in_transit`: "Em Trânsito / Chegando"
    - `sold`: "Vendido"
- [x] **AC5 (Seletor de Opcionais por Chips - `item_list`)**:
  - Grid de chips clicáveis com os opcionais mais frequentes do mercado (Ar condicionado, Direção elétrica, Bancos em couro, Teto solar, Multimídia, Câmera de ré, etc.) + input para digitar itens adicionais personalizados com tecla Enter.
- [x] **AC6 (Diferenciação por Perfil - RBAC)**:
  - Perfil `gestor` e `master`: Título "Cadastro central de veículos", botão "Cadastrar veículo", exibe o dropdown "Lojista" para selecionar a loja dona do carro.
  - Perfil `lojista`: Título "Meus veículos publicados", botão "Cadastrar meu veículo", oculta o dropdown de lojas (o veículo herda a loja do usuário).
- [x] **AC7 (Edição Completa)**:
  - Ao clicar em "Editar" em qualquer veículo da listagem, o modal deve carregar todas as fotos existentes na galeria, badges ativas, opcionais selecionados e campos preenchidos para alteração.
- [x] **AC8 (Testes e Validação)**:
  - Testes de regressão cobrindo o fluxo de criação e atualização de veículos no admin, além de validação visual e aprovação no linter.

---

## Tasks & Checklist

- [x] **Task 1 (Componentes de Estilo)**: Adicionar em `styles.css` os estilos para o novo modal ampliado: dropzone de fotos, grid de miniaturas com badges, chips de opcionais (`.chip-list`, `.chip`), switches toggle e layout em seções/grid.
- [x] **Task 2 (Componente Dropzone no JavaScript)**: Em `app.js`, implementar o componente de upload de fotos desacoplado com pré-visualização instantânea e reordenação drag & drop.
- [x] **Task 3 (Reformulação do Modal de Veículo)**: Atualizar `openVehicleModal()` em `app.js` para renderizar as novas seções: Galeria, Classificação, Ano/KM/Mecânica, Valores, Badges, Opcionais e Observações.
- [x] **Task 4 (Integração de Edição)**: Garantir que a edição de veículos (`data-vehicle-action="edit"`) preencha a galeria existente a partir do array `pictures` e monte os chips selecionados em `item_list`.
- [x] **Task 5 (Cache Busting)**: Atualizar `index.html` para `app.js?v=1.7` e `styles.css?v=1.7`.
- [x] **Task 6 (Validação e Quality Gate)**: Testar fluxos de cadastro e edição nos perfis `gestor` e `lojista`, rodar a suíte completa de testes com `pytest`.

---

## File List

- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFY] [styles.css](file:///c:/ProjetosMLDB/ASF-3/styles.css)
- [MODIFY] [index.html](file:///c:/ProjetosMLDB/ASF-3/index.html)
- [MODIFY] [docs/stories/story-2.3-interface-moderna-cadastro-veiculos.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-2.3-interface-moderna-cadastro-veiculos.md)

---

## Dev Notes
- O modal deve ter largura expandida (`max-width: 860px` ou `920px`) com barra de rolagem suave para garantir conforto visual tanto no desktop quanto em tablets.
- A exclusão de fotos na galeria antes do submit apenas remove o item do array local de URLs, não necessitando deletar imediatamente do R2.
