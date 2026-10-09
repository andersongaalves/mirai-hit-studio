# Storage integration and rollout gate

## Integration boundary

The temporary branch `phase/3.8-integration-gate` combines phases 3.8B-F on
top of main `2d83c8047c76614264cee2d4804fbf13a6740fc7`. It does not authorize a
merge, deploy, provider operation, migration copy, retention delete, or
Commercial V2 activation.

The integration CI uses PostgreSQL 17 and real FastAPI/Playwright processes.
R2, Cloudinary, and Supabase are replaced only at their external boundary. A
green result proves the integrated application contract, not live-provider
connectivity.

## Deployment dependency gate

Provider adapters are created lazily, so absent credentials do not prevent a
normal application startup. The affected upload/read operation fails closed
when its provider is resolved. Deploy must remain blocked until every required
provider below is provisioned and checked server-side. Production-file writes
are selected per scope; R2 and legacy Supabase remain independently resolvable
for persisted references during rollback.

- R2 private production files: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY`, `R2_TEMP_BUCKET`, and `R2_FINAL_BUCKET`. Buckets
  must be private. Each scope writes to its configured R2 or Supabase provider;
  both must remain addressable by persisted reference during rollback.
- Cloudinary public Portfolio images: `PUBLIC_IMAGE_STORAGE_BACKEND=cloudinary`,
  `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and
  `CLOUDINARY_API_SECRET`.
- Supabase public Portfolio audio: `PORTFOLIO_AUDIO_STORAGE_BACKEND=supabase`,
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and
  `PORTFOLIO_AUDIO_STORAGE_BUCKET`. The service role remains backend-only.

No credential value belongs in CI output, documentation, frontend code, or a
public URL.

## Sanitized rollout preflight

From `backend`, run `python -m scripts.storage_preflight` to report effective
configuration presence and format validity. It does not contact providers;
`provider_accessible` remains `not_checked` and `smoke` remains `not_run` until
separately reviewed evidence is recorded. The report contains no credential
values.

The deployment gate must run `python -m scripts.storage_preflight
--require-rollout-ready`. It exits nonzero unless configuration is valid,
Commercial V2 is explicitly `false`, and all five provider groups have
protected-environment attestations:

- `STORAGE_PREFLIGHT_R2_TEMP_ACCESSIBLE=true` and
  `STORAGE_PREFLIGHT_R2_TEMP_SMOKE=approved`;
- `STORAGE_PREFLIGHT_R2_FINAL_ACCESSIBLE=true` and
  `STORAGE_PREFLIGHT_R2_FINAL_SMOKE=approved`;
- `STORAGE_PREFLIGHT_CLOUDINARY_ACCESSIBLE=true` and
  `STORAGE_PREFLIGHT_CLOUDINARY_SMOKE=approved`;
- `STORAGE_PREFLIGHT_SUPABASE_AUDIO_ACCESSIBLE=true` and
  `STORAGE_PREFLIGHT_SUPABASE_AUDIO_SMOKE=approved`;
- `STORAGE_PREFLIGHT_LEGACY_STORAGE_ACCESSIBLE=true` and
  `STORAGE_PREFLIGHT_LEGACY_STORAGE_SMOKE=approved`.

Only the deployment process may set these attestations after the corresponding
read-only connectivity check and approved synthetic smoke. The integration CI
uses fakes and intentionally verifies that the rollout gate stays blocked; it
does not attest live connectivity. This repository has no deployment workflow
that can populate protected attestations in this phase.

## A. R2 real

Preflight:

- Confirm private temp/final buckets, least-privilege credentials, endpoint,
  region, and signed URL lifetime.
- Keep legacy Supabase production objects readable during rollout.

Smoke:

- Upload one synthetic temporary file and one synthetic final file through the
  backend; verify opaque reference, metadata, SHA-256, authorized download, and
  denied cross-owner access.
- Exercise one forced database failure and confirm compensation removes only
  the new object.

PASS requires all checks plus sanitized logs. Rollback sets the production
scopes back to the previous Supabase adapter and preserves every R2 object for
reconciliation.

## B. Cloudinary real

Preflight:

- Confirm account credentials and signed upload/delete access from the backend.

Smoke:

- Upload a synthetic image, verify the public transformed URL, replace it, and
  remove only the test asset.
- Confirm a historical external URL is never deleted.

PASS requires upload, transform, replacement, compensation, and controlled
delete. Rollback restores the previous image workflow and preserves unresolved
Cloudinary assets for inventory.

## C. Supabase audio real

Preflight:

- Confirm the configured `portfolio-audio` bucket, backend-only service role,
  allowed MP3 policy, and public delivery behavior.

Smoke:

- Upload synthetic Before/After MP3 files, play both public URLs, replace one
  version, and verify a historical raw key remains readable.

PASS requires upload, playback/range behavior, replacement, and legacy reads.
Rollback returns the audio scope to the previous adapter without rewriting
stored references.

## D. Legacy migration

Preflight:

- Run inventory mode first and review sanitized counts.
- Require PostgreSQL, verified destination providers, an approved batch size,
  `--confirm-copy`, and `STORAGE_MIGRATION_WRITE_ENABLED=true`.

Smoke:

- Copy a minimal authorized batch, verify source and destination size/SHA-256,
  retry the same batch, and confirm source objects remain present.

PASS requires deterministic resume, zero reference leaks, and no source
deletions. Rollback stops new batches; database references changed by a failed
batch must be reconciled transactionally, while both object copies remain.

## E. Lifecycle and retention

Preflight:

- Obtain approved retention periods by file category and implement a paginated
  provider inventory contract before evaluating remote orphans.

Smoke:

- Run dry-run only, verify active/final/financial records are preserved, and
  review every eligible category count.

The current phase is not authorized for automatic deletion. PASS for a future
delete rollout requires separate business approval, provider inventory proof,
an audited deletion plan, and a recovery window. Rollback disables the
scheduler; it cannot recover already deleted objects, so deletion stays off.

## Commercial and production controls

- `COMMERCIAL_PIPELINE_V2_ENABLED=false` throughout this gate.
- Phase 3.7 remains BLOCKED pending administrative reconciliation of historical
  proposal payment policies.
- Production remains unchanged. Real-provider smoke and rollout require a new
  explicit authorization.
