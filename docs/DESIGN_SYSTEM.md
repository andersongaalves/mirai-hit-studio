# Mirai Hit Studio - Design System

## Principios

- Clareza antes de efeito; identidade antes de decoracao.
- Music-tech premium: audio, estudio, waveform e tecnologia musical sao referencias primarias.
- Futurista sem sacrificar legibilidade, contraste ou foco.
- Referencias japonesas/geek sao assinatura secundaria, nao tema dominante.
- Mobile-first, acessibilidade e consistencia entre site, admin e IA.
- G cria as paginas; J faz o refinamento premium, CRO e microinteracoes.

## Tokens

Os tokens vivem em `frontend/css/variables.css`. As variaveis `--cor-*` existentes continuam compativeis; modulos novos devem preferir os aliases semanticos.

| Papel | Token | Valor/base |
|---|---|---|
| Fundo | `--color-background` | `#0b0f19` |
| Superficie | `--color-surface` | azul-escuro translucido |
| Superficie elevada | `--color-surface-elevated` | `#111827` |
| Destaque | `--color-accent` | `#00D4FF` |
| Destaque secundario | `--color-accent-secondary` | `#B22AF0` |
| Texto principal | `--color-text-primary` | `#F9FAFB` |
| Texto secundario | `--color-text-secondary` | `#AAB3C2` |
| Bordas | `--color-border` | branco sutil |
| Estado | `--color-success`, `--color-warning`, `--color-danger` | semanticos |

Nao introduzir hex novo em componente sem antes avaliar se ele representa um token reutilizavel.

## Tipografia e espacamento

- Logo/identidade: Ethnocentric quando aplicavel.
- Titulos e CTA: Oxanium.
- Subtitulos, valores e badges: Rajdhani.
- Texto corrido: Calibri ou fonte compativel ja definida.
- Usar `--font-size-display`, `--font-size-h1`, `--font-size-h2`, `--font-size-h3`, `--font-size-body`, `--font-size-small` e `--font-size-caption` para novos modulos.
- Usar `--space-1`, `--space-2`, `--space-3`, `--space-4`, `--space-5`, `--space-6`, `--space-8` e `--space-10` em vez de espacamentos arbitrarios.

Escala visual: display para hero real; h1 para pagina; h2 para secao; h3 para painel. Evitar letter-spacing negativo e texto apertado.

## Superficies e componentes

| Elemento | Regra |
|---|---|
| Botao primary | `.btn-cta`; ciano/roxo reservado para acao principal |
| Botao secondary | `.btn-outline`; sem competir visualmente com primary |
| Botao ghost | `.btn-small`; acao secundaria ou contextual |
| Perigo | `.btn-small.btn-danger`; apenas acao destrutiva |
| Card novo | `.card`; card legado continua `.glass-card` |
| Campos novos | `.input`, `.textarea`, `.select`; formularios existentes permanecem compativeis |
| Status | `.badge` e variantes `-success`, `-warning`, `-danger` |
| Container e secao | `.container` e secoes sem card externo decorativo |

Usar `--radius-sm`, `--radius-md` e `--radius-lg`; `--border-subtle` para estrutura e `--border-accent` para estado relevante. `--shadow-glow` e reservado a foco, CTA e elementos especiais; nao aplicar glow a todos os cards.

Modal e toast devem herdar superficie elevada, borda sutil, foco visivel e estado de carregamento sem deslocar o layout. Nao criar componentes abstratos sem uma tela real que os use.

## Interacao e movimento

- Todo elemento interativo precisa de hover, `:focus-visible`, active e disabled coerentes.
- Nunca remover outline sem substituto acessivel.
- Loading preserva dimensoes e bloqueia double-submit quando aplicavel.
- Animacoes funcionais: feedback, expansao e transicao de estado.
- Animacoes decorativas: discretas e nao continuas quando nao agregarem contexto.
- `prefers-reduced-motion` reduz animacoes e transicoes globalmente.

## Responsividade

Faixas de referencia: 320, 375, 390/414, 768, 1024 e 1440 px. Reutilizar breakpoints locais existentes: mobile ate 520/768 px, tablet ate 900 px e desktop acima disso. Nao criar um breakpoint novo por componente sem necessidade real.

Em mobile: comandos e textos nao podem truncar, grids devem cair para uma coluna quando necessario e controles de toque devem manter area confortavel. O primeiro viewport deve priorizar o trabalho ou conteudo real, nao decoracao.

## Direcao para G e J

G deve usar a fundacao para paginas de vertical e portfolio: espaco negativo, hierarquia sonora, midia real e CTA claro. J podera revisar composicao, hierarquia final, CRO e microinteracoes depois que as jornadas existirem. Evitar agora neon dominante, glitch continuo, iconografia gamer generica e efeitos que ocultem conteudo.
