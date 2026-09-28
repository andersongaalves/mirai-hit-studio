# I.2 - Commercial and payments E2E

## Status: partial, not a release checkpoint

The connected PostgreSQL/browser journey is **not yet validated**. No push or
remote migration is authorized by this work. I.3 has not started.

The HTTP tests below are supplementary evidence on disposable SQLite, not a
substitute for the requested real PostgreSQL and browser E2E.

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
The unique database index protects against concurrent workers; PostgreSQL
concurrency validation for this addition remains pending.

Public replay responses do not expose operator notes, proposal paths or later
administrative status. Keys/hashes are not included in response schemas.
Keys are currently retained only for the lifetime of the page: a reload starts
a new submission. This is not durable browser recovery after reload.
Repeated successful submission with the same key also avoids emitting another
`generate_lead` event in that page. Email remains best-effort after the commit:
an interruption between commit and transport is not repaired by replay; a
durable outbox is outside I.2 and has not been introduced.

### Migration boundary

User explicitly authorized preparing, **not applying**, migration
`b8c41e7d290a` after `f2a8c4e6d901`. It adds only nullable `idempotency_key` and
`request_hash` columns and a unique index. Existing rows need no backfill.
Historical migrations are unchanged. Upgrade was exercised on a disposable
legacy-shaped SQLite table; legacy rows and uniqueness were checked.

**Do not deploy the changed ORM/backend against the unmigrated remote DB.**
Even reads of budgets require the new columns. A separately authorized database
upgrade or a disposable PostgreSQL with the new schema is required before the
remaining PostgreSQL journey. No remote upgrade/downgrade was executed here.
Index creation/lock timing still requires evaluation against the target table.

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

## Browser regression

`frontend/tests/public_contracting.cjs` checks request-key stability on retry and
rotation after changed contact data, together with its existing double-submit,
validation, payload and responsive checks. This existing suite uses API fixtures;
it is not the requested connected PostgreSQL browser journey.

## Reproduction

From `backend` with the existing virtualenv:

```text
python -m unittest discover -s tests -p '*i2.py' -v
```

From the repository root with Playwright resolvable and Edge available:

```text
node frontend/tests/public_contracting.cjs
```

These commands require no real database/provider credentials.

## Recorded validation (2026-09-28)

- Five new backend tests passed (three connected HTTP journeys, retry contract,
  additive migration preserving legacy rows).
- Existing Checkout, Proposal commercial, Clients, Webhooks and Finance Admin:
  31 tests passed initially; one migration test assumed a fixed old head. It now
  discovers the current head, and its rerun passed, including metadata comparison.
- Browser suites: public contracting, flows, checkout and analytics passed.
  Public contracting also checks lost-response retry reuses its key.
- Four existing security/public-admin contract tests passed.
- Python syntax, focused Ruff, changed JS syntax and `git diff --check` passed.
- Local Alembic has one head: `b8c41e7d290a`. This is not evidence that a remote
  database has been upgraded. No remote connection was used in these runs.

## Remaining I.2 acceptance work

- Authorized PostgreSQL environment containing the pending migration.
- Existing catalog service -> public browser -> API -> PostgreSQL -> proposal
  -> checkout -> Finance browser, desktop and 390px, without domain mocks.
- Concurrent retry and selective fixture cleanup evidence on PostgreSQL.
- Client matching/conflict and independent snapshot after source change.
- QR target verification, checkout route/reference, cross-client isolation.
- Amount/provider mismatch, unknown/malformed webhook in connected scenarios.
- Browser payment/3DS states, analytics privacy and Finance screenshots.
- Confirm full focused regressions and record counts before closing I.2.

Real Mercado Pago/Resend delivery is intentionally untested; official sandbox
and deployed routing remain candidates for I.4/I.5. I.6 release must not treat
the supplemental tests as complete PostgreSQL/payment-provider evidence.

## LeanDev

Inspection followed budget -> proposal -> checkout -> provider -> Finance.
Expanded into startup only to avoid automatic backup seeding, into middleware
for request IDs/rate limiting, and into migrations for the reproduced retry bug.
No IA core, SEO, newsletter or broad Admin audit was undertaken. Exact cumulative
read/search counts across resumed turns were not retained. No context cache added.
