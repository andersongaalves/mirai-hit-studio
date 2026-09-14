# Mirai Hit Studio - Admin UX Foundation

## Objetivo

O Admin deve ser rapido, previsivel, legivel, responsivo e acessivel para operacao diaria. Produtividade vem antes de decoracao. Esta fundacao orienta J0.2, J0.3 e novos modulos, sem criar framework ou CRUD generico.

## Foundation Implementada em J0.2

- Shell compartilhado com sidebar desktop, navegacao ativa e menu mobile recolhivel.
- Navegacao por botoes reais, foco do titulo ao trocar de modulo e inicializacao idempotente.
- Classes compartilhadas para page header, filter bar, badges semanticos, estados, tabela desktop, card mobile e formularios.
- Helper pequeno de modal com semantica de dialogo, trap de foco, Escape e retorno ao elemento de abertura.
- Toast existente preservado e complementado com regioes `aria-live` e mensagens seguras.
- Producoes, Orcamentos, Servicos, Portfolio e Propostas receberam somente a integracao minima necessaria; J0.3 continua responsavel pelo refinamento profundo de Producoes.

## Referencia Implementada em J0.3

- Producoes e o primeiro modulo de listagem inteiramente alinhado a foundation: page header, filter bar, resumo, estados compartilhados, tabela desktop e entity cards mobile.
- Tabela e cards sao projecoes da mesma lista filtrada e ordenada; nenhuma regra de dominio ou estado paralelo foi criado.
- A partir de 769 px, a tabela concentra cliente/servico, responsavel, status, progresso, prazo e uma acao principal. Ate 768 px, somente os cards equivalentes ficam visiveis.
- Status e prazo usam badges semanticos compartilhados, mantendo sempre o texto legivel. Progresso reutiliza o calculo existente e combina texto com indicador nativo.
- O modal de Producoes usa integralmente o helper compartilhado para dialog, foco inicial, trap, Escape e retorno ao acionador; os blocos e formularios permanecem sob responsabilidade do modulo.
- O comando de limpar filtros atua apenas no estado local, sem nova requisicao, e o empty state diferencia ausencia geral de ausencia causada pelos filtros.
- Clientes/CRM e o segundo modulo construido diretamente sobre a foundation, reutilizando tabela desktop, entity cards mobile, filtros, estados, formulario e modal acessivel sem compartilhar regras de dominio com Producoes.

## Diagnostico Atual

### Shell

**Manter**

- Inicializacao unica de sessao em `initializeAdmin()` e limpeza de estado no logout.
- Navegacao simples por secoes e identidade visual compativel com os tokens F0.4.
- Area principal ampla, adequada para operacao desktop.

**Corrigir em J0.2**

- O menu atual e um dashboard de cards clicaveis, sem sidebar, cabecalho utilitario, modulo ativo ou navegacao por teclado adequada.
- Troca de secao so alterna visibilidade; nao atualiza contexto, foco ou estado de navegacao.
- Titulos, botao de retorno, acoes e larguras sao definidos de formas diferentes por modulo e parte do layout continua inline no HTML.
- A largura ampla precisa de grades e limites de leitura coerentes em cada pagina, sem transformar o admin em uma sequencia de cards decorativos.

**Adiar para J**

- Refinamento premium da marca, animacoes e composicao visual avancada.
- Personalizacao de workspace, atalhos complexos e navegacao por historico de URL.

### Listas, Filtros e Estados

Producoes e a melhor referencia atual: tem estado explicito, ordenacao por urgencia, filtros locais, mensagens de loading/erro/vazio e renderizacao segura por DOM. Orcamentos ja separa filtros, estado, DOM e modal. Servicos tem boa separacao por responsabilidade, mas a listagem e o editor ainda usam convencoes visuais diferentes.

As tres areas repetem listas em `.admin-list-item`, filtros sem uma barra padrao e estados vazios com implementacoes distintas. Producoes ainda usa cards em qualquer largura; para datasets mais densos o padrao deve ser tabela no desktop e card de entidade no mobile. Isso nao exige converter todas as listas de uma vez.

### Modais e Formularios

O modal de Producoes ja demonstra conteudo em blocos, scroll interno, botao de fechar e acoes com bloqueio durante salvamento. Propostas, Orcamentos e Projetos tambem usam o mesmo invólucro visual. Faltam semantica de dialogo, foco inicial, trap de foco, Escape, devolucao de foco e um rodape de acoes consistente.

Forms preservam labels em boa parte da interface e usam notificacoes para resultado. Faltam convencoes unicas para ajuda, erro proximo ao campo, required, loading e acoes. `confirm()` e aceitavel provisoriamente para exclusao, mas a confirmacao deve citar a entidade e migrar para uma confirmacao acessivel quando houver a fundacao modal.

## Shell Canonico

```text
AdminShell
|- Sidebar
|  |- Brand
|  |- Navigation
|  `- User / Logout
|- Header / MobileHeader
`- Main
   |- AdminPageHeader
   `- PageContent
```

Permanece HTML, CSS e JavaScript vanilla. A sidebar concentra navegacao persistente em desktop; o cabecalho mobile expande ou recolhe a mesma navegacao. A area principal possui um unico ponto de contexto por pagina, titulo, descricao opcional e acao primaria opcional. A navegacao deve ser composta por botoes ou links reais, com item ativo textual e visual; cards do dashboard deixam de ser o unico meio de navegar.

## Padroes Reutilizaveis

| Componente | Valor e referencia atual | Fase | Limite |
|---|---|---|---|
| `AdminPageHeader` | Padroniza titulo, descricao e acao primaria; hoje varia por secao | J0.2 | Nao define regras de negocio ou acoes de dominio |
| `AdminFilterBar` | Unifica busca, selects, labels e limpar filtros; Producoes e Orcamentos sao referencia | J0.2 | Cada modulo conserva seu proprio estado e predicados |
| `StatusBadge` | Reutiliza `badge` com texto e semantica neutral/info/success/warning/danger | J0.2 | Mapeamento de status permanece no dominio |
| `LoadingState`, `EmptyState`, `ErrorState` | Consolida o que Producoes ja usa | J0.2 | Mensagem e acao de recuperacao sao locais |
| `AdminTable` | Densidade e cabecalho consistentes no desktop | J0.2 | Nao e renderer universal de dados |
| `MobileEntityCard` | Alternativa clara a tabela em telas pequenas | J0.2/J0.3 | Campos exibidos sao definidos pela entidade |
| `ModalFoundation` | Semantica, foco, Escape, retorno de foco e rodape; base visual ja existe | J0.2 | Conteudo e persistencia continuam em cada modal |
| `Toast` | Reaproveita notificacoes existentes para sucesso, aviso e erro | J0.2 | Nao substitui erro de campo ou confirmacao critica |

Esses componentes devem ser classes CSS, helpers DOM pequenos e convencoes de markup. Nao criar `GenericEntityManager`, renderer JSON universal ou construtor dinamico de CRUD.

## Regras de Interacao

### Page Header e List Page

Uma pagina administrativa usa `AdminPageHeader`, resumo opcional, `AdminFilterBar`, conteudo e paginacao somente quando o endpoint exigir. A acao principal aparece no cabecalho; acoes de linha mantem uma acao principal visivel e agrupam secundarias quando a densidade pedir.

### Filter Bar

Busca e filtros possuem labels acessiveis, mantem estado ao renderizar e ocupam uma linha compacta no desktop. Em telas pequenas passam para coluna. O comando `Limpar filtros` so aparece habilitado quando houver filtro ativo. Nao adicionar filtros sem decisao operacional clara.

### Tabelas e Cards Mobile

Tabelas alinham valores, datas e acoes; texto longo deve truncar visualmente apenas quando houver titulo completo disponivel. Em 320-414 px, tabelas densas viram cards: entidade principal e status no topo, metadados relevantes abaixo e uma acao clara de detalhes. Nunca comprimir colunas ate perder leitura ou alvo de toque.

### Status, Prazo e Acoes

Badges sempre trazem texto, alem de cor. A camada visual usa apenas neutral, info, success, warning e danger. Regras como prazo proximo, atrasado e status finalizado pertencem a Producoes; a fundacao recebe apenas a variante ja decidida. Exclusoes usam variante danger e confirmacao com o nome ou identificador da entidade.

### Modal, Formulario e Feedback

Modal: titulo, fechar acessivel, `role="dialog"`, `aria-modal`, foco inicial contextual, trap de foco, Escape, retorno ao gatilho, body com scroll e footer de acoes previsivel. Drawer fica adiado: sera usado apenas se um detalhe rapido precisar coexistir com a lista; nao ha caso comprovado hoje.

Formulario: label, campo, ajuda opcional, erro proximo, required sem depender de placeholder, dados preservados em falha e botao que bloqueia double-submit sem alterar o layout. Loading deve indicar atividade; empty explica ausencia; error mostra recuperacao quando possivel; toast e discreto para sucesso ou aviso. Evitar `alert()` no fluxo normal.

## Acessibilidade e Responsividade

P0: cards do dashboard sao `div` com `onclick`, portanto nao recebem foco nem acionamento por teclado; modais nao controlam foco, Escape ou semantica dialog. J0.2 corrige a fundacao; J0.3 valida a aplicacao em Producoes.

P1: navegacao sem item ativo, titulos/acoes inconsistentes, filtros sem comando de limpeza, estados compartilhados incompletos e listas sem estrategia desktop/mobile uniforme.

P2: consolidar bordas, spacing, densidade, icones, menus de acao e alinhamentos; polish music-tech, animacoes e CRO ficam para J.

Verificar estruturalmente 320, 375/390, 414, 768, 1024 e 1440 px. O foco visivel e `prefers-reduced-motion` ja existem na base e devem ser preservados. Dados de cliente, observacoes e servicos continuam renderizados como texto, nunca HTML executavel.

## Producoes como Primeira Aplicacao

**Ja esta bom:** estado modular, API separada, filtros previsiveis, loading/empty/error, ordenacao por prazo, mensagens de feedback, DOM seguro, bloco de detalhes e bloqueio de acao durante request.

**Compartilhar:** estrutura de estados, barra de filtros, badges semanticos, modal acessivel e adaptacao tabela/card.

**Permanecer no dominio:** status permitidos, calculo de progresso, parsing de etapas, prazo proximo em tres dias, prazo atrasado e regras de producao finalizada.

**J0.3:** aplicar a fundacao a Producoes sem mover essas regras: header, filtros com limpar, lista desktop/card mobile, badges, estados, modal acessivel, foco e validacao responsiva.

## Matriz de Auditoria

| Area | Estado atual | Problema | Prioridade | Fase |
|---|---|---|---|---|
| Navegacao | Dashboard por cards | `div` clicavel, sem teclado, item ativo ou shell persistente | P0 | J0.2 |
| Modais | Base visual compartilhada | Sem dialog semantics e gerenciamento de foco | P0 | J0.2 |
| Cabecalhos | Variam por secao | Titulo, retorno e acao sem padrao | P1 | J0.2 |
| Filtros | Producoes/Orcamentos funcionais | Layout, labels e limpar filtros inconsistentes | P1 | J0.2 |
| Listas | Cards simples | Sem regra para alta densidade desktop/mobile | P1 | J0.2/J0.3 |
| Producoes | Melhor referencia atual | Ainda sem fundacao responsiva e modal acessivel | P1 | J0.3 |
| Servicos | Modulos separados | Builder e lista usam convencoes visuais distintas | P2 | J |
| Orcamentos | Estrutura modular | Acoes e detalhe podem adotar a fundacao depois | P2 | J |
| Feedback | Toast existe; estados em Producoes | Estados comuns ainda nao sao uma convencao | P1 | J0.2 |
| Hierarquia | Tokens F0.4 disponiveis | CSS inline, bordas e espacamentos heterogeneos | P2 | J0.2/J |

## Escopo Recomendado

### J0.2 - Shell + Componentes Administrativos

- Implementado: shell, mobile header, navegacao acessivel, page header, filter bar, badges, estados, tabela/card e modal foundation.
- Implementado sem mover regras de dominio ou duplicar listeners/requests de inicializacao.
- Adocao completa por tela permanece incremental; Servicos, Orcamentos e Propostas nao foram redesenhados.

Arquivos centrais: `frontend/admin.html`, `frontend/css/pages/admin.css`, `frontend/css/components.css`, `frontend/js/admin/index.js`, `frontend/js/admin/ui.js`, `frontend/js/admin/admin_shell.js` e `frontend/js/admin/admin_modal.js`.

### J0.3 - Aplicacao Inicial em Producoes

- Implementado: header, filtros, resumo, lista responsiva, badges, estados e modal acessivel somente em Producoes.
- Validado: teclado, foco, Escape, retorno ao acionador, erro de API, loading e larguras de 320 a 1440 px.
- Preservados: API, state, ordenacao, regras de prazo, status, etapas e atualizacoes da F.1.

Arquivos provaveis: `frontend/js/admin/producoes/`, `frontend/admin.html` e estilos compartilhados/administrativos estritamente necessarios.

### F.3 - Dashboard Administrativo

- Implementado: resumo operacional baseado em endpoint autenticado unico, com KPIs sem valor financeiro, pipeline, atencao e atividade recente.
- O Dashboard reutiliza header, estados, badges, tokens e navegacao do shell; ele resume e direciona para modulos, sem repetir CRUD.

### F.4 - Usuarios

- Implementado: listagem responsiva, busca, filtros, modal acessivel, criacao, edicao, desativacao e redefinicao explicita de senha.
- A tela reutiliza shell, page header, filter bar, tabela/card, badges, estados, modal e feedback compartilhados; permissoes e protecoes de conta permanecem no backend.

### J Final

Polish premium, animacoes com proposito, branding avancado, CRO, menus de acao sofisticados, UX de CRM/Financeiro/IA, microinteracoes e revisao ampla dos modulos legados.
