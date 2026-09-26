# Mirai Hit Studio - UX/Polish J

## Fonte e escopo

Fonte visual: MANUAL_IDENTIDADE_MIRAI_HIT_STUDIO_2_0.docx fornecido pelo usuario.
Texto e tabelas lidos integralmente. Identidade, paleta, arquivos de imagem/logo
e direcao music-tech preservados; nenhuma arte, cliente, depoimento ou metrica
comercial foi inventada. Auditoria e evidencias: UX_AUDIT_J1.md (14 achados).
O manual orienta apresentacao, nao muda contratos comerciais.

## Entregas por subfase

| Fase | Entrega | Limite preservado |
|---|---|---|
| J.1 | Auditoria com severidade, confianca e evidencia | Sem alegar dados de CRO inexistentes |
| J.2 | Marca/oferta literal, heroes mais curtos, CTA redundante removido | Ofertas, valores, briefing e eventos intactos |
| J.3 | Entrada/saldo explicados, Pix com validade local, cartao em linguagem direta | Backend/Brick/3DS mantem autoridade |
| J.4 | Contraste danger/logout, superficies discretas, atencao antes do pipeline | Sem mudar CRUD, filtros ou regras de prazo |
| J.5 | Rascunho explicitamente nao enviado, ajuda no composer, metricas sem codigos brutos | Handoff, tools, permissao e envio humano preservados |
| J.6 | Tokens/fontes/raios/botoes, menos glow, portfolio compacto, formulario antes do contexto mobile | Sem redesign estrutural, SEO ou backend |

Capas de portfolio respeitam proporcao responsiva, sem impor os 400px do atributo HTML.
Copy de portfolio deixa de falar em "prova inventada" e passa a apresentar
materiais; rotulos Demo/Concept/Study/Case continuam no renderer. Dados de teste
sao sinteticos e nao foram adicionados ao catalogo real.

## Padroes visuais

- Fundo oficial #111827; ciano e roxo preservados. Superficies distintas e erro
  mais claro permitem contraste sem molduras neon.
- Oxanium em titulos/CTA, Rajdhani em subtitulos/valores, Calibri com fallback.
  Ethnocentric reservado a identidade. Nenhuma fonte proprietaria nova incluida.
- Escala fixa por breakpoint, sem vw na escala compartilhada; espacos existentes.
- Primario ciano/escuro, secundario neutro, perigo com texto/borda contrastantes.
- Cards de conteudo permanecem; secoes Dashboard nao ficam em cards externos.
- Sem salto de superficie no hover; reduced motion preservado.
- Preferencias de privacidade apos conteudo, sem sobrepor Pix. Launcher de chat
  opaco, secundario, reposicionado acima do banner quando este estiver aberto.
- Nenhuma dependencia nova ou renderizacao de dados via innerHTML adicionada.

## Validacao

Testes Playwright existentes com interceptacao completa da rede e dados sinteticos:
public_accessibility, public_navigation, home_artists, creators, media_games,
portfolio_public, public_contracting, analytics, newsletter_public, checkout,
admin_foundation, flows, security, dashboard, producoes, clientes,
financeiro_admin, usuarios, newsletter_admin, auditoria, proposta_editor,
proposta_documento, proposta_comercial, ai_chat, ai_inbox; contrato Node
proposta_contracts.mjs. Todos aprovados na regressao local.

- 9 larguras publicas: 320/360/375/390/414/768/1024/1280/1440.
- Admin/Inbox com tabela/card/menu mobile; chat inclui viewport de 390x400.
- Teclado, foco, modal, Escape, landmarks, labels, headings, reduced motion,
  overflow e contraste do rodape verificados; nao equivale a certificacao WCAG.
- Novas assercoes: botao danger legivel e 44px, privacidade nao fixa, formulario
  antes do contexto, continuidade do hero, ordem real do Dashboard,
  rascunho/descricao acessivel, erro tecnico omitido e validade Pix formatada.
- Capturas temporarias em %TEMP%: mirai-j-* (Home, verticais, portfolio,
  orcamento, checkout, Admin); mirai-chat-*; mirai-ai-metrics-*.
- Inspecao visual representativa desktop/mobile; capturas nao versionadas.
- Teste de documento exigiu fixture ausente: gerada por
  test_proposta_documento.DocumentoTests.test_layout_cases, SQLite descartavel,
  rede proibida pelo harness. Teste backend passou, sem alteracao de codigo.
- Falhas encontradas: seletor de captura ambiguo na Inbox e renderer Dashboard
  recriando ordem anterior. Ambos corrigidos com regressao especifica.
- Alembic continua com uma head f2a8c4e6d901; nenhuma migration/backend alterado.

## Limites e proximas fases

Nao se mediu uplift de conversao. Arte existente nao substitui provas reais
autorizadas. Testes usam Edge headless, nao aparelhos fisicos, leitor de tela
real, gateway real nem producao. H cuida de SEO/CWV/assets; I valida infraestrutura,
PostgreSQL, integracoes e release. Nenhuma dessas fases foi iniciada.

Aviso Node MODULE_TYPELESS_PACKAGE_JSON no teste de contratos e preexistente;
nao se alterou package.json externo ao repositorio para silencia-lo.

## Git e Lean Dev

Commits separados J.1-J.6, push somente apos regressao CP-J. O relatorio final
confirma hashes remoto/local. ROADMAP fica pronto/pendente ate a confirmacao real,
sem commit artificial apenas para trocar esse texto.

Preservados fora dos commits: mudanca preexistente do href CSS de index.html e
backend/tests/test_phase1a.py. Staging parcial usado em index.html.
Leituras localizadas por subfase: identidade/docs/CSS em J.1; paginas/testes em
J.2; checkout em J.3; foundation/Dashboard em J.4; chat/Inbox em J.5; tokens e
evidencia transversal em J.6. Sem auditoria ampla do backend ou nova dependencia.
Nao ha contador cumulativo confiavel de linhas/tokens lidos apos compactacao;
nao foram inventados numeros de economia.
