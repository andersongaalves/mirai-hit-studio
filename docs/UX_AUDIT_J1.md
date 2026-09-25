# Mirai Hit Studio - Auditoria J.1

## Base e limites

Referencia: MANUAL_IDENTIDADE_MIRAI_HIT_STUDIO_2_0.docx, fornecido pelo responsavel.
Leitura integral do texto OOXML, incluindo tabelas. O manual e referencia de marca,
nao autorizacao para alterar regras comerciais. Evidencia: CSS/DOM atuais, jornadas
dos testes Playwright existentes e captura sintetica da Home em desktop/mobile.
Nao houve acesso a clientes, pagamentos ou analytics reais. Impactos de conversao
sao hipoteses; nao se afirma aumento de conversao sem medicao posterior.

## Identidade extraida

- Music-tech contemporanea, premium, precisa e proxima; origem geek secundaria.
- Paleta preservada: #111827, #00D4FF, #B22AF0, #F9FAFB.
- Ethnocentric somente na identidade; Oxanium em titulos/CTA; Rajdhani em
  subtitulos/valores; Calibri com fallback sans-serif em texto.
- Imagens de estudio, DAW e audio existentes permanecem; nenhuma prova inventada.
- Slogan: Criando o som do futuro. Descritor: producao musical e audio para
  artistas, criadores e projetos digitais.
- Menos neon/glitch gratuito, mais hierarquia, respiro e luz controlada.
- Os pesos de cores do manual orientam a composicao, nao uma cota literal de
  pixels: texto legivel e cores semanticas de erro/sucesso continuam necessarios.
- Divergencia: fundo legado #0b0f19 versus #111827 oficial. J.6 alinha o token,
  preservando aliases e sem alterar logotipo. Sem substituicao de identidade.

## Backlog executavel

| ID | Severidade | Confianca | Evidencia / area | Impacto e recomendacao | Fase |
|---|---|---|---|---|---|
| J01 | S2 | Alta | index.html: h1 abstrato e marca apenas no eyebrow; captura home-g2 | Tornar marca e oferta literais no primeiro viewport, manter CTA principal | J.2 |
| J02 | S2 | Alta | public.css: min-height 600/620/680px em mobile | Hero pode ocupar toda tela; ajustar altura e espacamento para revelar continuidade | J.2 |
| J03 | S2 | Alta | checkout.html: legend Pagamento comercial; explicacao de tokenizacao | Termos internos dificultam escolha; texto claro sobre valor atual, cartao e confirmacao | J.3 |
| J04 | S2 | Alta | checkout.js: expiration_time inserido sem formatacao | Data tecnica reduz compreensao; formatar data/hora e lidar com valor invalido | J.3 |
| J05 | S2 | Alta | admin.css: moldura roxa/glow, dashboard-section enquadrada | Ruido em operacao; retirar moldura decorativa e separar secoes sem cards externos | J.4 |
| J06 | S1 | Alta | components.css define texto vermelho em btn-small.btn-danger; admin.css define fundo vermelho | Captura confirma texto invisivel no logout; corrigir variantes e tornar sair secundario | J.4 |
| J07 | S2 | Alta | inbox_dom.js: sugestao aparece no historico e preenche composer | Reforcar que e rascunho nao enviado, editavel antes do envio humano | J.5 |
| J08 | S2 | Alta | inbox_metrics.js: nomes/resultados/error_code expostos diretamente | Usar rotulos operacionais, sem codigo tecnico bruto ou falsa taxa de resolucao | J.5 |
| J09 | S2 | Media | chat.css: cabecalho, aviso longo e acoes disputam altura | Compactar copy e validar composer em viewport baixo; distinguir humano de IA | J.5 |
| J10 | S2 | Alta | base.css: h2/h3 decorados globalmente; components.css glass-card salta 15px | Remover ornamento global e movimento de superficies nao interativas | J.6 |
| J11 | S3 | Alta | variables.css: escala com vw, fonte logo Impact, cores dispersas | Consolidar tokens e escala fixa responsiva; identidade usa arquivo de logo existente | J.6 |

Contagem: S0=0, S1=1, S2=9, S3=1. Ausencia de S0 nesta amostra nao certifica
ausencia de problemas em producao. Screenshots temporarios nao entram no Git.

## Preservar

- Verticais ja possuem ofertas e copy distintas; nenhuma nova oferta/preco.
- Portfolio rotula demos/cases e possui filtros/player; sem depoimentos ficticios.
- Contratacao mantem descricao/opcoes, validacao, retry e conversao apos API.
- Checkout usa backend, Brick, Pix e 3DS reais; nenhum estado pago local.
- Dashboard/CRM/Producoes/Financeiro/Usuarios/Newsletter usam dominio existente.
- Inbox/handoff/briefing/metricas preservam F2; nenhuma nova tool/provider.
- Navegacao, focus trap, consentimento e tratamento seguro de texto permanecem.

## Validacao e sequencia

Executar J.2, J.3, J.4, J.5, J.6 com commits separados e testes focados.
CP-J exige regressao frontend transversal, matriz 320-1440, capturas temporarias,
teclado/foco/reduced motion e revisao de diff. Nao altera backend/migrations.
H fica com SEO/performance; I com QA de infraestrutura, PostgreSQL e release.
