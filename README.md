# Mirai Hit Studio

Plataforma do estúdio Mirai Hit: site público, contratação de produção musical, venda de
licenças de beat, portais do cliente e do produtor e painel administrativo.

## O que existe hoje

- **Site público**: home, portfólio com créditos, páginas por público (`/artists`,
  `/creators`, `/media-games`), calculadora de orçamento, newsletter e chat de atendimento.
- **Comercial**: orçamento, proposta com documento PDF, checkout com Mercado Pago (Pix e
  cartão), Pix direto conciliado pelo Admin, licenças de beat com reserva por prazo.
- **Portal do Cliente**: projetos, etapas, arquivos e prévias, mensagens, propostas,
  pagamentos, créditos e beats.
- **Portal do Produtor**: produções atribuídas, envio de prévias e entregas (tag de áudio
  automática), beats, portfólio e repasses por etapa.
- **Admin**: dashboard com pendências, produções, clientes, propostas e orçamentos,
  financeiro (conciliação, Pix manual, repasses), serviços, combos e promoções,
  portfólio, beats, usuários, newsletter, Inbox de IA e auditoria.
- **Acesso**: login único em `/acesso` para os três painéis, cadastro e ativação de
  cliente, recuperação de senha e sessão revogável.

## Stack

| Camada | Tecnologia |
| --- | --- |
| API | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2 |
| Banco | PostgreSQL 17 (Supabase) em produção; SQLite nos testes isolados |
| Arquivos | Supabase Storage e provedores configuráveis (ver `docs/STORAGE_*`) |
| Frontend | HTML, CSS e JavaScript (ES modules), sem build |
| Hospedagem | API no Render; frontend no Cloudflare Pages (`functions/` para rotas) |
| Pagamentos | Mercado Pago (Orders API + webhook assinado) |
| E-mail | Resend |

## Estrutura

```
backend/
  core/          configuração, segurança, dependências, rate limit
  models/        modelos SQLAlchemy
  schemas/       contratos Pydantic
  routers/       rotas FastAPI
  services/      regras de negócio
  migrations/    Alembic (head registrado em backend/tests e no gate)
  tests/         unittest (isolados em SQLite e E2E em PostgreSQL)
frontend/
  *.html         páginas públicas, acesso, checkout e painéis
  js/            módulos por área (admin/, cliente/, produtor/, utils/)
  css/           camadas base, layouts e páginas
  tests/         suítes Playwright (.cjs) com API simulada
functions/       Cloudflare Pages Functions
docs/            arquitetura, decisões, runbooks e o roadmap 3.0
```

## Rodar localmente

API:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt
cp .env.example .env   # preencha só o necessário; integrações ficam desligadas sem chave
alembic upgrade head
uvicorn main:app --reload --port 8000
```

Frontend (qualquer servidor estático na porta 4173, que é a origem liberada em
`ALLOWED_ORIGINS` no exemplo):

```bash
cd frontend
python -m http.server 4173
```

## Testes

```bash
# backend: cada arquivo cria um banco descartável
cd backend && python -m unittest discover -s tests -p "test_checkout.py" -v

# frontend: Playwright com a API simulada pela própria suíte
node frontend/tests/dashboard.cjs
```

No GitHub Actions:

- **Storage Integration Gate** (`storage-integration-gate.yml`): obrigatório em PR e em
  `main`; roda testes de backend, PostgreSQL 17 e as suítes de navegador.
- **Commerce domain** e **Portals E2E**: jornadas comerciais e dos portais em PostgreSQL 17.
  Podem ser disparados manualmente em qualquer branch (`workflow_dispatch`); o Portals
  E2E também roda em `main` quando arquivos dos portais mudam.

## Publicação

A publicação usa os workflows `storage-provider-rollout.yml` (smokes reais com
autorização registrada) e `production-release.yml` (`dry-run` e depois `publish`).
Migrations são aplicadas antes, separadamente, e só com autorização. O passo a passo está
em [`docs/COMMERCIAL_V2_ROLLOUT_RUNBOOK.md`](docs/COMMERCIAL_V2_ROLLOUT_RUNBOOK.md) e
[`docs/PRODUCTION_INFRA_I4.md`](docs/PRODUCTION_INFRA_I4.md). O backup e a restauração
estão em [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md).

## Documentação

- Roadmap e auditoria 3.0: [`docs/roadmap-3.0/`](docs/roadmap-3.0/)
- Decisões: [`docs/DECISIONS.md`](docs/DECISIONS.md)
- Arquitetura comercial e checkout: [`docs/COMMERCIAL_ARCHITECTURE.md`](docs/COMMERCIAL_ARCHITECTURE.md),
  [`docs/CHECKOUT.md`](docs/CHECKOUT.md), [`docs/MERCADO_PAGO_INTEGRATION.md`](docs/MERCADO_PAGO_INTEGRATION.md)
- Frontend e design: [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md),
  [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md)
- IA: [`docs/AI_CORE_ARCHITECTURE.md`](docs/AI_CORE_ARCHITECTURE.md)

## Licença

MIT. Ver [`LICENSE`](LICENSE).
