# Prepared pull request — not published

**Title:** feat(org-chart): add interactive tenant-safe hierarchy explorer

**Base:** `main` · **Head:** `feat/interactive-org-chart`

## Summary

The organization chart now supports employee search and details, contextual filters, Tree/Stacked layouts, zoom/pan/focus, department/location/status colors and directory deep links. Authorized administrators can confirm reporting-manager changes through the existing audited employee PATCH workflow. Large hierarchies use flat transport, iterative layout and bounded viewport rendering.

The optional `format=flat` response reuses employee-read authorization and tenant scope with an allowlisted serializer. Default nested API compatibility remains. Reporting changes serialize with a PostgreSQL tenant `NO KEY UPDATE` lock; unchanged manager fields do not lock ordinary profile saves. Concurrent inverse assignments cannot both commit. No new dependency, migration, paid service, worker or cron is introduced.

## Validation

- 240 frontend tests / 76 files passed; 34 relevant backend tests passed.
- Two real PostgreSQL concurrency tests passed, including full update/history/commit, inverse assignments, FK compatibility, unchanged-manager saves and independent tenants.
- Actual Flask + migrated PostgreSQL 16 + local Redis browser acceptance passed with generated local MFA accounts: 1,001 synthetic employees across two tenants; directory, profile update, search/details, filters, layouts, manager reassignment/history, cycle rejection, cross-tenant rejection and read-only permissions.
- Desktop and mobile Chromium passed keyboard/viewport checks and axe scans with no serious/critical findings; no JavaScript exceptions on the tested pages.
- Ruff, ESLint, production Vite build and diff whitespace checks pass. Dedicated local integration tests are excluded from default browser test discovery.
- Freshly fetched main is still `36a52f2`, the feature base; no merge conflict at review. Remote CI is pending publication, which requires user approval.

## Screenshots and review

Generated synthetic data only:

![Authenticated desktop](https://github.com/mmwarunge-droid/hrmis-saas/blob/feat/interactive-org-chart/docs/org-chart-evidence/integration-desktop.png)
![Authenticated mobile](https://github.com/mmwarunge-droid/hrmis-saas/blob/feat/interactive-org-chart/docs/org-chart-evidence/integration-mobile.png)

Repository review: `docs/org-chart-integration-review.md`. Feature scope and algorithm evidence: `docs/org-chart-implementation-report.md`.

## Known limitations

PostgreSQL 18, production authentication, Safari/iOS and complete screen-reader coverage are not certified. Local timings are not a load-test guarantee. The existing large JS bundle warning remains. Very deep manager edits still query ancestors; combined legacy manager-plus-linked-email edits can hold the transaction during verification email delivery. Optional export/pinning, genuine vacancy/position models and additional reporting relationship types remain deferred.

## Rollback

Revert the feature and follow-up integration corrections. No migration or infrastructure rollback is required. Later authorized manager changes are real data: correct them through the audited employee workflow; a code revert does not undo them.
