# Org chart integration review — 9 November 2026

**GO for integration review and approval.** No unresolved blocker was reproduced. Publication, remote CI, merge and deployment remain pending approval. No branch was pushed, remote PR opened, production record changed or production service configured during this review.

## Baseline and scope

Reviewed the complete feature diff from `36a52f280049fc81c1570e01f324e544c1658eff` through `beec746`, including the follow-up corrections described below. A fresh fetch still identifies that same commit as `origin/main`; it is an ancestor of this feature, so there are no intervening main changes or merge conflicts at this checkpoint. Recheck before publishing if main advances. The original IDE checkout and infrastructure audit work remain untouched.

Review covered API permission/tenant boundaries, serialization and compatibility, reporting mutations/history, lock ordering, hierarchy algorithms, viewport rendering, directory integration, frontend permissions, tests and documentation. No dependency manifest, migration, hosting configuration, background worker or recurring task is added. Expected additional fixed infrastructure cost is **$0/month**; this is a code/configuration conclusion, not a fresh Render billing audit.

## Findings and corrections

| Finding | Correction and evidence |
|---|---|
| `FOR UPDATE` on Tenant unnecessarily conflicts with foreign-key `KEY SHARE` checks, potentially blocking unrelated employee/leave/document inserts. | Use `FOR NO KEY UPDATE` through SQLAlchemy `with_for_update(key_share=True)`. A real PostgreSQL test holds the reporting lock while a tenant-referencing employee insert and read complete under a 500 ms lock timeout. |
| Full profile forms submit unchanged `manager_id`, needlessly serializing profile updates and rejecting a retained inactive manager. | Remove unchanged manager fields from the mutation payload. Actual assignment/removal still validates under the tenant lock. API regression preserves an existing inactive manager during an unrelated profile edit; PostgreSQL verifies unchanged-manager saves do not wait on the reporting lock. New inactive manager assignments remain rejected. |
| An edited employee loaded before waiting on the tenant lock could retain stale relationship/history state. | Refresh the edited employee after acquiring the lock, as well as the proposed manager/ancestors. Inverse assignment test exercises the full update/history/audit/commit path. |
| Refresh after reassignment could focus the root instead of the selected employee. | Preserve selected-employee focus when that employee remains in the refreshed dataset. Existing filters and zoom behavior remain covered. |

There are no newly identified unresolved high-severity findings. This is a bounded feature review, not a claim that the entire application has no security defects.

## Actual authenticated acceptance

Used an isolated, migrated **PostgreSQL 16** database named `hrmis_org_test`, local Redis, actual Flask application, Vite frontend and Chromium. No API interception, fabricated authentication tokens, production credentials or production records were used. Mail transport was memory-only. Two synthetic tenants contained 1,000 and one employees respectively; two designated tenant administrators used password plus TOTP MFA, and a designated employee account exercised read-only access. Secrets were generated for this local run and kept outside Git.

The browser scenario proves:

- Real authenticated `GET /api/employees/org-chart?format=flat`, 1,000 employee payload, hierarchy counts and omission of private fields.
- A forged `tenant_id` query cannot switch scope; foreign employee retrieval returns 404 and foreign manager assignment returns 400. The second tenant sees only its single employee. A read-only employee can browse but cannot PATCH (403).
- Existing employee directory renders; existing profile form saves a work-location change, confirmed by the actual API.
- Search reveals Carol, details reflect the saved location, confirmed reporting reassignment updates PostgreSQL, refreshed counts and job history; a cycle-producing reassignment returns 400.
- Layout switching, contextual work-location filtering/reset, keyboard canvas scrolling and Escape dismissal.
- Mobile deep linking, details and zoom at 390×844, no page-width overflow; desktop at 1440×1000.

Screenshots contain only generated records: [authenticated desktop](org-chart-evidence/integration-desktop.png), [authenticated mobile](org-chart-evidence/integration-mobile.png). Existing mocked large-dataset screenshots/scenarios remain separate evidence.

## Validation

- **240 frontend tests passed in 76 files**, two workers, 95.67 seconds. Includes employee forms/details/directory, chart interactions, tenant-switch stale-response rejection, filters and 5,000-node iterative layout tests.
- **34 relevant backend tests passed**: org chart, employees, tenant context, object authorization, employee access directory/provisioning and employee-user tenant boundaries. No skips in this run.
- **Two real PostgreSQL concurrency tests passed**. Competing inverse assignments produce one commit and one validation rejection. Same-tenant reporting edits serialize; other tenants proceed independently. Ordinary reads, FK inserts and unchanged-manager profile saves proceed during the held lock. The deliberately blocked second reporting edit returns lock-timeout code `55P03`, not a deadlock.
- **One real full-stack browser scenario passed** (final run 30.6 seconds), covering the three accounts, two tenants and desktop/mobile contexts listed above. Desktop and mobile axe scans reported no serious/critical findings, and all four browser pages reported no JavaScript exceptions. Separate unit/API tests cover permission denial and malformed/legacy graph variants.
- Ruff, frontend ESLint, production Vite build with `VITE_API_BASE_URL=/api`, and whitespace checks pass.
- A sampled 1,000-person authenticated API response took **335–1,484 ms**. Inverse edit transaction maximum was **29–43 ms** in repeated local runs. These measurements are not production latency guarantees or a stress test.

Existing React Router future notices, React test `act` warnings, browser runner color-environment warning and the Vite large-chunk warning remain. Local Flask log inspection found no traceback, ERROR marker or HTTP 500; deliberate authorization/validation failures are expected. One repeated browser attempt exhausted the existing `/auth/me` rate limit in reused disposable Redis and returned to login (429). The final run uses fresh local rate-limit state; no application security limit was disabled or production state changed. Reproduction should start with a fresh disposable stack rather than repeatedly reusing exhausted counters.

## Authorization, compatibility and performance review

Both org-chart formats require JWT authentication and `employee:read`, and obtain employees through the existing tenant-scoped query. Flat serialization is allowlisted; private phone, address, DOB, salary and identification fields are not added. Foreign-tenant department metadata and unavailable manager identifiers are withheld. Details show the authorized employee dataset; existing PATCH permission, tenant/self/cycle checks, audit and effective-date validation remain authoritative. React renders names as text; no HTML injection or browser persistence of employee records is introduced.

Default nested `roots`, `vacancies` and existing metadata remain available. Flat format is opt-in and adds chart metadata. Invalid legacy edges become presentation roots with explicit integrity warnings, not database repairs. The legacy vacancy field remains compatibility-only; the new UI does not misrepresent historical roles as verified vacant positions. Inactive employees remain excluded by existing policy.

Hierarchy indexing, cycle detection/counts and layout are iterative. Query loading avoids per-employee department queries. Search/filter work is client-side over the authorized payload; off-screen cards are omitted and images lazy-loaded. No polling/subscription or new infrastructure is introduced. The flat response still transfers the full authorized active dataset; 5,000-node algorithms are tested, but very large real tenants merit payload/latency profiling. Deep manager edits still traverse ancestors with queries; the sampled balanced hierarchy does not establish a worst-case deep-chain transaction duration.

## Locking assessment and limits

All actual manager assignments/removals through the employee service acquire the same tenant row lock before graph writes; ordinary chart reads take no reporting lock. `NO KEY UPDATE` locks conflict with one another and serialize competing graph edits, while allowing foreign-key `KEY SHARE` checks. Locks end at the existing transaction commit/rollback. Refresh after acquisition ensures graph validation uses current committed relationships at PostgreSQL's default READ COMMITTED isolation. No migration or distributed lock service is required.

No deadlock was reproduced in the tested competing-edit paths. This is not a proof against every combination of administrative writes. Tenant configuration writes can legitimately contend on the same row. A legacy combined profile operation that changes both manager and a linked account email can still send verification mail inside its transaction and extend lock duration; this chart submits manager-only changes, and unchanged-manager profile edits now avoid the lock. Memory-mail acceptance does not measure SMTP delay. A broader post-commit mail/outbox refactor is separate work, not silently included here. Production PostgreSQL 18, extreme contention and live SMTP were not certified by this local PostgreSQL 16 run.

## Reproduction and release boundaries

Use a fresh local database named `hrmis_org_test`, loopback PostgreSQL/Redis, and memory mail. Migrate with `flask --app run.py db upgrade` from backend, using `APP_ENV=development`, `FLASK_SKIP_DOTENV=1`, local `DATABASE_URL`, `REDIS_URL`/`RATELIMIT_STORAGE_URI`, `MAIL_TRANSPORT=memory`, disposable `SECRET_KEY`/`JWT_SECRET_KEY`, and temporary upload/evidence directories. Configure frontend/CORS as `http://localhost:5189` and Flask on `127.0.0.1:5059`.

Generate a fresh password and valid Base32 TOTP secret outside Git. Export them as `ORG_TEST_PASSWORD` and `DEMO_MFA_SECRET`; use the same values for seeding and Playwright. Set `HRMIS_ORG_ACCEPTANCE=1` and `ORG_TEST_FIXTURE` to an absolute temporary JSON path, then run `python app/tests/seed_org_chart_acceptance.py` from backend. The helper refuses non-loopback databases, database names other than `hrmis_org_test`, non-memory mail and nonempty tenant databases. Its populated-database refusal was verified. It never clears data to make a rerun pass. Recreate only your disposable database for a clean rerun.

Start Flask without debugger/reloader and Vite on 5189 with `VITE_API_BASE_URL=http://localhost:5059/api`. Install the existing e2e lockfile dependencies and run `npx playwright test --config org-chart-integration.config.js` from `frontend/e2e`, with the same fixture/password/MFA environment. No auth-state file or trace is committed. The spec lives outside the default `tests` directory so normal browser CI does not require these local fixtures. Test discovery verifies that separation. The dedicated configuration writes only to `/tmp/hrmis-org-integration`.

For lock tests, set `HRMIS_ORG_TEST_URL` to that disposable local PostgreSQL URL and run `pytest app/tests/test_org_chart_postgres.py -s`; each test creates and removes its own schema. Ordinary backend tests use the existing isolated test fixtures.

No authenticated production, Safari/iOS, real touch-device or complete screen-reader certification is claimed. Optional export/pinning and additional relationship types remain deferred. Remote CI cannot be certified until the user approves publishing the branch. Recheck main and CI before merge.

The owned local Flask, Vite, Redis and PostgreSQL acceptance processes were stopped after validation. Temporary dependency links were removed; logs, generated secrets and auth material are excluded from the feature commit.

## Rollback

Revert the feature and its integration corrections to restore the former UI/API presentation. No schema or service rollback is needed. Any later authorized manager changes are actual employee data; correct them through the audited employee workflow rather than reverting a database or assuming a code rollback reverses data. Keep the existing API/PostgreSQL/Valkey/storage configuration unchanged.
