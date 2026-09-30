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
| Database | Supabase PostgreSQL 17.6 | Alembic `b8c41e7d290a` | `DATABASE_URL` | connected and at head |
| Generative AI | Groq Responses API | `openai/gpt-oss-20b` | `AI_API_KEY` | production smoke and telemetry passed |
| Email | Resend | sending domain plus inbound webhook | `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET` | outbound domain present; inbound incomplete |
| Payments | Mercado Pago | checkout and signed webhook | MP access/public/webhook keys | production endpoints currently unavailable (503) |
| Documents | local storage adapter | absolute persistent mount | `PROPOSTA_PDF_DIR` | production persistence not proven |
| Analytics | consent-gated frontend adapter | provider ID configured outside this audit | provider-specific | no PII or admin metrics added |

## Render and Python

- Repository: `andersongaalves/mirai-hit-studio`.
- Expected service branch: `main`; dashboard confirmation is still required.
- Expected root directory: `backend`; dashboard confirmation is still required.
- Expected build command: `pip install -r requirements.txt`.
- Expected start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Health path: `/health`; it returns 200 without exposing configuration.
- Runtime is pinned by `backend/.python-version` to Python 3.13.1, matching the
  development and connected-test interpreter. Render's unpinned default was 3.14.3.
- A clean Python 3.13.1 venv installed only `requirements.txt`; `main`, `httpx`,
  Resend, FastAPI and SQLAlchemy imported successfully.
- Runtime dependencies include `httpx==0.28.1`; test-only packages were not copied.
- The first public health request exceeded 25 seconds; the warm retry returned 200 in
  about two seconds. This is consistent with a cold start and should be observed after
  deploy rather than treated as application failure.

The push triggered successful `build`, `deploy`, `report-build-status` and Cloudflare
Pages checks for commit `b44f3d6`. Render build command, start command, auto-deploy
setting, instance count, persistent disk and deployed Python version are not exposed by
the public endpoint. They still require confirmation in the Render dashboard/build log.

## PostgreSQL, migrations and RLS

- PostgreSQL: 17.6.
- Database revision and repository head: `b8c41e7d290a`; a single Alembic head.
- Migration `b8c41e7d290a` only adds nullable request-idempotency columns and a unique
  index. The previously deployed backend ignores them, so the database-first rollout is
  backward-compatible.
- Future migrations use a manual/pre-deploy gate run once before application rollout.
  `alembic upgrade head` must not be added to multi-worker application startup.
- The backend connects as role `postgres`: non-superuser, table owner and
  `BYPASSRLS`. RLS is defense-in-depth, not the backend authorization boundary.
- The frontend contains no Supabase client, REST Data API URL, publishable key or direct
  database access. FastAPI authentication/authorization remains the primary boundary.

### Data API risk

The database currently grants broad table privileges to `anon` and `authenticated` on
16 application tables. Several have RLS disabled; the 10 RLS-enabled tables have no
policies. If `public` is exposed through the Supabase Data API and a publishable key is
available, tables without RLS can be read or modified directly. This is a high-priority
pre-release risk even though the current frontend does not use that API.

Do not alter the application owner role during I.4. The safe remediation is a separate,
tested privilege migration:

1. confirm exposed schemas and API settings in Supabase;
2. snapshot current grants and default privileges;
3. revoke all application-table privileges from `anon` and `authenticated`;
4. revoke corresponding default privileges for future tables;
5. prove FastAPI still works through its server role and Data API client roles are denied;
6. keep rollback SQL that restores only explicitly documented grants.

No privilege or RLS change was applied to production in this audit.

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

## Mercado Pago

The current production checkout config and webhook both return 503. Local configuration
also has no access token, public key or webhook secret, so no sandbox or real payment was
attempted. Provider test credentials may be added later for a controlled sandbox smoke;
real cards and real charges are outside I.4.

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

## CORS, health and failure isolation

- The official apex origin is accepted; an unrelated origin is rejected without an
  `Access-Control-Allow-Origin` header.
- `allow_credentials` remains false and wildcard origins are rejected at configuration.
- Groq, Resend and Mercado Pago clients are built lazily; their absence does not prevent
  backend import/startup. Their feature routes return controlled 503 responses.
- Startup still performs the established database initialization routine, but it does not
  run Alembic or `create_all`.

## Storage, rate limiting and backups

- Proposal PDFs use `LocalDocumentoStorage` and require an absolute persistent
  `PROPOSTA_PDF_DIR`. Render's ephemeral filesystem is not durable storage.
- A Render persistent disk or a private object-storage adapter must be confirmed before
  relying on generated PDFs across deploys. This is a release risk, not silently assumed.
- Rate limiting uses a bounded SQLite file shared by processes on one filesystem. It is
  not globally distributed across Render instances. This is temporarily acceptable only
  for a single instance and modest traffic; instance topology needs dashboard confirmation.
- Repository scripts provide explicit `pg_dump`/restore operations. Provider-managed
  backup retention and PITR availability were not inferable from PostgreSQL and require
  Supabase dashboard confirmation. Restore drill remains I.6.

## Secrets and logging

Expected server-only names:

`DATABASE_URL`, `SECRET_KEY`, `AI_API_KEY`, `RESEND_API_KEY`,
`RESEND_WEBHOOK_SECRET`, `MERCADO_PAGO_ACCESS_TOKEN`,
`MERCADO_PAGO_WEBHOOK_SECRET`, and administrative email credentials/configuration.

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
- Alembic current/head: one head, `b8c41e7d290a`.

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
- PostgreSQL remains at the single repository head `b8c41e7d290a` after deploy.
- `www` still returns 200 instead of redirecting to the apex domain.

## External gates before I.4 completion

1. Confirm Render branch/root/build/start/auto-deploy, Python and persistent disk.
2. Configure and validate Resend receiving DNS, webhook and signing secret.
3. Configure/test Mercado Pago sandbox if test credentials are available.
4. Configure the Cloudflare `www` to apex 308 redirect.
5. Confirm Supabase exposed schemas, backups, retention and PITR.
6. Resolve Data API grants before exposing a publishable Supabase key.
7. Inspect Render and provider logs for the controlled smokes; public behavior and safe
   database telemetry passed, but dashboard log access was unavailable in this run.

## Sources checked

- Render Python version, native runtime and environment documentation.
- Resend inbound, webhook management, raw-body verification and threading docs.
- Cloudflare Pages serving, headers and `www` redirect documentation.
- Supabase RLS, API security and backup documentation/changelog.

I.5 remains responsible for global launch regression, enforced CSP decision and full
deployed Lighthouse/security review. I.6 remains responsible for restore drill and final
release cleanup.
