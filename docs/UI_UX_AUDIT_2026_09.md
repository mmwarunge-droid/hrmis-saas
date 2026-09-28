# UI/UX audit — 28 September 2026

## Baseline

The IDE checkout began clean on `feat/ui-ux-transformation-phase-2` at `279fde3b4bf5cadfcd96a7d38f90d31a34bebf49`. After fetching current main, `audit/ui-ux-revamp` was created from `2eef9b4b1be2d77762b5fee37555196686e9b9eb`. This preserves invitation resend reliability (`2a9289d`) and the PostgreSQL driver fix (`2eef9b4`). The signing checkpoint was not restored over newer work.

The existing blue/slate palette, typography, spacing, shared buttons, cards, form feedback, tables and modal shells were retained. No backend implementation, API contract, authorization, dependency, migration or consent text changed.

## Actual scope

Authenticated local administrator and employee browser sweeps rendered dashboard/home, employee directory, org chart, documents, leave, attendance, goals, tasks, onboarding, profile, settings and help. Administrator sweeps additionally rendered departments, signature requests, users, leave setup, employee-experience and employment-governance settings. Every route was measured at widths **1440, 1280, 1024, 768, 430, 390 and 360px**, height 900px.

Login, password recovery/reset, activation, invalid activation and unauthenticated MFA routing were observed locally and in production at 1440, 768 and 360px. Real local admin MFA was exercised by signing acceptance. Screenshots and DOM geometry were inspected; audit did not rely only on JSX.

This scope combines route/render checks, focused browser interactions, source review and existing automated form coverage. It is not exhaustive mutation testing of every settings form. Employee/department/leave/account forms received existing frontend integration coverage. Platform super-admin organization switching and real external-provider settings were not authenticated browser scenarios.

## Findings

No new P0 was reproduced in tested paths.

P1 issues fixed:

- `EmployeeHome.jsx`: implicit grid tracks expanded mobile cards by up to 107px at 360px. An explicit single-column grid now allows content to shrink.
- `Goals.jsx`: fixed filter columns overflowed by 141px at 1024px. Intermediate layouts wrap and desktop tracks flex; all filters remain available.
- `Sidebar.jsx`: the mobile drawer now contains keyboard focus, supports Escape, returns focus, locks background scrolling and closes on entering desktop layout. It has a named dialog role.
- `NotificationMenu.jsx`: the panel fits narrow screens; long text wraps; Escape restores trigger focus; unread status has accessible text. Mark-all-read errors preserve unread state, show feedback and permit retry. The action disables while pending. Native region/button semantics replace incomplete menu semantics.
- `Table.jsx`: nested controls no longer activate the parent row via click or Enter/Space. Direct row activation is preserved.
- `ActivateAccount.jsx`: validation failures offer retry and sign-in navigation, clear stale state, and explain when administrator assistance is needed. Backend invitation semantics are unchanged.
- `SignatureTask.jsx`: cancelled, expired and otherwise closed requests explicitly explain why no further signature can be submitted.

## Validation and regression protection

- **233 frontend tests passed, 74 files**, with two workers.
- **22 Playwright tests passed**, desktop/mobile Chromium, one worker, fresh session and isolated artifact directory.
- **51 focused backend tests passed**: signing stability, signature workflows, account invitations and invitation branding. The historical full 352-test backend run was not repeated.
- ESLint, production Vite build (`VITE_API_BASE_URL=/api`) and `git diff --check` passed.
- The repeated two-role/seven-width sweep measured zero page-width overflow on sampled routes after fixes.
- Keyboard checks cover mobile focus containment, Escape, focus return and nested table actions. Existing axe checks found no serious/critical violations on dashboard, profile, goals and documents on desktop/mobile. This is not a complete WCAG conformance certification.

Real local signing acceptance demonstrates admin MFA, mobile/desktop upload, source retrieval, signature/date field placement, recipient task/notification visibility, PDF rendering, consent, completion, final PDF/checksum, requester notification, refresh and idempotent retry. Sequential completion/final PDF retrieval, four signature input types, storage rollback and invitation resend/activation/tenant isolation passed focused backend tests. Activation form completion/navigation passed frontend integration tests; live invitation email delivery was not exercised.

A separate browser fixture tests a 12-page PDF, long recipient name, multiple required fields, missing-required-field submission prevention, task/PDF loading retries, validation/API failures, preserved entries, successful retry, and completed/cancelled/expired states at 360px. Its API responses are intercepted deliberately; it is UI recovery coverage, not backend acceptance.

Route sweeps and signing scenarios monitored page-level JavaScript errors. Deliberately injected 422/503 responses are expected. Earlier browser attempts hit expired sessions, resource timeouts, and overlapping artifact writes. The final isolated 22-test run passed in 2.1 minutes. React Router future-version notices and the existing Vite large-chunk warning remain.

## Production and follow-ups

Read-only public-page observations at https://app.careerdisrupters.com found no page-level JavaScript exceptions or viewport overflow at sampled widths. Unauthenticated MFA routing returns to login. Backend health reported production release `2eef9b4b1be2d77762b5fee37555196686e9b9eb`. No production HR/signing/invitation records were mutated. Local acceptance does not establish production signing or mail delivery.

P2 follow-ups: measure and split the approximately 1.3MB main JS bundle; extend touch-target and long-name discoverability checks; broaden manual screen-reader, Safari/iOS, real-device and platform-admin coverage. Existing live SMTP/S3 verification and durable email-outbox follow-ups still apply.

The audit is committed on `audit/ui-ux-revamp`. It is intentionally not pushed to main or deployed: this request requires review of the audit results followed by explicit deployment instruction. The containing commit records the implementation and this report; generated screenshots, auth state and test artifacts are not committed.
