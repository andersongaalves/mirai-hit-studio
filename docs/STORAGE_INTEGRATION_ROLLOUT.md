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
- is time-limited to two hours when emitted and never accepted beyond four hours;
- has a SHA-256 evidence digest and successful connectivity/smoke result for
  each of R2 temp, R2 final, Cloudinary, Supabase audio, and legacy storage.

The former `STORAGE_PREFLIGHT_*_ACCESSIBLE` and `*_SMOKE` environment flags are
not accepted as evidence. Fakes, local test fixtures, configuration presence,
or a manually edited JSON file do not prove provider connectivity. The HMAC
key is referenced only by protected workflow steps, never Render, frontend
builds, pull-request jobs, ordinary CI, or jobs checking out another branch.
The issuer runs only from `main`; `target_sha` must equal its own `GITHUB_SHA`,
and it checks out only that same main SHA. Before any secret step, the workflow
verifies fixed SHA-256 pins for the smoke, signer, and verifier modules; it
repeats the signer/verifier checks immediately before those modules receive the
HMAC key. The publication workflow similarly pins the verifier. Any source
change requires a reviewed workflow change to update the pin. The workflow
definition on protected `main`, its Environment approval, and these source pins
are the trust roots; a separate candidate branch is never checked out. A
no-secret guard queries GitHub before any job
references `storage-rollout`, so a missing Environment is not auto-created and
mistaken for a protected one. The guard requires reviewers, prevents self-review
and administrator bypass, and restricts deployments to the single `main`
branch policy.

The emitter retains a sanitized, run-scoped report and a two-hour signed
manifest as a one-day GitHub artifact. It signs only after every real provider
smoke passes. The separate `storage-publication-gate.yml` validates the exact
successful issuer run and invokes
`python -m scripts.storage_preflight --require-rollout-ready` in a protected
job with Storage configuration/HMAC access but no Render or Pages deploy
credentials. Python dependencies are not installed in this secret-bearing
job; the preflight uses the standard library. Environment approval is the authorization control; the free-form
authorization reference is traceability only. The verifier requires a manual
dispatch from `main`, exact SHA, allowlisted workflow, complete evidence,
unchanged configuration fingerprint, and Commercial V2 exactly off.

These workflows are definitions only. A read-only API audit on 2026-10-09
confirmed that `storage-rollout`, `render-production`, and
`cloudflare-pages-production` now exist, but all three are **unprotected**:
administrator bypass is enabled, no protection rule/reviewer exists, and no
`main`-only deployment branch policy is configured. They must not be treated
as authorization gates. No provider secret value was read or changed. No real
provider evidence exists, so `--require-rollout-ready` must fail. The
CLI labels verified results `verified_from_evidence`, keeps
`provider_connectivity_probed=false`, and never probes a provider itself.

The real-smoke harness uses unique synthetic IDs, reads existing bucket
settings, and cleans up only precomputed run-scoped keys. It never creates a
missing bucket. Any uncertain failure marks the component failed and prevents
signing. The legacy document adapter does not expose deletion; its smoke uses
the server-only Supabase API to delete only its own unique key and verifies the
object is gone. No smokes were executed in this phase.

### Actual publication mechanism and required integration

The `storage-publication-gate.yml` workflow remains a manually dispatched
preflight, not a publisher and not a required branch-protection check. The new
`production-release.yml` is the prepared central publisher. It validates the
exact main SHA, exact successful integration/evidence runs, all three protected
Environments, signed unexpired Storage evidence, effective provider identity,
and that direct auto-deploy is disabled before a deploy API is called. Its
`dry-run` mode never receives Render/Cloudflare credentials or calls their
deployment APIs. Its `publish` path deploys the exact SHA to Render first,
then the static `frontend` directory to the existing Pages project, performs a
read-only smoke, and retains only sanitized release evidence.

The publisher is **prepared code, not an operational gate**. Existing
production publication is external. A read-only Cloudflare API audit confirmed
that Pages project `mirai-hit-studio` uses GitHub `main`, has production
deployments enabled, and currently serves main SHA
`2d83c8047c76614264cee2d4804fbf13a6740fc7`. The Render account could not be
queried because no Render MCP, CLI credentials, API token, or service ID was
available in this environment; its current auto-deploy state therefore remains
unverified rather than inferred from historical docs. The integration is
**not rollout-ready** until the CTRL approves and configures these controls:

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

Neither manual workflow is a mandatory publication gate while provider-side
auto-deploy remains enabled or unverified. A successful dry-run or fake-provider
CI result must not be represented as a real deployment homologation.

### Phase 3.8S infrastructure audit

| Platform | Connected/readable | Automation prepared | Current blocker |
|---|---|---|---|
| GitHub | Repository admin identity confirmed; public REST state readable | protected Environments, exact-run validation, serialized release | three production Environments exist but are unprotected; branch protection and Actions permission endpoints were not readable with the available integration; no second reviewer was proven |
| Render | No authenticated MCP/CLI/API session available | exact-commit deploy, status polling, health smoke and rollback procedure | service ID, effective branch/build/start/health/auto-deploy and rollback target require authenticated read-only audit |
| Cloudflare Pages | Account/project/deploy history readable through official MCP/API | Wrangler direct upload of the exact authorized SHA and read-only smoke | production auto-deploy is enabled; protected transition and deploy token are not configured |

The GitHub repository has no rulesets visible through the public endpoint. That
does not prove unprotected `main`: the authenticated branch-protection endpoint
was unavailable and must be checked before rollout. Existing GitHub-hosted
Pages uses a separate `github-pages` Environment and is not accepted as a
substitute for the three production Environments above.

Required secret/variable placement is deliberately separated:

- `storage-rollout`: provider variables/secrets already enumerated above and
  `STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY`; no deploy credential.
- `render-production`: `RENDER_API_KEY` secret and `RENDER_SERVICE_ID` variable;
  neither belongs in ordinary CI or Storage evidence jobs.
- `cloudflare-pages-production`: `CLOUDFLARE_API_TOKEN` secret and
  `CLOUDFLARE_ACCOUNT_ID` variable; token must be limited to the existing Pages
  project/account operations needed by the publisher.

No secret was generated, inspected, rotated, or stored by phase 3.8S.

### Required external setup before use

1. Protect existing `storage-rollout` with required CTRL reviewer(s),
   prevent-self-review, administrator bypass disabled, and exactly the `main`
   deployment policy. Confirm another eligible reviewer first; do not create a
   self-lockout when no second reviewer exists.
2. Add least-privilege R2, Cloudinary, and Supabase values referenced by the
   issuer. Keep `STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY` in this Environment only.
3. Protect existing `render-production` and `cloudflare-pages-production` with
   separate reviewer rules and `main` only, then store each provider credential
   only in its matching Environment. The Storage jobs do not use deployment
   credentials.
4. Confirm rollback availability in both provider dashboards. Only after an
   approved replacement path is ready, disable external auto-deploy and make
   the verified gate a required check. Do not integrate Storage before this
   transition has been demonstrated.

### Rollout and rollback procedure

The transition is an ordered, separately authorized operation:

1. Perform authenticated read-only audits of Render and Cloudflare and record
   current deployment IDs/SHAs, settings, health, and rollback eligibility.
2. Protect all Environments and prove the environment guard fails for bypass,
   missing reviewers, self-review, and non-main deployment policy.
3. Configure least-privilege secrets and run real provider smokes from the
   protected evidence workflow for the exact main SHA.
4. Run `production-release.yml` in `dry-run` mode and retain its sanitized
   evidence. This is still not a deploy homologation.
5. With separate CTRL authorization, disable direct Render and Cloudflare
   production auto-deploy. Re-read both provider APIs and require the guard to
   report disabled before publication credentials can be used.
6. Prove a push to `main` does not publish. Only then run the protected
   publisher with `release_mode=publish` for the exact approved SHA.
7. If Render fails before becoming live, stop. If Pages fails after Render is
   live, do not improvise another upload: preserve evidence and use the recorded
   previous Render deployment plus the Pages rollback mechanism after explicit
   operational authorization. Never downgrade the database or delete Storage
   objects as an automatic rollback.

Rollback disables further release runs, keeps Commercial V2 off, redeploys the
last known-good application commits through each provider's official rollback
mechanism, and preserves all new and legacy objects for reconciliation. A
rollback cannot be claimed tested until both real provider paths are exercised
with synthetic content under explicit approval.

GitHub Environment protections are configured outside YAML. The read-only
guard fails closed unless the API reports required reviewers, self-review
prevention, administrator bypass disabled, and only `main` as an allowed
branch. See [GitHub deployment environments](https://docs.github.com/en/actions/reference/workflows-and-deployments/deployments-and-environments)
and the [deployment branch policy API](https://docs.github.com/en/rest/deployments/branch-policies).

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
