# Mirai Hit Studio - Performance H.3

## Metodologia

A medicao usa `frontend/tests/performance_h3.cjs`, servidor HTTP local sem cache e Edge headless. Cada pagina foi executada tres vezes por perfil; os valores abaixo sao medianas, nao a melhor execucao.

- Mobile: 390x844, CPU 4x, 1,6 Mbps down, 750 Kbps up e 150 ms de latencia.
- Desktop: 1440x900, CPU 1x, 10 Mbps down, 5 Mbps up e 20 ms de latencia.
- Paginas: Home, Artists, Creators, Media & Games, Portfolio, Orcamento e Checkout.
- APIs comerciais foram substituidas por respostas sinteticas; nenhum banco, pagamento ou provider real foi usado.
- Consentimento de analytics permaneceu recusado durante a medicao.

Foram coletados LCP, CLS, FCP, long tasks/TBT proxy, requests, bytes transferidos e duracao de script/task/layout. Lighthouse nao esta instalado no ambiente; Speed Index, INP real e dados de campo nao foram medidos. Resultados locais nao substituem CrUX, Search Console, aparelhos reais ou serving de producao.

## Baseline mobile

| Pagina | LCP | FCP | CLS | TBT proxy | Requests | Transferencia |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Home | 2464 ms | 1732 ms | 0,10 | 28 ms | 39 | 441 KB |
| Artists | 1704 ms | 1704 ms | 0,10 | 0 ms | 37 | 306 KB |
| Creators | 1724 ms | 1724 ms | 0,10 | 0 ms | 37 | 314 KB |
| Media & Games | 2416 ms | 1716 ms | 0,10 | 0 ms | 37 | 439 KB |
| Portfolio | 3300 ms | 1280 ms | 0,10 | 0 ms | 41 | 464 KB |
| Orcamento | 1776 ms | 1360 ms | 0,10 | 0 ms | 41 | 232 KB |
| Checkout | 2364 ms | 1472 ms | 0 | 10 ms | 20 | 361 KB |

No desktop, o favicon de 744 KB elevava a transferencia total para aproximadamente 1,0-1,2 MB em todas as paginas. O checkout ainda carregava uma logo de 237 KB.

## Gargalos encontrados

- P1: `favicon.png` tinha 702x702 e 744 KB, apesar de ser declarado como 64x64.
- P1: CSS de Admin, Calculadora, Portfolio e Chat era importado globalmente.
- P1: o hero do Portfolio era o LCP real, mas nao possuia preload; LCP mobile mediano de 3,30 s.
- P1: o placeholder da navegacao nao reservava altura; a injecao assincrona deslocava o `main` e gerava CLS de 0,10.
- P1: logo do Checkout tinha 953x250 e 237 KB para exibicao maxima de 230 px.
- P2: Chat completo, incluindo CSS e tres modulos, era baixado no carregamento mesmo sem interacao.
- P2: audio direto do Portfolio solicitava metadata antes de intencao de reproducao.
- P2: Google Fonts era descoberto dentro de `variables.css`, um nivel depois do CSS principal.
- P3: Ethnocentric local permanece em TTF de 63 KB; conversao/self-hosting adicional foi adiada por exigir pipeline e validacao de fonte.

## LCP e CLS reais

O LCP das paginas Home, Artists, Creators e Media & Games e o background WebP do hero. No Portfolio, e o background do header. No Orcamento, e texto do formulario; no Checkout mobile, a logo.

O CLS de 0,10 nas paginas publicas vinha principalmente da navegacao injetada sem espaco reservado. A reserva de 69 px eliminou o shift mediano nas cinco paginas editoriais. Orcamento permanece em 0,10 por insercao dos servicos retornados pela API; nao foi criada uma altura ficticia para um catalogo de tamanho variavel. Checkout permaneceu em 0.

## Mudancas realizadas

- CSS de Admin, Calculadora e Portfolio passou a ser ligado apenas nas paginas correspondentes.
- CSS do Chat e modulos completos carregam somente depois do clique no launcher leve.
- Launcher continua imediato, acessivel e posicionado em relacao ao consentimento.
- Hero do Portfolio recebeu preload/fetchpriority, pois foi confirmado como LCP.
- Placeholder da navegacao publica passou a reservar altura.
- `font-display: swap` foi aplicado a Ethnocentric; Google Fonts foi antecipado um nivel na cadeia CSS.
- Favicon foi redimensionado para 64x64: 744 KB para 8,9 KB.
- Logo do Checkout foi redimensionada para 460x121: 237 KB para 64 KB, preservando 2x do tamanho visual.
- Audio direto do Portfolio passou de `preload="metadata"` para `preload="none"`.
- MercadoPago.js continuou restrito ao Checkout e somente e solicitado quando o usuario escolhe cartao.

## Resultado mobile

| Pagina | LCP antes | LCP depois | FCP antes | FCP depois | CLS depois | Requests depois | Transferencia depois |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Home | 2464 ms | 2112 ms | 1732 ms | 1072 ms | 0 | 34 | 387 KB |
| Artists | 1704 ms | 1144 ms | 1704 ms | 1088 ms | 0 | 32 | 252 KB |
| Creators | 1724 ms | 1176 ms | 1724 ms | 1068 ms | 0 | 32 | 260 KB |
| Media & Games | 2416 ms | 2120 ms | 1716 ms | 1088 ms | 0 | 32 | 385 KB |
| Portfolio | 3300 ms | 2136 ms | 1280 ms | 1016 ms | 0 | 37 | 414 KB |
| Orcamento | 1776 ms | 992 ms | 1360 ms | 992 ms | 0,10 | 37 | 187 KB |
| Checkout | 2364 ms | 1200 ms | 1472 ms | 988 ms | 0 | 17 | 146 KB |

No desktop, Home caiu de 1,186 MB para 387 KB e Checkout de 1,105 MB para 146 KB, principalmente pela correcao dos PNGs. Portfolio caiu de 3,30 s para 2,14 s no LCP mobile por antecipar o recurso realmente responsavel. O JS inicial da Home caiu de aproximadamente 59 KB para 47 KB porque o Chat completo saiu do caminho inicial.

TBT proxy permaneceu em 0 na maioria das paginas. Home variou de 28 para 27 ms. Checkout variou de 10 para 53 ms, ainda baixo; nao ha evidencia de tarefa longa sistemica e a variacao nao foi ocultada. INP exige interacoes e dados de campo, portanto nao foi inferido do TBT.

## Revisao por area

- Imagens: heroes existentes em WebP foram preservados; capas do Portfolio ja possuem dimensoes, lazy loading e decoding async.
- Fontes: identidade preservada; swap reduz bloqueio visual. O TTF local ainda e um candidato futuro.
- CSS: imports de dominio deixaram o caminho global; nao foi criado critical CSS ou bundler.
- JS: inicializacao por presenca de componente foi preservada; Chat completo ficou lazy por intencao.
- Portfolio: capa lazy, audio sem preload e hero priorizado. Nenhum audio completo e pre-carregado.
- Chat: nenhuma API, historico ou polling ocorre antes de abrir; polling humano continua apenas com dialog aberto e pagina visivel.
- Checkout: logo otimizada; SDK do Mercado Pago permanece carregado apenas ao escolher cartao. Pix, cartao, 3DS e polling nao tiveram regra alterada.
- Third-party: GA4 continua condicionado ao consentimento; Mercado Pago continua por intencao; Google Fonts permanece a unica dependencia visual externa no caminho inicial.
- Analytics: comportamento e privacidade nao foram alterados.

## Protecoes e regressao

O teste de performance rejeita CSS administrativo em paginas publicas, CSS de pagina fora do contexto, Chat completo antes de intencao, Mercado Pago pre-carregado e regressao grosseira no peso dos dois PNGs. Testes funcionais cobrem SEO, navegacao, responsividade, acessibilidade, Portfolio, Orcamento, Checkout, analytics/consentimento e Chat.

## Adiado

I.4 deve validar cache, Brotli/Gzip, headers, HTTP/2/3, redirect `www`, fontes em producao e eventual WOFF2. I.5 deve repetir Lighthouse/DevTools em deploy, conferir CrUX/Search Console quando houver dados, testar aparelhos reais, rede real, screenshots e fluxos integrados. Nenhuma migration ou mudanca de backend foi criada em H.3.
