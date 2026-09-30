# Codebase commentary coverage — 30 September 2026

Baseline: merged UI audit `6342bfe2c53a0b7789748d170d642469b88b2fe0`, followed by the separately tested notification correction `238072f`. The documentation branch is `docs/codebase-commentary`; original audit commit `aecce34` is preserved.

## Inventory and review method

The maintained application inventory contains **102 Python files in `backend/app`**, excluding tests, and **137 JS/JSX source files in `frontend/src`**, excluding tests. All were inspected structurally for responsibilities, definitions/exports and dependencies. This is not a claim of line-by-line manual review of all 239 files. High-risk workflows received focused source/transaction review, including the long signing, native PDF, evidence, leave accrual/policy, demo seed, field placement, recipient task, form/draft, authentication, invitation and notification modules. Worker, configuration, CI, browser setup and onboarding documents were reviewed separately.

The pass adds or corrects inline documentation in **23 Python files** (including the evidence worker), **16 frontend application files**, and **2 browser setup/configuration files**: **41 source/configuration modules** in total. **19 Python functions/classes** receive added or corrected docstrings, and **5 frontend functions/components** receive explicit JSDoc contracts. Module comments explain broader ownership without adding repetitive comments to small wrappers or presentational components.

Counts distinguish inventory from changed files. Existing useful comments were retained, including PDF.js compatibility and PostgreSQL driver explanations. The stale claim that the in-memory Redis substitute was test-only was corrected: explicit development `memory://` also uses it, and it does not enforce TTLs. Generated migrations, vendored dependencies, lockfile internals, builds, binaries and runtime artifacts were excluded.

## Responsibility coverage

| Boundary | Documentation location |
| --- | --- |
| Factory/configuration/Redis | Factory/config module docstrings, `InMemoryRedis`, architecture runtime section |
| Sessions/auth/MFA | Auth/session/MFA service modules and transaction-sensitive function docstrings |
| Invitations/activation/access | Recovery/provisioning modules, token model, architecture account lifecycle |
| Tenant/authorization/schema | Decorator/base-model/common-schema module contracts and contributor security expectations |
| Signing concurrency and final PDF | Parent lock, recipient lock, native field/artifact and evidence claim docstrings; architecture signing lifecycle |
| Provider adapters and workers | Adapter class contract, worker module and architecture provider evidence section |
| Storage/rollback/mail | Transaction callback docstrings, notification module/function contracts, architecture storage/mail section |
| Leave and remaining HR domains | Accrual/policy modules and architecture responsibility table |
| Form drafts and async mutations | Draft route module; Form, draft hook, request feedback and navigation comments |
| Frontend auth/tenant/client | Context and transport module comments |
| PDF and field editing | Viewer and field-placement module/JSDoc contracts |
| Accessibility and recovery | Modal, table, drawer, notification, activation and signing-task comments |
| E2E configuration | Browser setup/config comments, E2E README and contributor validation guidance |
| Onboarding contributors | New `CONTRIBUTING.md`, architecture guide and README links |

## Separate functional correction

Review found the notification post-commit recipient snapshot contained email but omitted the ID used by its SMTP error logger. An injected `EmailDeliveryError` reproduced an `AttributeError` after the authoritative commit. Commit `238072f` retains the ID in the snapshot. The new regression checks that the notification remains persisted/unread and failed delivery status is recorded. No signing, authorization, tenant, MFA or schema behavior was changed by that correction.

Documentation changes are checked by comparing Python ASTs after removing docstrings and JavaScript ASTs after removing comments/location metadata. This guards against accidental executable edits; it does not by itself prove prose accuracy. Full backend/frontend/browser validation and PR CI are recorded in the release report.

## Limits and follow-ups

This is a repository-wide responsibility map with focused inline contracts, not a claim that every function needs or now has a docstring. Future changes should extend comments beside the relevant invariant. Live SMTP, S3/provider credentials, durable mail retries, bundle splitting, Safari/iOS, real devices, manual screen-reader use and platform-admin browser coverage remain operational or product follow-ups. Local acceptance and intercepted recovery tests do not establish authenticated production behavior. No disposable production account/data set was designated for mutation tests.
