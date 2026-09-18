# Document signing MVP stabilization

Validated on 18 September 2026 in the signing implementation checkout.

## Reproduced defects and fixes

- Malformed resource UUIDs raised database bind exceptions. Resource routes now use UUID converters; workflow query identifiers are validated before querying.
- Missing source/evidence files caused uncontrolled errors. Missing evidence now produces controlled responses; local/S3 dependency failures roll back mutations and return availability errors without exposing storage paths.
- SMTP rejected multiline document titles as email subjects. Subjects are normalized; invalid email header configuration is reported as a delivery failure.
- Test-only branches accepted missing PDFs and completed workflows after rendering failures. These branches are removed; workflow fixtures now contain real PDFs. Failed rendering leaves recipients, fields, request completion, notifications, and artifacts uncommitted.
- Repeated views created duplicate events/notifications; repeated submissions failed instead of returning the existing receipt. Views and submissions now serialize on the refreshed request row and preserve the original signature on retry. Expired/closed workflows cannot accept new signatures. Related lifecycle mutations use the same request lock.
- Email was sent before authoritative state committed, and failed transactions left newly written artifacts behind. Email is deferred until commit, notification rows participate in the transaction, new files are removed on rollback, and SMTP failures leave the committed workflow usable with a failure event.
- Platform requesters' notifications were silently dropped by the ordinary tenant filter. Platform users can receive their own tenant-scoped notifications; ordinary users remain tenant restricted.
- PDF.js's modern worker required `Uint8Array.toHex`, absent in the acceptance browser. Production/development API and worker now both use the compatibility build previously used only by unit tests.
- Task/PDF loading failures displayed indefinite loading screens. Both now display recoverable errors and retry actions; binary JSON errors are decoded. Closed requests cannot submit through the UI.
- The document library's implicit grid width expanded the mobile viewport and displaced modal click targets. Explicit shrinkable grid tracks and dialog sizing keep the upload/signing workflow usable on mobile.

## Validation

- Full backend suite with disposable migrated PostgreSQL: **352 passed**, **87% coverage**, no skips.
- Additional focused storage/signing regressions: **29 passed**, including an S3 outage rollback scenario added after that full run.
- Real PostgreSQL tests: concurrent final signers and simultaneous retries by the same signer both pass, with one completion artifact/event.
- Ruff and frontend ESLint pass.
- Frontend suite: **226 passed** (two workers; an earlier unconstrained run hit worker timeouts under concurrent browser load).
- Production Vite build passes with `VITE_API_BASE_URL=/api`.
- Playwright: **14 passed** across desktop and mobile Chromium, including the new native signing journey and existing accessibility/navigation checks.
- Sequential signing regression now runs both recipients through completion and retrieves the final PDF.

The browser scenario proves administrator login/MFA, PDF upload/library visibility, original retrieval, field placement, assignment, recipient notification/task visibility, PDF rendering, viewed state, consent, signing, completion, artifact download/checksum, document status, requester notification, refresh, and idempotent resubmission. API regressions cover generated, typed, drawn, and uploaded signatures, tenant isolation, failure rollback, and storage errors. No database schema migration or new dependency was introduced.

## Operational limits

- No P0 blocker remains in the demonstrated native signing paths.
- P1: live SMTP delivery and real S3/provider credentials require operational verification; local acceptance uses memory mail and local evidence, with mocked SMTP/S3 outage tests and existing provider suites.
- P2: post-commit email callbacks are best effort. A process termination between commit and delivery can lose an email; in-app notifications remain durable. A durable email outbox/retry worker is a follow-up improvement.
- Previously lost/corrupt source files must be restored from storage backups or re-uploaded. The application now reports their unavailability rather than completing without a signed PDF.

Deployment status is reported separately with the actual commit and live checks; local acceptance alone is not a production signing verification.
