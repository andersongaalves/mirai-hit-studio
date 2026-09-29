# I.2 - Commercial and payments E2E

## Status: completed locally, not a release checkpoint

I.2 is validated with the real local frontend, local FastAPI HTTP server and the
authorized Supabase PostgreSQL. Mercado Pago and Resend remain transport fakes:
no real payment, Pix or email was sent. Migration `b8c41e7d290a` was applied to
the authorized database, but no Git push or application deploy was performed.
I.3 has not started.

## Reproduced defect and correction

Two identical HTTP POSTs to `/orcamentos` created two budgets. The regression
first failed with `retry duplicated budget`.

Public submissions now carry an optional UUID `Idempotency-Key` header. The
browser retains the key while the submitted payload is unchanged, including
after an API error; changing the payload generates a new key. No PII or key is
added to analytics or persistent browser storage.

The backend stores a unique nullable key and a SHA-256 fingerprint of the
validated request. A replay returns the same budget without resending emails;
changed data with the same key returns 409. A new key permits a genuinely new
request even with identical content. Requests without a key remain compatible.
The unique database index protects against concurrent workers. Five PostgreSQL
runs with two simultaneous requests each produced five logical budgets and zero
duplicates.

Public replay responses do not expose operator notes, proposal paths or later
administrative status. Keys/hashes are not included in response schemas.
Keys are currently retained only for the lifetime of the page: a reload starts
a new submission. This is not durable browser recovery after reload.
Repeated successful submission with the same key also avoids emitting another
`generate_lead` event in that page. Email remains best-effort after the commit:
an interruption between commit and transport is not repaired by replay; a
durable outbox is outside I.2 and has not been introduced.

### Migration boundary

Migration `b8c41e7d290a` follows `f2a8c4e6d901`. It adds only nullable
`idempotency_key` (`VARCHAR(36)`) and `request_hash` (`VARCHAR(64)`) columns to
`orcamentos`, plus a unique index on the key. It has no default or backfill and
does not touch users, roles or permissions. Existing backend code ignores the
new nullable columns, so the rollout is backward-compatible.

Preflight on PostgreSQL 17.6 found four existing budgets and zero possible key
collisions. The incremental SQL was transactional and non-destructive; the
unique index can briefly lock the small table. Revision advanced only from
`f2a8c4e6d901` to `b8c41e7d290a`. Columns, nullability and index were verified
afterward. Supabase backup capability was identified, but project-specific
restore/PITR availability was not independently proven from the database
connection. No downgrade was run and historical revisions were not changed.

Current database and local Alembic both report the single head
`b8c41e7d290a`. Application deployment remains intentionally separate.

## Supplementary connected HTTP evidence

`backend/tests/test_commercial_journey_i2.py` starts Uvicorn on an ephemeral
loopback port and sends actual HTTP requests with HTTPX. It includes the real
domain routers and security middleware, real login/password/JWT verification,
independent request sessions, real services and persistence.

It does not run application startup/import-backup seeds. It is a focused router
assembly, not proof of the complete FastAPI startup or browser deployment.

Only Mercado Pago's HTTP session and Resend transport are replaced. The real
Mercado Pago adapter constructs requests and parses fake provider responses.
No card PAN/CVV, real Pix, external email or real money is used.

Fixtures and PDFs live in temporary directories removed by the test harness.
The database has a synthetic operator and contact; no production data/users
are read or modified. The supplemental service label is synthetic: selection
of an existing real catalog service remains for the PostgreSQL/browser run.

Covered in connected HTTP scenarios:

- Budget creation and briefing retained in proposal snapshot.
- Proposal creation retry, authoritative item totals, real preview/PDF.
- Fake email submission, repeated send without another email.
- Authenticated operator approval, repeated approval, one production/charge.
- Guest summary excludes contact name/email.
- Pix pending, repeated creation without another provider POST.
- Signed webhook, provider GET authoritative even when event body says paid.
- Duplicate webhook and stale pending state do not duplicate/regress payment.
- Entry 99.99 plus balance 100.00 equals 199.99; Finance API reflects paid.
- Card rejection, retry requiring 3DS, no premature paid status.
- Explicit Finance reconciliation, full refund accounting.
- Provider timeout remains unresolved until authoritative webhook confirms.
- Invalid signature/reference and unauthenticated Finance request rejected.
- Card-number field rejected; transient card token absent from payment record.

Separate retry tests cover UUID validation, changed-payload conflict, independent
identical submissions, private-note protection, and legacy migration rows.

## Connected PostgreSQL and browser evidence

`backend/tests/test_commercial_postgres_i2.py` is opt-in and aborts unless the
explicit active-database acknowledgement is present. It serves the real frontend
and FastAPI over loopback and drives Microsoft Edge with Playwright. Database,
routers, authentication, services, PDF generation and Admin UI are real. Only
provider HTTP and email delivery are replaced by deterministic transports.

Validated end to end:

- Existing catalog service, dynamic briefing, retained contact values and public
  double-submit through the calculator.
- Budget and briefing visible in Admin, persisted proposal snapshot, real PDF,
  fake email send, repeated approval, exactly one production and one charge.
- Dynamic `/checkout/<reference>` without redirect, masked analytics, safe XSS
  rendering and no contact data in the public summary.
- Pix entry `99.99`, balance `100.00`, QR copy text/ticket URL, signed webhook,
  identical webhook replay, final paid state and Finance UI.
- Card rejection, retry with 3DS, transient token absent from persistence,
  authoritative reconciliation, refund and Finance detail showing `Reembolsado`.
- Two independent checkout references, malformed/nonexistent token handling,
  invalid webhook signature and provider amount mismatch recorded as conflict.
- Desktop and 390 px checkout rendering without horizontal overflow. A Finance
  screenshot was captured in the temporary fixture directory and removed after
  validation.

The PostgreSQL run exposed a real incompatibility hidden by SQLite: `FOR UPDATE`
was applied to nullable outer-joined relations. The query now uses
`FOR UPDATE OF cobrancas`, preserving charge serialization while locking only
the intended table. A PostgreSQL-dialect regression test protects the SQL shape.

## Reproduction

Disposable HTTP regression from `backend`:

```text
python -m unittest discover -s tests -p '*i2.py' -v
```

Connected PostgreSQL/browser validation is opt-in and requires the explicit
authorized target and acknowledgement; credentials are never printed. From the
repository root, the four normal browser regressions remain:

```text
node frontend/tests/public_contracting.cjs
```

The normal commands require no provider credentials. The connected test uses a
real PostgreSQL URL but never a real Mercado Pago or Resend credential.

## Recorded validation (2026-09-29)

- 38 disposable backend regressions plus 3 connected PostgreSQL/browser tests:
  41 passed.
- Browser suites `public_contracting`, `flows`, `checkout` and `analytics`:
  all passed.
- Four security/public-admin contract tests passed; the contract subprocess was
  rerun with the workspace Playwright path after an environment-only failure.
- Focused Ruff, Python/JS syntax and `git diff --check` passed.
- Connected cleanup confirmed zero I2 clients, budgets and synthetic users; the
  harness also asserts zero proposals, productions, charges, payments and fake
  webhook events before teardown completes.
- Protected-user digest stayed exactly
  `1:17ab03a60784110c7f5bb942ef9089aadd6455ce2dca4a96d448029da4c008b2`.
- PostgreSQL and local Alembic report one head: `b8c41e7d290a`.

## Deliberately not validated here

Real Mercado Pago/Resend delivery, project-specific Supabase restore execution,
unknown provider resources and deployed routing remain for I.4/I.5. No browser
test can prove real card authorization or payable Pix while transports are fake.
I.6 must preserve this distinction during release validation.

## LeanDev

Inspection followed budget -> proposal -> checkout -> provider -> Finance.
Context expanded only when PostgreSQL exposed the outer-join lock defect and when
the Admin module graph exceeded the local test server queue. No IA core, SEO,
newsletter or broad Admin audit was undertaken. Exact cumulative read/search
counts across resumed turns were not retained. No context cache was added.
