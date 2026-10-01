# Mirai Hit Studio - Roadmap

## Status

Fase atual: I.4 parcialmente concluida; deploy controlado e smokes publicos aprovados,
com gates externos de infraestrutura pendentes.

Ultimo checkpoint enviado: CP-H.

Checkpoint atual: bloco I em andamento.

Proximo checkpoint: definido pelo bloco I apos conclusao dos gates de release.

Proximo push: somente apos a proxima entrega versionada do bloco I.

Ultimo deploy auditado: `b44f3d6` (`chore: prepara infraestrutura de producao`).

## Concluido

- A: backend persistente de propostas.
- B: editor real de propostas.
- C: HTML/PDF/QR/documento.
- D: envio/aprovacao/producao.
- E: seguranca.

## Planejado

F0 - Fundacao Mirai 2.0

- F0.0 Contexto Codex, roadmap e decisoes.
- F0.1 Posicionamento, publicos e ofertas. Concluida.
- F0.2 Taxonomia comercial e impacto tecnico/CRM. Concluida.
- F0.3 Analytics, funil e consentimento. Concluida.
- F0.4 Design system minimo e plano de provas sociais. Concluida.
- CP-F0 enviado.

F - Admin/CRM

- F.1 Producoes. Concluida.
- F.2 Clientes/CRM. Concluida.
- F.3 Dashboard. Concluida.
- CP-F1 enviado.
- F.4 Usuarios. Concluida.
- F.5 Newsletter e comunicacao. Concluida.
- F.6 Logs, auditoria e backup/restore. Concluida.
- CP-F2 enviado.

J0 - Fundacao UX do Admin

- J0.1 Auditoria UX e especificacao de padroes reutilizaveis. Concluida.
- J0.2 Shell e componentes administrativos. Concluida.
- J0.3 Aplicacao inicial da fundacao em Producoes. Concluida.
- J0 concluida.

F3 - Pagamentos/Financeiro

- F3.1 Modelo financeiro. Concluida.
- F3.2 Mercado Pago backend. Concluida.
- F3.3 Webhooks, idempotencia e reconciliacao. Concluida.
- F3.4 Checkout. Concluida.
- F3.5 Financeiro admin. Concluida.
- CP-PAG enviado.

G - Site publico

- G.0 Provas sociais. Concluida.
- G.1 Arquitetura publica. Concluida.
- G.2 Home e Artists. Concluida.
- CP-G1 enviado.
- G.3 Creators. Concluida.
- G.4 Media & Games. Concluida.
- G.5 Portfolio/cases. Concluida.
- G.6 Orcamento/contratacao. Concluida.
- G.7 Acessibilidade/responsividade. Concluida.
- CP-G2 enviado.

F2 - IA

- F2.1 Auditoria e adaptacao do agente Dark District. Concluida.
- F2.2 Core de IA independente de canal. Concluida.
- F2.3 Knowledge/tools. Concluida.
- CP-IA1 enviado.
- F2.4 Chat do site. Concluida.
- F2.5 E-mail. Concluida.
- CP-IA2 enviado.
- F2.6 Inbox/copiloto. Concluida.
- F2.7 Briefing/CRM. Concluida.
- F2.8 Guardrails/custos/evals/metricas. Concluida.
- F2 concluida; limites operacionais e de avaliacao em AI_GUARDRAILS_EVALS_METRICS.md.
- CP-IA3 enviado em `972049f`.

J - UX/CRO

- J.1 Auditoria UX e identidade. Concluida.
- J.2 Experiencia e conversao publica. Concluida.
- J.3 Checkout. Concluida.
- J.4 Admin. Concluida.
- J.5 IA/Inbox. Concluida.
- J.6 Polish transversal. Concluida.
- CP-J pronto para regressao final e push; resultados em UX_POLISH_J.md.

H - SEO/performance: SEO tecnico, SEO por vertical e Core Web Vitals.

- H.1 SEO tecnico. Concluida.
- H.2 SEO de conteudo, intencao de busca e interlinking. Concluida.
- H.3 Performance e Core Web Vitals. Concluida.
- CP-H enviado.

I - QA/release: PostgreSQL/migrations, E2E comercial/pagamentos, E2E IA/e-mail, infraestrutura, regressao global, cleanup/release e v2.0.0.

K - Growth continuo.

## Subfase atual

I.1 concluida - PostgreSQL real, migrations, constraints, concorrencia, idempotencia e RLS validados sem operacoes destrutivas. Clean bootstrap e downgrade permanecem pendentes ate existir banco descartavel.

I.2 concluida - migration `b8c41e7d290a` aplicada ao PostgreSQL autorizado; retry concorrente, jornada comercial, checkout Pix/cartao, webhook, reconciliacao, reembolso e Finance validados com frontend/backend reais e transports externos sinteticos. Nenhum push ou deploy foi realizado; ver `COMMERCIAL_PAYMENTS_E2E_I2.md`.

I.3 concluida - E2E IA e e-mail validado com Groq live, tool calling, guardrails,
grounded context e jornadas conectadas. Resend live inbound/outbound foi transferido
para I.4 por depender da infraestrutura publica e do signing secret.

I.4 concluida - release candidate e deploy em `main` validados; site,
backend, PostgreSQL, CORS, Checkout shell e Groq em producao passaram nos smokes.
Data API foi restringida pela migration `93c2cf108202`, com regressao conectada aprovada.
O painel Render foi confirmado e o adapter privado de PDFs no Supabase Storage foi
validado em producao com hash, imutabilidade e persistencia apos redeploy. O backup
externo diario tambem foi validado de ponta a ponta: dump PostgreSQL 17, validacao,
criptografia AES-256, checksum e armazenamento privado no Cloudflare R2 com retencao de
30 dias. Supabase Free continua sem PITR e o restore drill permanece reservado para I.6.
Estado dos gates: A Render/runtime concluido; B PDF Storage concluido; C backup externo
concluido; D Resend inbound concluido com webhook assinado, processamento HTTP 200 e
resposta automatica no mesmo thread; E Mercado Pago TEST concluido com Pix, cartao
aprovado/recusado, webhook assinado, consulta autoritativa, reconciliacao, PostgreSQL e
Finance Admin; F redirect `www` para apex concluido com 308 unico e preservacao de
path/query. I.5 nao foi iniciada. Ver `PRODUCTION_INFRA_I4.md`.

## Proxima subfase

I.5 - regressao global de lancamento e seguranca implantada.
