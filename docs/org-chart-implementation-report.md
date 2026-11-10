# Interactive org chart implementation report — 9 November 2026

The subsequent [integration review](org-chart-integration-review.md) records full-stack synthetic acceptance and fixes beyond `beec746`; it supersedes the pre-integration validation boundary below. The [PR description](org-chart-pull-request.md) is prepared locally and remains unpublished pending approval.

## Delivery and scope

Implemented on dedicated branch `feat/interactive-org-chart`, based on fetched main `36a52f2`, in `/tmp/hrmis-org-chart`. The original IDE checkout and prior infrastructure-audit work are preserved. No production service, environment variable, employee record or database schema was changed. No dependency was installed into the application.

The reference video itself was not attached. The written requirements informed the interactions; existing Kinetic components, blue/slate colors, permissions and employee records remain authoritative.

## Existing architecture and gaps

See [the assessment and plan](org-chart-enhancement-plan.md). Existing `/org-chart` used `GET /api/employees/org-chart`, a recursive tree response from Employee.manager_id, with basic collapse and zoom. The directory and employee profile already used the same employee API. Department, job title, location and active/probation status exist; there is no independent position entity, dotted-line relationship, or organizational-unit model. The existing manager update API already records job history and audit events.

## Implemented capabilities

| Requirement | Result |
|---|---|
| Employee cards | Photos with initials fallback, name/title/department/location/status, direct and indirect report counts, selection and collapse indicators |
| Hierarchy correctness | Multiple roots, missing managers, self edges and cycles handled iteratively; invalid edges become presentation roots with separate integrity messages; persisted data is never silently repaired |
| Details panel | Authorized employee email/start date/tenure, role, department, status, manager and direct-report navigation; profile link follows employee-read permission; Escape closes and returns focus |
| Search | 180 ms debounce over the already-authorized dataset; name, employee number, title, department and location; capped result list; reveals required ancestors and focuses the employee |
| Viewport | 10–200% zoom, reset zoom, two-dimensional fit, center, focus selected, mouse blank-space drag, native touch scroll, keyboard canvas arrows; selection does not reset zoom |
| Layout | Tree and compact indented Stacked, sharing one hierarchy index; layout changes preserve selection/search/filter state |
| Filters | Department, location, active/probation status, manager and job title; matching nodes retain ancestor context; counts remain unfiltered authorized reporting counts |
| Visualization | Neutral default; deterministic department/location/status accent colors and text legend; no employee data persisted in browser storage |
| Directory | Per-person View in Org Chart in table/cards, URL employee focus, return to directory and authorized profile navigation |
| Reporting changes | Existing PATCH endpoint with confirmation, active/probation manager candidates, descendant exclusion, server tenant/self/cycle/eligibility checks, existing history/audit/effective-date validation, refresh without page reload |
| Large datasets | Flat transport, iterative traversal/layout, initial collapsed subbranches, off-screen card omission, lazy image loading and direct-report list pagination |
| Recovery | Loading, empty, inaccessible/deep-linked employee and fetch/retry messages; relationship integrity details; mutation failures remain visible in confirmation dialog |

Focusing an employee hidden by filters clears those filters so the destination can actually be revealed. Search selection does the same. During active filtering, relevant branches are shown and collapse controls are disabled; clearing filters restores the stored collapsed state. Explicit Refresh obtains current profile changes; there is no timer polling or live subscription.

## Source changes

- `backend/app/services/org_chart_service.py`: dedicated allowlisted serializer, linear cycle detection and bottom-up counts. No private phone/address/identification/DOB/salary fields are included. Generic phone is deliberately omitted because it is not classified as a work number.
- `backend/app/routes/employee_routes.py`: reuses employee-read authorization and tenant query; loads only chart employee columns and eager-loads department identity/name. Adds `format=flat`; default nested roots and legacy vacancy-summary field remain available. Foreign-tenant department names and unavailable manager IDs are not serialized.
- `backend/app/services/employee_service.py`: manager eligibility check and PostgreSQL tenant-row serialization of non-null manager assignments, with refreshed relationship reads. This prevents concurrent inverse assignments from both validating against stale state. The lock lasts until the existing transaction completes; no migration or new lock service is required.
- `frontend/src/components/orgChart/hierarchy.js`: shared iterative indexing, ancestor navigation, contextual filtering, layout and color mapping.
- `frontend/src/pages/OrgChart.jsx`: chart interactions, viewport rendering, details, settings and confirmed existing manager workflow. Tenant context changes immediately hide the previous dataset; outdated responses are ignored.
- `frontend/src/pages/Employees.jsx`: per-person chart links for active/probation employees.
- `frontend/src/api/employeeApi.js`: optional org-chart query parameters.
- Backend/frontend regression files and isolated browser configuration: synthetic coverage described below.

## API and database compatibility

No new endpoint or migration. The existing read endpoint accepts `?format=flat`, returning `items`, `meta`, `integrity_issues` and the retained `vacancies` field. Without this option it retains nested `roots`. Additional chart fields include employee_number, department_id, email, hire_date and indirect_report_count. Invalid manager references are normalized only in the chart representation; read the integrity warning rather than interpreting a display root as an actual manager reassignment.

The new UI does not display inferred historical roles as genuine vacant positions. The legacy response field is retained for compatibility because the current schema cannot establish whether an old role is truly vacant. Inactive employees remain outside the active chart, following existing rules.

`PATCH /api/employees/{id}` remains the only reporting-assignment mutation. Existing permission checks, audit, job history and effective-date validation apply. Managers selected for new assignments must now be active or on probation. A per-tenant lock serializes these edits; there is no additional infrastructure. Ordinary browsing does not take that lock.

## Validation evidence

- Full frontend suite: **240 tests passed, 76 files**, two workers, in an isolated final run (67.95 seconds). A run overlapping browser/build work timed out in an existing password-recovery test and caused a subsequent assertion failure; the isolated rerun passed without changing those tests. After the last memoization-only optimization, the 11 focused chart tests were rerun.
- Final focused chart tests: **11 passed**, including search/ancestor reveal, card/details interaction, manager confirmation, tenant-switch stale-response rejection, read-only controls, zoom/photo behavior, contextual filters and 5,000-node iterative layouts.
- Relevant backend suite: **26 passed** across org-chart, employee, tenant-context, object-authorization and employee-access-directory tests. Covers nested compatibility, flat authorization/privacy, multiple roots, counts, orphan/cycle handling, inactive/foreign manager rejection and history after manager update.
- Dedicated **real PostgreSQL 16 concurrency test passed**: two threads load the old graph and attempt inverse manager assignments; one commits and one is rejected. The disposable schema/server was removed/stopped. PostgreSQL 18 is not locally certified by this test.
- Browser scenarios: **desktop Chromium 1440px and mobile Chromium 390px**, 1,000 synthetic people, search/focus, layout/color/filter changes, zoom/default restoration, bounded rendered-card count, no horizontal page overflow, no JavaScript exceptions and no serious/critical axe findings. APIs are deliberately intercepted; this is browser interaction coverage, not authenticated live-production acceptance.
- Ruff, ESLint, production Vite build (`VITE_API_BASE_URL=/api`) and diff whitespace checks pass. Existing React Router notices, test act warnings and Vite large-chunk warning remain.

Development failures were resolved: initial browser interception also caught `/src/api` JavaScript modules; fixtures now intercept only `/api/`. Earlier assertions matched duplicate labels in hidden select options; tests target controls precisely. The negative permission fixture initially referenced a detached SQLAlchemy object; it now resolves the account inside its session. Visual inspection caught the root being off-screen after mobile reset; default restoration now focuses the root. No production records were used to manufacture evidence.

## Performance and infrastructure impact

A local Node measurement of indexing plus fully expanded Tree layout took **5.73 ms for 1,000** and **15.58 ms for 5,000** balanced synthetic nodes. This is a single local algorithm sample, not a browser frame-time or production API SLO. Separate deep-chain tests process 5,000 employees without recursive hierarchy/layout traversal.

Browser scenarios enforce fewer than 100 mounted cards for the sampled 1,000-person viewport. Off-screen nodes remain searchable; selection/focus mounts the destination. Large direct-report lists start at 50 with Show more. React StrictMode may initiate an additional development request; there is no recurring polling. Fetches occur on mount/context change, explicit refresh and successful manager edit. Department eager loading avoids per-node lookup queries. Filter option sets are memoized, and descendant exclusion for manager choices is computed only when the edit dialog is open, avoiding repeated ancestry scans during panning.

Expected additional fixed hosting cost: **$0/month**. Existing API, PostgreSQL, Valkey/security and file storage remain shared; no new cron, worker, disk or paid chart/export API. Current overall bill was not re-audited for this feature. The production bundle retains its existing approximately 1.3 MB warning; the chart adds local client code, not a hosted visualization dependency.

## Limits and second-stage proposal

- Only the authoritative reporting-manager relationship is supported. Additional relationship types/units/vacancies require a real schema and authorization design first.
- Pinning is omitted as optional. Chart preferences are session component state, not persisted employee data.
- PNG/PDF export is deferred as explicitly optional. A follow-up should export the authorized filtered layout model, not screenshot only mounted cards. Define page tiling/resolution, private avatar fetching/CORS and memory limits, then compare browser print/SVG/canvas approaches. No paid service or backend worker is proposed.
- Existing nested JSON consumers remain appropriate for ordinary depths; the new flat response is the supported path for exceptionally deep hierarchies.
- Browser fixtures and API regression tests are complementary; a real full-stack browser journey with designated synthetic accounts is still useful before deployment. No authenticated production testing or Safari/iOS certification is claimed.
- Existing styling has no dedicated dark-theme context/toggle; this change follows the current shared light visual system.
- This is not a complete WCAG certification or an exhaustive audit of all historical employee relationships.

## Review and rollback

Review this dedicated feature branch before deployment. No live infrastructure changes are needed. Revert the feature changes to restore the previous UI/API presentation; there is no schema rollback. Authorized manager edits made later are actual employee data and must be corrected through the audited employee workflow, not undone by a code revert or database restore.

## Synthetic browser screenshots

[Desktop Tree view](org-chart-evidence/desktop.png) · [Mobile focused Tree view](org-chart-evidence/mobile.png)

These screenshots contain generated example names and counts, not employee records. The browser fixture covers Stacked mode, details and filters before restoring the default Tree view for capture. Reproduce with the isolated `frontend/e2e/org-chart.config.js` against a local Vite server on port 5179 with `VITE_API_BASE_URL=/api`; install the existing e2e lockfile dependencies first. The fixture intercepts API calls and needs no live credentials.
