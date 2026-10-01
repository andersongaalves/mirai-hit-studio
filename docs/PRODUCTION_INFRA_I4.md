# Mirai Hit Studio - Production Infrastructure I.4

Audit date: 2026-09-29 to 2026-10-01 (America/Sao_Paulo).

## Status

The release candidate is reproducible, the I.1-I.3 gates pass and commit `b44f3d6`
was pushed to `main`. Public post-deploy smokes passed for the site, backend and Groq.
All I.4 external gates are now confirmed. No secret value is recorded here.

## Production inventory

| Component | Service | Configuration | Secret names | Status |
| --- | --- | --- | --- | --- |
| Frontend | Cloudflare Pages | project `mirai-hit-studio`, branch `main` | none required by static pages | public site healthy |
| Backend | Render | Python/Uvicorn, service URL `mirai-hit-studio.onrender.com` | runtime env | health healthy after cold start |
| Database | Supabase PostgreSQL 17.6 | Alembic `93c2cf108202` | `DATABASE_URL` | connected, at head and Data API restricted |
| Generative AI | Groq Responses API | `openai/gpt-oss-20b` | `AI_API_KEY` | production smoke and telemetry passed |
| Email | Resend | sending domain plus inbound webhook | `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET` | outbound and inbound validated |
| Payments | Mercado Pago | Orders API checkout and signed webhook | MP access/public/webhook keys | TEST sandbox validated; production credentials not used |
| Documents | private Supabase Storage adapter | bucket `propostas-pdf` | server-only Storage credentials | production persistence validated |
| Analytics | consent-gated frontend adapter | provider ID configured outside this audit | provider-specific | no PII or admin metrics added |

## Render and Python

- Repository: `andersongaalves/mirai-hit-studio`.
- Service branch: `main`; root directory: `backend`; both were confirmed in Render.
- Build command: `pip install -r requirements.txt`.
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`, without reload.
- Auto-deploy is enabled on commit.
- Health path: `/health`; Render probes returned 200 after it was configured.
- Runtime is pinned by `backend/.python-version` to Python 3.13.1, matching the
  development and connected-test interpreter. The deploy log supplied for this gate did
  not print the interpreter version, so this is configuration evidence rather than a
  direct runtime observation.
- A clean Python 3.13.1 venv installed only `requirements.txt`; `main`, `httpx`,
  Resend, FastAPI and SQLAlchemy imported successfully.
- Runtime dependencies include `httpx==0.28.1`; test-only packages were not copied.
- The first public health request exceeded 25 seconds; the warm retry returned 200 in
  about two seconds. This is consistent with a cold start and should be observed after
  deploy rather than treated as application failure.

The service uses one Free instance with 0.1 CPU and 512 MB RAM. Autoscaling is disabled.
The Free plan does not provide a persistent disk. `WEB_CONCURRENCY=1` was observed in the
deploy log.

A single instance allows the current filesystem-backed rate limiter as a documented
temporary limitation. Multiple instances require a distributed limiter before release.

## PostgreSQL, migrations and RLS

- PostgreSQL: 17.6.
- Database revision and repository head: `93c2cf108202`; a single Alembic head.
- Migration `b8c41e7d290a` only adds nullable request-idempotency columns and a unique
  index. The previously deployed backend ignores them, so the database-first rollout is
  backward-compatible.
- Migration `93c2cf108202` removes Data API privileges from browser client roles and
  changes no tables, rows, constraints or application-role permissions.
- Future migrations use a manual/pre-deploy gate run once before application rollout.
  `alembic upgrade head` must not be added to multi-worker application startup.
- The backend connects as role `postgres`: non-superuser, table owner and
  `BYPASSRLS`. RLS is defense-in-depth, not the backend authorization boundary.
- The frontend contains no Supabase client, REST Data API URL, publishable key or direct
  database access. FastAPI authentication/authorization remains the primary boundary.

### Data API boundary and remediation

The `public` schema is exposed to PostgREST. Initially, 16 backend tables and 15
sequences granted broad privileges to both `anon` and `authenticated`; 11 exposed tables
had RLS disabled and 10 RLS-enabled tables had no policies. Repository search confirmed
there is no `supabase-js`, `/rest/v1`, `/graphql/v1`, publishable key or direct browser
database access. Supabase Auth has zero users; application authentication lives in
`usuarios` behind FastAPI.

The 16 tables were `alembic_version`, `audit_logs`, `clientes`, `cobrancas`,
`configuracoes`, `newsletter`, `newsletter_campaigns`, `newsletter_deliveries`,
`orcamentos`, `pagamentos`, `producoes`, `projetos`, `propostas`,
`provider_webhook_events`, `servicos` and `usuarios`.

Migration `93c2cf108202` revoked table, sequence and function privileges from `anon` and
`authenticated`, revoked function execution from `PUBLIC`, and changed owner `postgres`
defaults so future objects remain private. It does not touch `auth`, Storage or internal
schemas. Verification found zero client table grants, zero sequence usage grants and zero
unsafe owner defaults. Both client roles fail privilege checks for `usuarios` and
`servicos`; the application user count stayed stable. Security advisors no longer report
the non-RLS tables as externally exposed.

The production boundary is `Browser -> FastAPI -> PostgreSQL`. The backend role remains
owner-like with `BYPASSRLS`; FastAPI authorization is primary and RLS is defense in depth.
The downgrade restores only the observed legacy tables/sequences and default privileges.

## Groq

Required server configuration:

```text
AI_ENABLED=true
AI_PROVIDER=groq
AI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=openai/gpt-oss-20b
AI_API_KEY=<secret>
```

I.3 validated the official Responses endpoint, usage, tool calling, grounded context,
guardrails and deterministic-first routing. A controlled post-deploy site conversation
returned 200 and persisted provider telemetry with provider `groq`, model
`openai/gpt-oss-20b`, 1,869 total tokens and 1,454 ms provider latency. A separate smoke
validated deterministic greeting, public-services lookup, history and explicit handoff
to `waiting_human`. Prompts, replies, session tokens and credentials were not logged.
Published rate limits remain account/model dependent and must be read from the Groq
console, not hardcoded.

## Resend

- The domain `miraihitstudio.com.br` is verified for sending and the AI channel uses a
  sender from that domain. The first inbound smoke used the account-provided private
  configuration with a `resend.app` receiving address, so custom receiving MX was not a
  prerequisite for Gate D.
- The application route is `POST /webhooks/resend`; it verifies raw-body Svix headers
  before parsing JSON and fails closed without `RESEND_WEBHOOK_SECRET`.
- The registered production webhook is
  `https://api.miraihitstudio.com.br/webhooks/resend` for `email.received`. Its signing
  secret and provider credentials remain only in Render.
- Gate D is closed. Production health returned 200, an unsigned request was rejected with
  401, and a controlled real inbound e-mail produced a Resend webhook HTTP 200. The
  automatic reply reached the sender and remained in the original thread. No address,
  message body, payload or secret was recorded in this document.
- Custom-domain receiving remains optional. If adopted later, only the exact MX records
  presented by Resend should be applied after checking for conflicts with existing mail
  routing; it is not required for the validated v2.0 inbound path.

## Mercado Pago

Gate E is closed using credentials explicitly identified as TEST. The Access Token and
webhook secret remained server-only in Render; the Public Key was exposed only through the
checkout configuration endpoint. No production credential or real payment instrument was
used, and real money moved was BRL 0.

The following controlled Orders API scenarios were validated against the deployed checkout:

- Pix TEST, proposal 61: payment 73 became `aprovado` and charge 62 became `paga`.
- Card TEST `APRO`, proposal 64: payment 76 became `aprovado` and charge 65 became `paga`.
- Card TEST `OTHE`, proposal 66: the provider returned the deterministic HTTP 402 rejection;
  payment 78 became `recusado`, charge 67 remained `pendente`, the full BRL 50 balance
  remained available and no automatic retry or reconciliation was scheduled.
- A deterministic provider rejection now preserves sanitized provider status/detail/code
  for operational logging and returns a coherent public rejected result instead of 503.

The registered TEST webhook is
`https://api.miraihitstudio.com.br/webhooks/mercado-pago` for `Order (Mercado Pago)`.
An unsigned request returned 401 without persistence. A signed simulation returned 200 and
created event 66 as `processed`, linked to payment 76. Processing performed an authoritative
Orders API GET before reconciling PostgreSQL; the simulator payload was not treated as
financial truth. The current official signature contract signs `data.id` with its original
case, covered by the focused webhook suite and deployed in commit `dd322b0`.

Finance Admin was checked against the three TEST fixtures and showed the same approved,
paid, rejected and pending states stored in PostgreSQL. The financial schema persists no
PAN, CVV or card token. Duplicate delivery, invalid-signature and reconciliation behavior
remain covered by focused tests; an exact provider retry was not manufactured in the live
simulator. External refund was not forced in Gate E because I.2 already covers the domain
flow with a fake provider.

`MERCADO_PAGO_3DS_VALIDATION=never` was used only to make the official deterministic TEST
card scenarios reproducible. Before replacing TEST credentials with production credentials,
restore `MERCADO_PAGO_3DS_VALIDATION=on_fraud_risk` and repeat the production-readiness
check. No production charge is authorized by this sandbox validation.

## Cloudflare Pages and edge

- Public apex: `https://miraihitstudio.com.br`.
- Cloudflare project evidenced by deployment checks: `mirai-hit-studio`, branch `main`.
- Home, Artists, Creators, Media & Games, Portfolio, robots, sitemap and checkout shell
  return 200.
- `/checkout/test-token-routing-123` preserves the path and returns `X-Robots-Tag:
  noindex, nofollow, noarchive`.
- `www` performs one permanent 308 redirect to the HTTPS apex while preserving path and
  query string.
- HTML uses revalidation. Static CSS/JS/images return a four-hour browser TTL and ETag.
  Cloudflare serves Brotli for textual assets and advertises HTTP/3 via `alt-svc`; the
  audit client negotiated HTTP/1.1. No custom immutable cache rule was added because
  asset filenames are not content-hashed.
- MIME types verified: HTML, CSS, JavaScript, WebP, plain-text robots and XML sitemap.
- CSP remains report-only. HSTS, nosniff, frame denial, referrer and permissions policy
  headers are present. CSP enforcement remains an I.5 decision after violation review.

### Gate F validation

The Cloudflare Single Redirect Rule matches only `www.miraihitstudio.com.br` and targets
the HTTPS apex with status 308. Live GET traces for `/`, `/artists` and
`/creators?source=test` each performed exactly one hop and ended at 200 on the equivalent
apex URL. The query string remained intact, direct apex requests had zero redirects and
canonicals remained on the apex without `.html`. A synthetic checkout URL also performed
one hop, preserved its token-shaped path and query, and ended at 200 without a payment.

## CORS, health and failure isolation

- The official apex origin is accepted; an unrelated origin is rejected without an
  `Access-Control-Allow-Origin` header.
- `allow_credentials` remains false and wildcard origins are rejected at configuration.
- Groq, Resend and Mercado Pago clients are built lazily; their absence does not prevent
  backend import/startup. Their feature routes return controlled 503 responses.
- Startup still performs the established database initialization routine, but it does not
  run Alembic or `create_all`.

## Storage, rate limiting and backups

- Proposal PDFs now support private Supabase Storage through a server-only adapter. New
  objects use opaque keys with proposal/version IDs and a random UUID, never customer
  data. Uploads explicitly disable upsert.
- `propostas.pdf_path` stores the opaque `supabase://` reference and the nullable
  `pdf_sha256` stores the integrity hash. Existing local references remain readable as a
  legacy path and can be promoted without changing the bytes sent to the customer.
- The bucket is created private when absent and rejected if reported public. Access uses
  only backend credentials; the frontend receives neither credentials nor direct object
  URLs. Downloads continue to stream through the authenticated FastAPI route.
- Sending first confirms upload and hash persistence in the transaction, then submits the
  exact same bytes to e-mail. Upload failure prevents e-mail and status transition. A
  persisted document is reused and is never overwritten; sent documents with a durable
  object cannot be regenerated. Legacy documents without a durable object may be promoted
  or regenerated when their old file is unavailable.
- Rate limiting uses a bounded SQLite file shared by processes on one filesystem. It is
  not globally distributed across Render instances. This is temporarily acceptable only
  for a single instance and modest traffic; instance topology needs dashboard confirmation.
- Repository scripts provide explicit `pg_dump`/restore operations. Provider-managed
  restore remains reserved for I.6.
- The Supabase organization is on the Free plan. Current Supabase documentation says
  automatic daily backups are provided on Pro, Team and Enterprise; Free projects should
  make regular off-site logical exports. PITR is a paid add-on for Pro or higher and is
  unavailable on the current plan.
- Gate C is closed with a daily external backup for v2.0: Supabase PostgreSQL is exported
  in PostgreSQL 17 custom format, validated with `pg_restore --list`, encrypted with GPG
  AES-256, decrypted and validated again, hashed with SHA-256, then uploaded to the private
  Cloudflare R2 bucket `mirai-production-backups`. Objects under `daily/` expire after 30
  days. The workflow verifies the remote object size and removes temporary runner files.
- GitHub Actions run `36787530623` proved the complete path with
  `/usr/lib/postgresql/17/bin/pg_dump` and `pg_restore` 17.11. No secret was exposed in the
  logs. Restore was not executed and remains a required drill for I.6.

The additive proposal-hash migration is applied to the connected PostgreSQL. Render uses
the Supabase adapter with a private `propostas-pdf` bucket and server-only credentials.
Proposal 58 was used as the controlled storage fixture: generation uploaded the opaque
object `propostas/58/v1/15e000c1360a4b0ba4bef2ee127e74b8.pdf` with HTTP 200. After a
manual deploy of the same commit, health, proposal preview and document retrieval all
returned 200 and the same PDF remained available. No e-mail was sent. Gate B is closed.

### Gate C - external backup

Gate C is complete. The adopted chain is: Supabase PostgreSQL -> PostgreSQL 17 custom
dump -> archive validation -> GPG AES-256 -> decrypt verification -> SHA-256 -> private
Cloudflare R2 -> 30-day lifecycle. This is the v2.0 backup strategy while Supabase remains
on the Free plan without PITR. Recovery readiness still depends on the I.6 restore drill.

## Secrets and logging

Expected server-only names:

`DATABASE_URL`, `SECRET_KEY`, `AI_API_KEY`, `RESEND_API_KEY`,
`RESEND_WEBHOOK_SECRET`, `MERCADO_PAGO_ACCESS_TOKEN`,
`MERCADO_PAGO_WEBHOOK_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, and administrative email
credentials/configuration.

`MERCADO_PAGO_PUBLIC_KEY` is intentionally public but still configured server-side for
the checkout endpoint. Tracked-file scanning found no live Groq, Resend, webhook,
Mercado Pago or PostgreSQL credential. The only URL-shaped match is a localhost test
fixture. Logs and smoke output did not include keys, authorization headers, message
bodies, phone numbers or payment tokens.

## Pre-deploy gate

- Clean Python 3.13.1 install/import: passed.
- I.1 connected PostgreSQL: 7/7.
- I.2 connected commercial/browser: 3/3.
- I.3 connected AI/email/browser: 2/2.
- AI unit/evals: 81 passed, 2 opt-in skipped; offline evals 35/35.
- Mercado Pago/webhooks: 16/16 after updating the obsolete expected Alembic head.
- Checkout: 9/9.
- Exact-case Mercado Pago webhook signature regression: 10/10.
- Security plus budget idempotency: 5/5.
- Frontend contracting, checkout, routing, Chat, Inbox and XSS suites: passed.
- Ruff, compileall and `configure_mappers()`: passed.
- Alembic current/head: one head, `93c2cf108202`.

## Deploy and post-deploy evidence

- Git push: `b44f3d6e7902e1aa42d206bc8f90fe12b46ebf17` on `main`.
- GitHub checks: `build`, `deploy`, `report-build-status` and Cloudflare Pages completed
  successfully for that commit.
- Backend health: 200 after warm-up; one earlier 25-second timeout remains consistent
  with the documented cold-start behavior.
- Site Chat: session 201; deterministic reply 200; Groq reply 200; explicit handoff 200;
  persisted history ended in `waiting_human`.
- Public routes: Home, three verticals, Portfolio, robots, sitemap and synthetic checkout
  path returned 200. Checkout retained `X-Robots-Tag: noindex, nofollow, noarchive`.
- CORS: official apex preflight returned 200 with the expected origin; an unrelated
  origin returned 400 without an allow-origin header.
- PostgreSQL remains at the single repository head `93c2cf108202` after deploy.
- Mercado Pago TEST checkout passed Pix, approved card and deterministic rejected card
  scenarios. The signed `Order (Mercado Pago)` webhook returned 200 and reconciled the
  approved order through an authoritative provider lookup; Finance Admin matched PostgreSQL.
- Mercado Pago signature hotfix `dd322b0` passed deploy and the live signed webhook smoke.
- Data API hardening commit `06bff80` passed `build`, `deploy`,
  `report-build-status` and Cloudflare Pages checks. Connected I.2 and I.3 suites passed
  after the privilege change; final health, public routes, checkout shell, Admin auth
  surface, deterministic Chat, Groq Chat and CORS smokes passed.
- Cloudflare Gate F returned one 308 hop from `www` to apex for root, Artists, Creators
  with query string and a synthetic checkout path; every final response was 200.

## External gates

1. Gate A - Render/runtime: confirmed.
2. Gate B - private PDF Storage: confirmed.
3. Gate C - automated external PostgreSQL backup: confirmed.
4. Gate D - Resend inbound, signed webhook and threaded controlled reply: confirmed.
5. Gate E - Mercado Pago TEST sandbox, signed webhook, authoritative reconciliation and
   Finance Admin: confirmed.
6. Gate F - Cloudflare `www` to apex 308 redirect with path/query preservation: confirmed.
7. Inspect Render and provider logs for the controlled smokes; public behavior and safe
   database telemetry passed, but dashboard log access was unavailable in this run.

## Sources checked

- Render Python version, native runtime and environment documentation.
- Resend inbound, webhook management, raw-body verification and threading docs.
- Cloudflare Pages serving, headers and `www` redirect documentation.
- Supabase RLS, API security and backup documentation/changelog.
- Mercado Pago test credentials, test accounts and signed webhook documentation.

### I.5 global release regression

I.5 passed on 2026-10-01 without application-runtime changes. The backend regression
completed with 169 tests passing and 12 skipped; the browser contract that initially
could not find the temporary Playwright runtime was rerun and passed, for 170 passed
and 12 skipped across the executed set. Public/admin/checkout/Chat/analytics, security,
SEO, accessibility, responsive and proposal flows passed in the existing browser suite.

The local performance regression used Edge headless and the existing H.3 harness. It
covered Home, Artists, Creators, Media & Games, Portfolio, contracting and Checkout on
mobile and desktop. No severe LCP, CLS, JS, network or console regression was found.

Production smokes confirmed `/health` 200, public indexable routes 200, canonical apex
URLs, `www` to apex in one 308 hop, query preservation, checkout noindex, admin noindex,
expected CORS behavior and essential security headers. No payment was executed and real
money moved during I.5 was BRL 0.

The only test changes align stale fixtures with the exact-case Mercado Pago signature,
the current Alembic head `a7d4e9c2b610`, and the administrative stylesheet used by
responsive admin fixtures. No migration, runtime application code, or production data
was changed. The full Ruff baseline still reports legacy findings outside this release
regression; focused checks for the changed Python test files pass. CSP remains
report-only and is a deliberate release follow-up pending violation review.

I.6 remains responsible for clean bootstrap, downgrade validation, the encrypted R2
restore drill and final release cleanup/tagging.
