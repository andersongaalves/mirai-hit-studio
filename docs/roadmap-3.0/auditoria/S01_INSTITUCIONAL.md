# Auditoria setorial - S01 Institucional

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Suites `seo_technical`, `seo_content_h2`, `public_navigation`, `home_artists`, `home_mix_comparison`, `portfolio_public`, `creators`, `media_games`, `newsletter_public`, `analytics` verdes; `public_accessibility` falha (001); `performance_h3` depende de recurso externo |

## 2. Inventario

Paginas publicas: home, artists, creators, media-games, portfolio, calculadora, checkout,
404 e telas de acesso. Consentimento de analytics, newsletter, chat do site, comparacao A/B.

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S01-001 | P2 | 4.4 / 4.5 (conformidade) | Nao existe pagina de Politica de Privacidade, embora o site colete dados (orcamento, cadastro, newsletter, chat, analytics); o rodape "Privacidade" das telas de acesso e texto sem link | Aberto |
| AUD6-S01-002 | P3 | 4.9 | `/portfolio`: links "artistas", "criadores" e "midia e games" abaixo do tamanho minimo de alvo (falha em `public_accessibility.cjs`) | Aberto |
| AUD6-S01-003 | P3 | 4.12 / S12 | `public_accessibility.cjs` e as suites de SEO/navegacao nao rodam no CI, por isso a regressao 002 passou despercebida | Aberto |

### AUD6-S01-001 - Politica de privacidade (P2)

- Evidencia: nenhum HTML ou script referencia uma politica; as 16 paginas nao incluem uma
  pagina de privacidade; o banner de analytics e os formularios nao apontam para regras de
  tratamento.
- Impacto: obrigacao de transparencia da LGPD (finalidade, base legal, contato,
  direitos do titular); risco reputacional e juridico.
- Recomendacao: pagina `/privacidade` (texto revisado pelo responsavel/juridico) e links
  no rodape, no consentimento, no cadastro, no orcamento e na newsletter.
- Dependencia: **decisao** sobre o conteudo (nao gerar texto juridico sem revisao).

### P3

- **002**: aumentar a area clicavel (padding minimo de 24 px).
- **003**: ver S12.

## 5-13. Resumo

- Candidatas: busca/filtros do portfolio; CTA contextual; ajuda para iniciar projeto.
- Dependencias: S11 (consentimento/chat), S12 (CI).
- Validacao: 001 publicado com links; `public_accessibility.cjs` verde e no CI.
