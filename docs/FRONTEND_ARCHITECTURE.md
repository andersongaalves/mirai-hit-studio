# Arquitetura do frontend

Estado da refatoração local em `fix/client-portal-visual` (12/10/2026). O frontend é
HTML estático servido por Cloudflare Pages, com CSS nativo e módulos JavaScript sem
build ou framework. `frontend/_redirects` mantém as rotas dos portais e do
orçamento; `functions/checkout/[[path]].js` serve o checkout por referência. O
JavaScript público injeta `components/nav.html` e `components/footer.html` e adapta
alguns links para a prévia local. Os portais e o admin montam conteúdo e estados
dinamicamente; classes como `.hidden`, `.is-active`, `.is-open` e atributos ARIA
são contratos também usados pelo CSS.

## Diagnóstico e decisões

Antes, `css/main.css` importava o layout e os estilos públicos em **todas** as
páginas. `css/integrado.css` reunia 1.250 linhas de fundação, site, autenticação,
checkout e três áreas operacionais, com media queries agrupadas no fim. A ordem
dos links escondia dependências de cascata. O cliente e as cinco telas de acesso
carregavam `css/pages/produtor.css`, inclusive regras de repasse específicas do
produtor. `docs/DESIGN_SYSTEM.md` já definia `variables.css` como origem dos
tokens; as oito cores de `--integrado-*` ainda estavam repetidas em outro `:root`.

A separação preserva os seletores e a lógica JavaScript existentes. O CSS de
base continua em `main.css` (`variables.css`, `base.css`, `components.css`,
`notifications.css`, `consent.css`). Apenas páginas públicas carregam
`layout.css` e `pages/public.css`. `integrado.css` contém só a fundação visual,
foco, controles e movimento reduzido. Cada página carrega sua camada integrada
específica após seu CSS existente. Os valores `--integrado-*` são aliases de
compatibilidade em `variables.css`; a fonte externa Oxanium/Rajdhani é carregada
uma vez por `main.css`, e Ethnocentric tem uma única declaração `@font-face` em
`variables.css`. Calibri continua como fonte de texto com fallback Arial.

`components/portal-entry.css` reúne a entrada/autenticação usada nas telas de
acesso e nos dois portais. `layouts/portal-base.css` reúne shell, sidebar,
navegação, conteúdo, cards, arquivos e estados compartilhados pelo cliente e
produtor. `pages/cliente.css` mantém regras do cliente e `pages/produtor.css`
agora contém apenas o repasse do produtor. `layouts/integrado-portal.css`
preserva a camada visual comum e responsiva dos dois portais. O admin usa outra
estrutura e permissões; compartilha tokens, altura do cabeçalho e largura da
sidebar, mas conserva seu shell em `pages/admin.css` e
`pages/integrado-admin.css`. Não foi introduzido um template ou framework para
estruturas que não têm o mesmo contrato de conteúdo.

Nos módulos integrados, 23 raios literais de 4px, sete usos de `#071018`, dois
de `#62e5ff` e quatro de `#eaf2ff` passaram a referenciar tokens existentes ou
novos, sem mudar seus valores calculados. Nenhuma regra foi removida por mera
ausência de correspondência textual: seletores podem ser usados após renderização
de JavaScript ou por estado. As classes `producer-*` continuam como API de
compatibilidade dos dois portais; renomeá-las exigiria modificar HTML, JS e
testes sem ganho funcional comprovado nesta refatoração.

## Inventário HTML e rotas

| HTML | Estado | Papel e rota |
| --- | --- | --- |
| `index.html` | Ativo | Home `/`; entrada pública. |
| `artists.html` | Ativo | Vertical `/artists`. |
| `creators.html` | Ativo | Vertical `/creators`. |
| `media-games.html` | Ativo | Vertical `/media-games`. |
| `portfolio.html` | Ativo | Portfólio `/portfolio`, conteúdo obtido pela API. |
| `calculadora.html` | Ativo | Orçamento `/orcamento`, rewrite em `_redirects`. |
| `checkout.html` | Ativo | `/checkout` e `/checkout/:referencia` via Pages Function; preço e pagamento dependem do backend. |
| `acesso.html` | Ativo | `/acesso`, login e redirecionamento por papel. |
| `cadastro.html` | Ativo | `/cadastro`, convite/cadastro do cliente. |
| `ativar.html` | Ativo | `/ativar`, ativação por token. |
| `recuperar-senha.html` | Ativo | `/recuperar-senha`, solicitação de recuperação. |
| `redefinir-senha.html` | Ativo | `/redefinir-senha`, redefinição por token. |
| `portal-cliente.html` | Ativo | `/cliente/*` via `_redirects`; rotas e vistas internas no módulo `js/cliente/index.js`. |
| `portal-produtor.html` | Ativo | `/produtor/*` via `_redirects`; rotas e vistas internas no módulo `js/produtor/index.js`. |
| `admin.html` | Ativo | `/admin`, dashboard e módulos administrativos no shell. |
| `404.html` | Ativo | Página de erro padrão do Pages. |
| `components/nav.html` | Compartilhado | Fragmento injetado por `js/modules/components.js` nas páginas públicas. |
| `components/footer.html` | Compartilhado | Fragmento injetado pelo mesmo módulo. |

Nenhum HTML foi classificado como legado ou órfão confirmado. Não foram removidos
HTML, rotas nem arquivos de recursos. Uma ausência de link estático não prova
desuso: Pages, links externos e navegação em JavaScript também são entradas.

## Mapa de dependências de estilos

Em todas as linhas abaixo, `main.css` é carregado primeiro. A ordem indicada
depois dele é a ordem efetiva dos links. O CSS integrado de página continua após
o CSS de página anterior, mantendo a precedência visual.

| Páginas | CSS adicional após `main.css` | JavaScript de entrada |
| --- | --- | --- |
| `404` | `layout.css` → `pages/public.css` | Nenhum. |
| Home | `layout.css` → `pages/public.css` → `pages/home.css` → `pages/mix-comparison.css` → `integrado.css` → `layouts/integrado-public.css` → `pages/integrado-home.css` | `js/main.js` (módulos por rota). |
| Artists, Creators, Media & Games | `layout.css` → `pages/public.css` → `pages/verticals.css` → `integrado.css` → `layouts/integrado-public.css` → `pages/integrado-verticals.css` | `js/main.js`. |
| Portfólio | `layout.css` → `pages/public.css` → `pages/portfolio.css` → `integrado.css` → `layouts/integrado-public.css` → `pages/integrado-portfolio.css` | `js/main.js` → módulo de portfólio. |
| Orçamento | `layout.css` → `pages/public.css` → `pages/calculator.css` → `integrado.css` → `layouts/integrado-public.css` → `pages/integrado-quote.css` | `js/main.js` → módulo de orçamento. |
| Checkout | `layout.css` → `pages/public.css` → `pages/checkout.css` → `integrado.css` → `layouts/integrado-public.css` → `pages/integrado-checkout.css` | `js/checkout.js`. |
| Acesso, cadastro, ativação e recuperação | `components/portal-entry.css` → `integrado.css` → `pages/integrado-auth.css` | Módulo da página; `integrado_auth.js` quando referenciado. |
| Cliente | `components/portal-entry.css` → `layouts/portal-base.css` → `pages/cliente.css` → `integrado.css` → `layouts/integrado-portal.css` | `js/cliente/index.js` e `js/integrado_portal.js`. |
| Produtor | `components/portal-entry.css` → `layouts/portal-base.css` → `pages/produtor.css` → `integrado.css` → `layouts/integrado-portal.css` | `js/produtor/index.js` e `js/integrado_portal.js`. |
| Admin | `pages/admin.css` → `integrado.css` → `pages/integrado-admin.css` | `js/admin/index.js` e `js/integrado_admin.js`. |

`layout.css` e `pages/public.css` deixaram de chegar às telas internas. A
camada integrada de uma página também não é carregada pelas outras. O CSS
compartilhado dos portais controla grid, rail, header, estado ativo e menu
responsivo; cada portal fornece sua navegação, conteúdo, permissões e estado.

## Verificação e limites

- `frontend/tests/style_architecture.cjs`: 16 HTML de entrada, 31 módulos CSS,
  110 referências HTML e 322 imports/recursos JavaScript locais resolvidos.
- Comparação com `HEAD` anterior: 80 combinações de página e largura (1440,
  1366, 1024, 768 e 390px) sem diferença nas propriedades calculadas; 18 pares
  de capturas do viewport em 1440/390px idênticos. Esta comparação usa HTML
  estático sem JavaScript e bloqueia a fonte externa nos dois lados; não é prova
  visual das vistas autenticadas preenchidas por API.
- Testes de navegador com mocks: navegação pública, Home/Artists, portfólio,
  cliente, produtor, admin, checkout e acesso do cliente passaram. Interações,
  classes dinâmicas e layout responsivo dessas jornadas foram exercitados.
- ESLint de `frontend/js`: zero erros, 11 avisos preexistentes. A configuração
  passou a reconhecer APIs padrão do navegador antes tratadas como indefinidas.
- Não há etapa de build do frontend neste repositório; arquivos estáticos são
  publicados diretamente. Não foi feita validação contra backend ou produção.

`admin.css` e `home.css` continuam grandes, mas concentram regras próprias de
suas páginas. A navegação/consentimento ainda usam classes genéricas
compatíveis com o HTML atual; futuras renomeações devem começar por um conflito
real e atualizar consumidores dinâmicos. O teste de performance local apontou
CLS em uma amostra do portfólio desktop, mas esta refatoração manteve as
capturas e os estilos iniciais idênticos ao `HEAD` anterior; investigar o fluxo
dinâmico separadamente antes de atribuir causa a esta mudança.
