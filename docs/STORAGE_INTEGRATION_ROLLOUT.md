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

From `backend`, `python -m scripts.storage_preflight` reports only effective
configuration presence/format and the Commercial V2 flag. It does not contact
providers. Credential values are never included in the report.

The mandatory rollout command is:

```sh
python -m scripts.storage_preflight --require-rollout-ready
```

The protected workflow supplies the evidence file path through
`STORAGE_PREFLIGHT_EVIDENCE_PATH`; the optional `--evidence` argument is for
explicit controlled invocations and does not weaken validation.

The gate fails closed unless all required configuration is valid, the current
environment explicitly sets `COMMERCIAL_PIPELINE_V2_ENABLED=false`, and the
evidence manifest:

- has an HMAC-SHA256 signature made with `STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY`;
- is bound to the exact target `GITHUB_SHA` and a keyed fingerprint of the
  effective storage configuration (the fingerprint does not disclose secrets);
- identifies the GitHub repository, workflow run URL/ID, the allowlisted
  `.github/workflows/storage-provider-rollout.yml` on `main`, actor, and CTRL
  authorization reference;
- is time-limited to at most 24 hours;
- has a SHA-256 evidence digest and successful connectivity/smoke result for
  each of R2 temp, R2 final, Cloudinary, Supabase audio, and legacy storage.

The former `STORAGE_PREFLIGHT_*_ACCESSIBLE` and `*_SMOKE` environment flags are
not accepted as evidence. Fakes, local test fixtures, configuration presence,
or a manually edited JSON file do not prove provider connectivity. The HMAC
key must only be available to a GitHub Actions job in a protected Environment
with CTRL-approved reviewers; it must never be configured in Render, frontend
builds, pull-request jobs, or ordinary CI. The issuer must create evidence only
after the real provider smokes have completed, and the referenced sanitized
evidence artifact must be retained with the workflow run. No such real
attestation exists in this phase, so `--require-rollout-ready` is expected to
fail. The CLI labels provider checks as `verified_from_evidence` and keeps
`provider_connectivity_probed=false`; the CLI itself never probes a provider.
The allowlisted `storage-provider-rollout.yml` issuer does not exist yet, and
its protected Environment/key have not been provisioned.

When authorized, isolate the signing job from candidate code: use the trusted
workflow definition on `main`, review and bind the exact candidate SHA, retain
the sanitized smoke artifact, and expose the HMAC key only to the protected
signing job after reviewer approval. Do not run candidate-controlled scripts
in a job that can read the signing key.

### Actual publication mechanism and required integration

The repository has no application deploy workflow that can enforce this
command. Existing production publication is external: Render auto-deploys
from `main`, and Cloudflare Pages is connected to `main` (see
`docs/PRODUCTION_INFRA_I4.md`). Therefore a repository-only check cannot claim
to block those deployments. The integration is **not rollout-ready** until the
CTRL approves and configures one of these controls:

1. Disable direct auto-deploy in both providers and publish only from a
   protected GitHub Actions deployment workflow that runs this exact command
   before obtaining deploy credentials; or
2. Make the verified preflight a required check before merge and confirm the
   providers deploy only merged `main` commits after all required checks pass.

The control must cover backend and frontend publications that change Storage
adapters, configuration, migrations, or Storage-facing routes. Provider deploy
credentials must be unavailable to earlier jobs. A `workflow_dispatch` check
that is not required by branch protection is advisory, not a deploy gate.
Changing Render/Cloudflare settings or branch protection requires separate CTRL
approval and was not performed here.

## A. R2 real

Preflight:

- Confirm private temp/final buckets, least-privilege credentials scoped to
  those buckets, endpoint/region, and signed URL lifetime. Verify read, write,
  delete of a newly created test object, and that public access is disabled.
- Keep legacy Supabase production objects readable during rollout.

Smoke:

- Upload one synthetic temporary file and one synthetic final file through the
  backend; verify opaque reference, metadata, SHA-256, authorized download, and
  denied cross-owner access.
- Exercise a forced database failure and confirm compensation removes only the
  newly-created test object. Verify a persisted R2 reference remains readable
  after switching the write provider, and that rollback never deletes source
  objects or silently writes to another provider.

PASS requires all checks plus sanitized logs. Rollback sets the production
scopes back to the previous Supabase adapter and preserves every R2 object for
reconciliation.

## B. Cloudinary real

Preflight:

- Confirm credentials are server-only and least-privilege; validate signed
  upload, transformation, and controlled deletion from the backend.

Smoke:

- Upload an identifiable disposable synthetic image, verify the public
  transformed URL and integrity/ownership, replace it without silently
  deleting the prior version, then remove only the exact test asset.
- Confirm a historical external URL is never deleted.

PASS requires upload, transform, replacement, compensation, and controlled
delete. Rollback restores the previous image workflow and preserves unresolved
Cloudinary assets for inventory.

## C. Supabase audio real

Preflight:

- Confirm the configured `portfolio-audio` bucket, server-only service role,
  allowed MP3 policy, and public delivery behavior. Verify playback and HTTP
  Range requests against the actual delivery path.

Smoke:

- Upload identifiable disposable Before/After MP3 files, verify playback and
  Range requests, replace one version while retaining history, and verify a
  historical raw key remains readable.

PASS requires upload, playback/range behavior, replacement, and legacy reads.
Rollback returns the audio scope to the previous adapter without rewriting
stored references.

## D. Storage smoke evidence and cleanup

Each smoke must use a unique run-scoped synthetic object name with no customer
data, record sanitized operation results and SHA-256, test authorized and
cross-owner access, verify replacement/version behavior and failure
compensation, then remove only the exact synthetic objects it created. The
sanitized evidence artifact must include opaque non-sensitive object
identifiers, result codes, digests, timestamps, and the run reference; it must
contain no credentials, signed URLs, PII, customer keys, or object contents.
Confirm cleanup and rollback/read behavior before issuing the signed manifest.
No smoke in this phase created or changed an external resource.

## E. Legacy migration

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

## F. Lifecycle and retention

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
