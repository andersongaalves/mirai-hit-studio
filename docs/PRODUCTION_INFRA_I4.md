# Mirai Hit Studio - Production Infrastructure I.4

Audit date: 2026-09-29/30 (America/Sao_Paulo).

## Status

The release candidate is reproducible, the I.1-I.3 gates pass and commit `b44f3d6`
was pushed to `main`. Public post-deploy smokes passed for the site, backend and Groq.
I.4 remains partially complete because provider-dashboard and DNS gates listed below
are not configured or cannot yet be verified. No secret value is recorded here.

## Production inventory

| Component | Service | Configuration | Secret names | Status |
| --- | --- | --- | --- | --- |
| Frontend | Cloudflare Pages | project `mirai-hit-studio`, branch `main` | none required by static pages | public site healthy |
| Backend | Render | Python/Uvicorn, service URL `mirai-hit-studio.onrender.com` | runtime env | health healthy after cold start |
| Database | Supabase PostgreSQL 17.6 | Alembic `93c2cf108202` | `DATABASE_URL` | connected, at head and Data API restricted |
| Generative AI | Groq Responses API | `openai/gpt-oss-20b` | `AI_API_KEY` | production smoke and telemetry passed |
| Email | Resend | sending domain plus inbound webhook | `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET` | outbound domain present; inbound incomplete |
| Payments | Mercado Pago | checkout and signed webhook | MP access/public/webhook keys | production endpoints currently unavailable (503) |
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

- Account query found one domain: `miraihitstudio.com.br`.
- Sending capability is enabled; DKIM and sending-subdomain MX/TXT records verify.
- Receiving capability exists, but the root MX record is failed and the domain status is
  `partially_failed`.
- There are zero registered webhooks and zero received messages.
- The application route is `POST /webhooks/resend`; it verifies raw-body Svix headers
  before parsing JSON and fails closed without `RESEND_WEBHOOK_SECRET`.
- The current production route returns 503, confirming inbound is not configured.

To finish inbound: correct the receiving MX in DNS, choose the account-provided inbound
address, register the HTTPS webhook for `email.received`, store its signing secret only
in Render, enable the AI email variables, deploy, then send controlled synthetic inbound
and outbound replies. Do not create a webhook until the signing secret can be saved in
the backend environment.

### Action required in Resend and Render

In Resend, open Receiving Emails and record the non-secret inbound address; a provided
`<alias>@<id>.resend.app` address can run the first smoke without custom MX. Create one
webhook to `https://mirai-hit-studio.onrender.com/webhooks/resend` for `email.received`.
Save its signing secret directly as `RESEND_WEBHOOK_SECRET` in Render, confirm the
verified outbound sender and configure `AI_EMAIL_ENABLED`, `AI_EMAIL_FROM` and
`AI_EMAIL_INBOUND_ADDRESS`. Report only whether each variable is configured, never its
value. Then send one controlled synthetic email and verify signature, retrieval,
conversation/threading and reply headers. Custom-domain inbound additionally requires
the failed root MX to be corrected.

## Mercado Pago

The current production checkout config and webhook both return 503. Local configuration
also has no access token, public key or webhook secret, so no sandbox or real payment was
attempted. Provider test credentials may be added later for a controlled sandbox smoke;
real cards and real charges are outside I.4.

### Action required in Mercado Pago and Render

In Your integrations, activate and identify test credentials explicitly; configure the
test webhook URL `https://mirai-hit-studio.onrender.com/webhooks/mercado-pago` and its
secret, then save the existing Mercado Pago environment names directly in Render. Do not
paste values into chat. Only proven test credentials may exercise official test buyer and
card flows for approved, rejected, webhook and reconciliation states. Ambiguous or
production credentials must not be used for I.4 testing.

## Cloudflare Pages and edge

- Public apex: `https://miraihitstudio.com.br`.
- Cloudflare project evidenced by deployment checks: `mirai-hit-studio`, branch `main`.
- Home, Artists, Creators, Media & Games, Portfolio, robots, sitemap and checkout shell
  return 200.
- `/checkout/test-token-routing-123` preserves the path and returns `X-Robots-Tag:
  noindex, nofollow, noarchive`.
- `www` still returns 200 instead of a permanent redirect. Configure a Cloudflare Bulk
  Redirect with 308, subpath matching, preserved path suffix and preserved query string.
- HTML uses revalidation. Static CSS/JS/images return a four-hour browser TTL and ETag.
  Cloudflare serves Brotli for textual assets and advertises HTTP/3 via `alt-svc`; the
  audit client negotiated HTTP/1.1. No custom immutable cache rule was added because
  asset filenames are not content-hashed.
- MIME types verified: HTML, CSS, JavaScript, WebP, plain-text robots and XML sitemap.
- CSP remains report-only. HSTS, nosniff, frame denial, referrer and permissions policy
  headers are present. CSP enforcement remains an I.5 decision after violation review.

### Action required in Cloudflare

Create one hostname redirect rule matching only `www.miraihitstudio.com.br`, targeting
the HTTPS apex with status 308 and preserving path and query. Verify `www /`,
`www /artists` and `www /creators?x=1` each perform exactly one redirect to the equivalent
apex URL. The final smoke still returns 200 from `www`, so this gate remains open.
Canonicals and sitemap already use the apex and must not change.

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
  unavailable on the current plan. No scheduled off-site dump was proven. This is a v2.0
  blocker until an automated, private backup with retention exists or the project is
  upgraded and managed backup status is confirmed.

The additive proposal-hash migration is applied to the connected PostgreSQL. Render uses
the Supabase adapter with a private `propostas-pdf` bucket and server-only credentials.
Proposal 58 was used as the controlled storage fixture: generation uploaded the opaque
object `propostas/58/v1/15e000c1360a4b0ba4bef2ee127e74b8.pdf` with HTTP 200. After a
manual deploy of the same commit, health, proposal preview and document retrieval all
returned 200 and the same PDF remained available. No e-mail was sent. Gate B is closed.

### Action required for backups

For PostgreSQL, schedule `scripts.backup_database` to private, encrypted off-site storage
with an explicit retention policy. Do not leave dumps on Render's ephemeral filesystem.

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
- Data API hardening commit `06bff80` passed `build`, `deploy`,
  `report-build-status` and Cloudflare Pages checks. Connected I.2 and I.3 suites passed
  after the privilege change; final health, public routes, checkout shell, Admin auth
  surface, deterministic Chat, Groq Chat and CORS smokes passed.
- `www` still returns 200 instead of redirecting to the apex domain.

## External gates before I.4 completion

1. Render branch/root/build/start/auto-deploy, runtime pin, topology, health and disk: confirmed.
2. Private Supabase PDF storage, integrity hash and redeploy persistence: confirmed.
3. Configure and validate Resend inbound, webhook, signing secret and controlled reply.
4. Configure/test Mercado Pago sandbox with explicitly identified test credentials.
5. Configure the Cloudflare `www` to apex 308 redirect and verify path/query.
6. Configure automated off-site PostgreSQL backup and retention or upgrade Supabase;
   current Free plan has no managed daily backup/PITR.
7. Inspect Render and provider logs for the controlled smokes; public behavior and safe
   database telemetry passed, but dashboard log access was unavailable in this run.

## Sources checked

- Render Python version, native runtime and environment documentation.
- Resend inbound, webhook management, raw-body verification and threading docs.
- Cloudflare Pages serving, headers and `www` redirect documentation.
- Supabase RLS, API security and backup documentation/changelog.
- Mercado Pago test credentials, test accounts and signed webhook documentation.

I.5 remains responsible for global launch regression, enforced CSP decision and full
deployed Lighthouse/security review. I.6 remains responsible for restore drill and final
release cleanup.
