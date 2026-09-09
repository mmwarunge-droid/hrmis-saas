# Document signing readiness review

Reviewed 9 September 2026 against the ten requested HR-native document-execution requirements.

**Reviewed project:** `/home/ubuntu/moringa/hrmis-saas-signing-base/hrmis-saas-main`.
The similarly named `/home/ubuntu/projects/hrmis-saas` checkout is older and was not used as the implementation baseline.

## Assessment

The original project already had substantial native signing functionality, but did not satisfy the complete requested workflow. It included a PDF field editor, recipient-owned fields, sequential/parallel routing, notifications and reminders, a signing dashboard, consent records, source snapshots, generated PDF evidence, and a separate provider-based QES integration.

This change implements the missing core workflow in the native signing path. It is ready for staging validation after migration **035_hr_native_execution**. This is a code and automated-test assessment, not confirmation that the deployed environment has been upgraded or configured.

| Requirement | Before review | Changes / resulting behavior |
|---|---|---|
| 1. Field placement and configuration | PDF click placement, moving/resizing, six primitive field types; limited prefills; no general read-only/default-value configuration | Palette drag-and-drop; named presets for all requested business fields; required/optional, read-only and sender defaults for data fields; Word-to-PDF preparation before placement |
| 2. Signer assignment | Field ownership grouped under each recipient | Explicit **Assigned to** selector moves a field to another signer; server rejects submissions for fields owned by another signer |
| 3. Multiple signers/order | Sequential and parallel workflows, stage notifications and reminders already implemented | Retained and regression-tested, including simultaneous final submissions on PostgreSQL |
| 4. Smart fields/signatures | Profile-generated signature, server date, limited browser prefills | Server-side snapshots of selected name/email/initials/job title/employee number/company/signing-role values; typed, drawn or uploaded PNG signature marks; authoritative account identity remains in the audit |
| 5. Reusable templates | No reusable signing-template store | Tenant-scoped templates preserve source reference, checksum, signer roles, routing and placements. HR selects a template and employee, maps remaining signers, reviews, and sends. A configurable employee-role slot supports employer-first ordering |
| 6. Status dashboard | Workflow states and recipient timestamps, but generic “in progress” label | Draft saving/sending/discarding; display labels Draft, Sent, Viewed, Partially Signed, Fully Signed, Declined and Expired; per-signer sent/viewed/signed information retained |
| 7. Audit trail | Events and consent/checksums, but no database append-only protection or consistent request context | Document/version IDs, account email, connection IP and browser user agent recorded on native events; database triggers reject event and artifact updates/deletes and completed-field mutation |
| 8. Integrity/employee file | Separate source and signed artifacts; executed copy not automatically listed as its own employee-file document | Executed PDF registered separately in the selected employee's file, linked to its immutable evidence artifact; read/download checksum verification; updates rejected; unique workflow/document identifiers embedded in PDF metadata |
| 9. Signing UX | In-app PDF review and generated profile signature | Review → required fields → choose signature method → consent → submit; no download/print/scan/upload of the document required |
| 10. HR-native execution | Most workflow infrastructure present, template and employee-file integration missing | Document preparation, employee selection, signer assignment, reusable templates, routing, tracking and executed employee-file storage are connected |

## Product decisions and limits

- Signature marks and signing dates are ceremony-controlled. Dates cannot be supplied by the browser, and a sender cannot pre-complete another person's signature. Ordinary data fields can be editable or read-only. The Full Name preset uses an editable text field with an HR prefill; older `name` fields retain their existing server-controlled behavior.
- Employee ID prefills use `employee_number`. The HRIS stores only the last four characters of national identifiers, so the **National ID** preset is intentionally blank/manual; those four characters are not represented as a complete ID.
- Native signers require an active HRIS account linked to an employee record. HR, employer representatives and CEOs must also have such records. Anonymous/external email-link signing is not added.
- PDF preparation is direct. Opening a Word file for signing from the document library creates a distinct PDF preparation copy using the existing LibreOffice converter; the original Word file remains. Direct legacy Word requests can still use the existing generated signing appendix.
- Templates save signer roles and configuration, not previous submitted answers or employee/account IDs. The sender selects which role receives the chosen employee. Static content already printed in the uploaded document is not rewritten; personal values should be dynamic fields.
- Template sources are checksum-bound. A changed source is rejected and requires a new template version. Reusing a template creates a separate source document so previous workflows remain independent.
- New native workflows sent through the UI require an employee-file selection. Legacy API calls without an employee owner retain their existing behavior; existing historical executed artifacts are not automatically backfilled into employee-file documents by this migration.
- “Locked” means immutable through application operations and database retention rules, with checksum checks detecting storage tampering. A downloaded PDF is not made mathematically impossible to edit by arbitrary external software. This work does not add certificate-based PDF signing or make a legal signature-assurance claim. The existing QES path remains separate.
- IP capture records the connection address Flask observes. A reverse-proxy deployment needs its existing trusted-proxy setup reviewed if the actual client address, rather than the proxy address, is required.
- Database owners/storage administrators remain privileged. Production retention permissions and storage administration must support the desired retention policy. Retention triggers intentionally prevent cascaded deletion of signing evidence.

## Validation completed

- Existing frontend suite: **189 tests passed**.
- New signature-input/template-picker tests: **3 passed**.
- Final affected frontend regression group after Word/draft refinements: **27 passed**.
- Signing/document backend regression group: **123 passed**, with the PostgreSQL-only concurrency test initially skipped in the SQLite run.
- New HR-native backend suite after final Word/draft additions: **8 passed** (six were included in the broader backend run).
- PostgreSQL-only concurrency test then run separately against the migrated isolated PostgreSQL database: **passed**. It checks simultaneous signers and exactly one executed artifact.
- PostgreSQL migrations **001–035**, downgrade **035 → 034**, and re-upgrade **034 → 035**: passed.
- PostgreSQL and SQLite direct-SQL audit update/delete rejection: passed. SQLite also checks artifact mutation/deletion rejection.
- Production frontend build using `VITE_API_BASE_URL=/api`: passed. Vite reports the existing large-bundle advisory.
- Ruff and ESLint checks on changed implementation files: passed.

The new backend tests exercise HR prefills, rejected read-only overrides, draft activation/discard, final image rendering, employee-file ownership, source/executed separation, tamper detection, template cloning/permissions/source checks, blank/invalid signature images, and atomic required-field validation. The Word-preparation test mocks the conversion output; the existing document-conversion regression tests also pass. No live email delivery or manual browser acceptance session was performed.

## Staging rollout

1. Back up the staging database and evidence storage using the normal deployment procedure.
2. Deploy the backend and run `flask --app run:app db upgrade` from `backend` with the intended staging database configuration. Do not rely on `db.create_all()` to install retention triggers.
3. Deploy the built frontend with its actual API URL. Retain the existing PDF/evidence storage and notification-worker configuration. LibreOffice is required for Word preparation.
4. Exercise a real employment template with Employer → Employee and a parallel case: review the rendered placements, send/view/sign timestamps, notifications, final employee-file PDF and access from each account. Check a declined and an expired request too.
5. Verify source and executed copies remain separately retrievable. Confirm an attempted modification of the executed document is rejected and evidence downloads pass checksum verification.

No production database migration, deployment, or live signing invitation was performed during this review.

## Form workflow follow-up (9 September 2026)

See [Form feedback and draft readiness](FORM_WORKFLOW_READINESS.md) for the platform-wide contextual feedback, unsaved-change protection and private resumable preparation drafts added after the original signing release.
