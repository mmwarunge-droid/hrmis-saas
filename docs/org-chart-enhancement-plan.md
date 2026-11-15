# Org chart enhancement plan — 8 November 2026

Baseline: origin/main 36a52f2, isolated feature branch feat/interactive-org-chart. Existing IDE edits are not part of this branch. No reference video was attached; the written interaction requirements are the specification.

| Capability | Existing | Planned |
|---|---|---|
| Data | Employee.manager_id, tenant_id, department, job_title, work_location, active/probation | Reuse; no migration |
| Hierarchy | Recursive nested API; cycle fallback; direct counts | Iterative forest, integrity warnings, direct/indirect counts; optional flat representation |
| Cards | Names, title, department, collapse | Selection, photo fallback, locations and counts |
| Exploration | Text filtering and zoom | Debounced result selection, ancestor reveal, detail panel, pan/focus/fit |
| Customization | Tree only | Tree/stacked, department/location/status color and filters, legend |
| Integration | Profile links | Directory-to-chart links and authorized existing manager update |
| Performance | Entire recursive tree expanded | Initial collapse, flat layout and viewport rendering; no polling |
| Export | None | Separate second-stage proposal; no paid service |

Employee read permission and database-level tenant query remain mandatory. The chart exposes a dedicated field allowlist, never Employee.to_dict(). Phone is omitted because the model has only a generic phone field, not a clearly classified work phone. No salary, DOB, address, identification or emergency contact fields are added. Active/probation visibility remains unchanged. There is no position entity, dotted-line relationship or independent organizational-unit model; do not invent these. Existing inactive-role summaries are historical roles, not confirmed vacancies.

Reuse shared controls and colors; no visualization package or recurring infrastructure. Fetch once per tenant/context and on explicit refresh or successful edit. Filters retain ancestors; counts describe the unfiltered authorized forest. Display relationship issues separately without changing stored managers. Preserve existing nested API consumers; use format=flat for the new chart to avoid deeply nested JSON.

Milestones: data safeguards; interactive cards/layout; details/search/navigation; filters/directory; authorized edit and performance; automated and browser verification. Reporting edits use existing permission, validation, history and effective-date rules. No production changes or schema changes authorized by this implementation.
