# Mirai Hit Studio 3.0 - Etapa 02: Mapa setorial e fronteiras

Baseline: `main` em `a37c82b` (PR #25), 14/10/2026.
Referencia: `Mirai_Hit_Studio_3_0_Roadmap_Completo.pdf`, Etapa 02.

A divisao e logica. Nenhum diretorio foi movido. Cada setor lista seus arquivos
exclusivos, os modulos compartilhados que consome e o contrato publico (rotas HTTP e
tabelas). Uma auditoria setorial pode ler dependencias externas, mas nao deve corrigi-las
de forma incidental.

## Modulos compartilhados (pertencem a S12)

| Modulo | Uso |
| --- | --- |
| `backend/main.py`, `backend/database.py` | App FastAPI, CORS, handlers globais, sessao SQLAlchemy |
| `backend/core/*` | Config, JWT/bcrypt (`security.py`), `require_admin/producer/client` (`dependencies.py`), middleware de seguranca e rate limit |
| `backend/services/audit_service.py`, `models/audit_log.py` | Trilha de auditoria usada por todos os setores |
| `backend/services/storage/*`, `documento_storage.py` | Registry de storage (Cloudinary, R2, Supabase, legacy) |
| `backend/services/email_service.py`, `backend/templates/email_*.html` | E-mail transacional (Resend) |
| `frontend/js/api.js`, `frontend/js/config.js`, `frontend/js/admin/auth.js` | Cliente HTTP, URL da API, sessao/JWT no navegador |
| `frontend/js/utils/*`, `frontend/css/variables.css`, `frontend/css/base.css` | DOM seguro, formatacao, tokens visuais |

## Setores

### S01 - Institucional
- Frontend: `index.html`, `artists.html`, `creators.html`, `media-games.html`, `portfolio.html`, `404.html`, `components/nav.html`, `components/footer.html`, `js/main.js`, `js/ui.js`, `js/portfolio_ui.js`, `js/public_navigation.js`, `js/modules/{home,portfolio,mix_comparison,components,globals,newsletter}.js`, `css/pages/{home,public,verticals,portfolio,mix-comparison,integrado-*}.css`, `sitemap.xml`, `robots.txt`, `_headers`, `_redirects`.
- Backend (leitura publica): `GET /projetos`, `GET /projetos/public/mix-comparisons`, `GET /config/portfolio-segments/public`.
- Tabelas lidas: `projetos`, `configuracoes`.
- Admin do portfolio: `js/admin/projetos.js`, `routers/projetos.py` (escrita restrita a admin), `services/portfolio_*`.

### S02 - Identidade e acesso
- Backend: `routers/auth.py`, `routers/client_access.py`, `routers/usuarios.py`, `services/client_access_service.py`, `services/usuario_service.py`, `crud/crud_usuario.py`, `core/security.py`, `core/dependencies.py`.
- Frontend: `acesso.html`, `cadastro.html`, `ativar.html`, `recuperar-senha.html`, `redefinir-senha.html`, `js/{acesso,cadastro,ativar,recuperar-senha,redefinir-senha,auth_next,integrado_auth}.js`, `js/admin/usuarios/*`.
- Tabelas: `usuarios`, `cliente_acessos`, `auth_rate_limits`.
- Contrato: JWT `sub` + `av` (auth_version); papeis `admin`, `produtor`, `cliente`.

### S03 - Orcamentos
- Backend: `routers/orcamentos.py`, `services/orcamento_service.py`, `crud/crud_orcamento.py`.
- Frontend: `calculadora.html`, `js/calculator.js`, `js/modules/{calculator,orcamento,service_renderer}.js`, `js/admin/orcamentos/*`.
- Tabela: `orcamentos`. Rota publica: `POST /orcamentos` (rate limit 5/10 min).

### S04 - Catalogo de servicos
- Backend: `routers/servicos.py`, `crud/crud_servico.py`, `models/servico.py`.
- Frontend: `js/admin/servicos/*`, `js/admin/builder/*`.
- Tabela: `servicos`. Leitura publica `GET /servicos`.
- Fase 5.04 adicionara etapas, pesos percentuais e politicas aqui.

### S05 - Propostas comerciais
- Backend: `routers/propostas.py`, `services/proposta_*`, `services/pdf_service.py`, `services/qr_code_service.py`, `crud/crud_proposta.py`, `templates/proposta.html`, `templates/email_proposta*.html`.
- Frontend: `js/admin/propostas/*`, area de propostas do portal do cliente.
- Tabela: `propostas` (snapshot de cliente/orcamento, numero, versao, PDF).

### S06 - Checkout e pagamentos
- Backend: `routers/checkout.py`, `routers/webhooks.py` (`/webhooks/mercado-pago`), `services/checkout_service.py`, `services/mercado_pago_service.py`, `services/mercado_pago_webhook_service.py`, `integrations/mercado_pago/client.py`.
- Frontend: `checkout.html`, `js/checkout.js`, `js/pix.js`, `css/pages/*checkout.css`, `functions/checkout/[[path]].js`.
- Tabelas: `cobrancas`, `pagamentos`, `provider_webhook_events`.

### S07 - Portal do Cliente
- Backend: `routers/portal_cliente.py`, `services/portal_cliente_service.py`, `services/portal_cliente_proposta_service.py`.
- Frontend: `portal-cliente.html`, `js/cliente/*`, `css/pages/cliente.css`.
- Leitura de `producoes`, `producao_arquivos`, `propostas`, `cobrancas` sempre filtrada por `cliente_id` no backend.

### S08 - Portal do Produtor
- Backend: `routers/portal_produtor.py`, `services/producao_arquivo_service.py` (parte produtor), `services/repasse_produtor_service.py` (leitura).
- Frontend: `portal-produtor.html`, `js/produtor/*`, `css/pages/produtor.css`.
- Ownership por `producoes.produtor_id`.

### S09 - Administracao operacional
- Backend: `routers/producao.py`, `routers/portal_operacao_admin.py`, `routers/clientes.py`, `routers/dashboard.py`, `routers/config.py`, `services/{producao_liberacao_service,cliente_service,dashboard_service}.py`, `crud/crud_{producao,cliente,config}.py`.
- Frontend: `admin.html`, `js/admin/{admin_shell,index,ui,dashboard}.js`, `js/admin/{producoes,clientes,dashboard,auditoria}/*`, `js/admin/configuracoes.js`.
- Tabelas: `producoes`, `clientes`, `configuracoes`, `producao_arquivos` (visibilidade).

### S10 - Financeiro
- Backend: `routers/financeiro.py`, `services/{financial_service,financeiro_admin_service,repasse_produtor_service}.py`, rotas `/producoes/{id}/repasse*`.
- Frontend: `js/admin/financeiro/*`.
- Tabelas: `cobrancas`, `pagamentos` (leitura), `repasses_produtor`.

### S11 - IA e comunicacao
- Backend: `routers/{ai_chat,ai_inbox,newsletter}.py`, `routers/webhooks.py` (`/webhooks/resend`), `services/ai_*`, `services/newsletter_service.py`, `backend/ai/knowledge`.
- Frontend: `js/chat/*`, `js/admin/inbox/*`, `js/admin/newsletter/*`.
- Tabelas: `ai_conversations`, `ai_messages`, `ai_email_threads`, `ai_briefings`, `ai_usage_events`, `newsletter`, `newsletter_campaigns`, `newsletter_deliveries`.

### S12 - Infraestrutura
- `backend/migrations/*` (Alembic, head `c5f2a7d9e184`), `backend/scripts/*`, `.github/workflows/*`, `netlify.toml`, `frontend/_headers`, `backend/core/*`, storage, backup/restore.
- Deploy: Cloudflare Pages (frontend), Render (backend), Supabase PostgreSQL 17 e Storage, R2, Cloudinary.

## Matriz de integracoes auditaveis

| ID | Fluxo | Ponto de contrato no codigo | Teste existente mais proximo |
| --- | --- | --- | --- |
| INT-01 | S03 -> S05 | `POST /orcamentos/{id}/enviar-proposta`, `proposta_service` (snapshot do orcamento) | `test_proposta_service.py`, `test_commercial_journey_i2.py` |
| INT-02 | S05 -> S06 | `POST /portal/cliente/propostas/{id}/aceitar` e `/checkout/*`, `checkout_service` | `test_client_proposals.py`, `test_authenticated_checkout.py` |
| INT-03 | S06 -> S09 | `mercado_pago_service.reconcile_order` -> `producao_liberacao_service` (idempotente) | `test_mercado_pago_webhooks.py`, `test_commerce_domain.py` |
| INT-04 | S09 -> S08 | `PATCH /orcamentos/{id}/produtor` (`orcamentos.produtor_id`), `producoes.produtor_id`, `require_producer` | `test_portal_produtor.py` |
| INT-05 | S08 <-> S07 | `producao_arquivos.visivel_cliente`, `PATCH /producoes/{id}/arquivos/{id}/visibilidade` | `test_portal_cliente_operacao.py`, `test_portal_produtor_operacao.py` |
| INT-06 | S07/S08 <-> S12 | `producao_arquivo_service.upload`, `producao_arquivo_storage`, rotas `/conteudo` | `test_producao_r2_storage.py`, `test_storage_*` |
| INT-07 | S04 -> S05 -> S09 | `servicos` -> itens da proposta -> `producoes.etapas` (lista livre hoje) | `test_proposta_contracts.py`, `test_producao.py` |
| INT-08 | S05/S06 -> S10 | `cobrancas`/`pagamentos` -> `financial_service` -> resumo admin | `test_financeiro.py`, `test_financeiro_admin.py` |
| INT-09 | S09 -> S10 -> S08 | `/producoes/{id}/repasse*` (definir, liberar, pagar, corrigir) | `test_portal_produtor_operacao.py` |
| INT-10 | S09 <-> S11 | `ai_briefing_service` -> CRM; e-mails transacionais de producao/proposta | `test_ai_briefing.py`, `test_ai_email.py` |

## Regras de PR por setor

Cada PR declara: setor principal, setores impactados, risco (P0-P3), testes executados e
arquivos alterados. Regras de negocio ficam no backend do dominio; os portais exibem
valores financeiros sem recalcular saldos.
