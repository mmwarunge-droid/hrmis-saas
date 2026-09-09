# Form feedback and draft readiness

Assessment and implementation: 9 September 2026. Baseline: `b30cc61`.

## Assessment

The reported hidden-error problem was architectural. Forms use React controlled state, native HTML constraints and custom submit handlers. There is no shared form-validation library. Many modal submit handlers caught API failures into their parent page's `error` state; the page alert was behind the modal portal. A global toast was therefore insufficient. Some child submit handlers also discarded the parent's promise, preventing reliable tracking of completion. Submission handlers now return explicit failure results, including local failures after intermediate uploads.

`Modal` portals to the document body at z-index 100 and owns a scrollable content region. Its original X, backdrop, Escape and Cancel paths closed immediately. Changing the `onClose` function restarted its focus-management effect. Axios flattened responses but did not consistently normalize structured validation errors; a protected-endpoint 401 could unmount entered work by clearing authentication state.

Existing signing drafts were send-ready `SignatureRequest` records: they required complete configuration, and their details screen offered deadline changes, sending and cancellation. They did not preserve an incomplete preparation form. There was no general persistent form-draft or autosave mechanism.

## Implemented pattern

- `components/forms/Form.jsx` wraps the existing controlled forms, retaining their payloads and business validation. It adds contextual summaries, native constraint checks, busy state, duplicate-submit protection, success feedback and unsaved-change protection.
- `utils/formFeedback.js` associates API activity with its active form or modal. API validation dictionaries remain available as field issues while their main message is safe to render. Errors are captured even when an existing parent catches the rejection.
- `WorkflowFeedback` focuses and scrolls the summary into view, marks matching controls invalid and links issues to those controls. Error summaries are referenced through `aria-errormessage`. Existing matching inline alerts are suppressed within a form to avoid duplicate feedback.
- `Modal` renders its own action errors inside the dialog and delegates closing to changed child forms. Its focus lifecycle no longer restarts on every `onClose` identity change.
- The router uses the data-router API so browser Back and programmatic navigation can be blocked. Links, tab changes, organization changes and sign-out also honor changed forms. Reload/tab close uses the browser's native unload warning. The in-app choices are **Save draft and exit**, **Discard changes**, and **Continue editing**; Save is available on draft-enabled workflows.
- Protected-endpoint session expiry leaves changed forms mounted and provides a new-tab sign-in action. Public login/MFA failures retain their authentication error message. This does not bypass server authentication or authorization.

## Coverage

All original native form sites use the shared component. Additional button-driven settings, signing, seal-placement and discussion editors now participate. Search/filter controls and immediate single-click actions are not treated as draft workflows.

| Workflow | Feedback / processing / close protection | Persistent preparation draft |
| --- | --- | --- |
| Signing preparation | Shared pattern; explicit send | Complete configuration; listed on Documents |
| Employee create/edit and own profile | Shared pattern | Yes, separated by record |
| User create/edit | Shared pattern | Yes, separated by record |
| Employee access/linking | Shared pattern | No; short access actions |
| Organization create/edit | Shared pattern | Yes |
| Department create/edit | Shared pattern | Yes |
| Department transfers/archive | Shared pattern | No; short administrative actions |
| Goal creation | Shared pattern | Yes |
| Goal check-ins | Shared pattern | No |
| Leave requests | Shared pattern | Yes |
| Leave setup/ledger actions | Shared pattern | No |
| Document upload | Shared pattern | Metadata; local file must be reattached |
| Onboarding/training template authoring | Shared pattern | Template description and dynamic tasks; local files must be reattached |
| Onboarding assignment/retake | Shared pattern | No; short assignment actions |
| Employee events | Shared pattern | Yes |
| Homepage / employment-governance settings | Shared pattern | Yes |
| Password, activation and MFA flows | Shared pattern | No credentials persisted |
| Signing response, discussion, company-seal placement | Shared pattern | No signature images or consent persisted as form drafts; existing server records remain authoritative |

## Private draft storage

Migration `036_private_form_drafts` creates `form_drafts`. Drafts are scoped to the authenticated owner and selected organization, with a separate global scope for platform work. The authenticated owner is always determined on the server. A client owner assertion also rejects stale-tab draft access after another account signs in.

`GET /api/form-drafts` lists metadata; `GET`, `PUT` and `DELETE /api/form-drafts/<key>` retrieve, save and discard a draft. Updates and deletes require the current revision, preventing silent overwrites from another tab. Partial or business-invalid fields can be saved because preparation is separate from submission. The API caps draft count, size and nesting, rejects credential fields and inline attachments, and never invokes signing, email or other workflow execution.

The UI supports explicit Save draft, last-saved timestamps, an indication of newer unsaved changes, resume, discard and reload after a conflict/failure. A saved candidate is never automatically substituted for current entries. Existing saved work must be resumed or discarded before submitting a replacement. Saving failures keep the form and entries open. Successful submission attempts to remove its preparation draft.

Draft persistence uses the server, not localStorage/sessionStorage. Automatic background saving is not enabled: users explicitly save meaningful progress. A browser/process crash can only recover the last explicit save; local attachment bytes require reselection.

## Signing workflow

The preparation draft includes the document ID, seal requirement, assurance method, field-placement mode, subject, completion date and time, message, signing mode, reminder settings, employee-file assignment, template settings, all recipients, roles, sequences and placed fields. Saving is independent of the send-time requirement for a future deadline, selected recipients and required signature/date placements.

Documents lists private signing drafts and opens their original document for resumption. Successful sending provides a **View signing request** action using the document's signing-request filter. Existing standard signing supports up to four participants, sequential/parallel routing, signer-specific fields and company seals. Provider-hosted QES remains a separate single-signer ceremony. These limits and the existing signing execution/integrity rules are unchanged.

New preparation drafts can be edited in full. Older send-ready `SignatureRequest` drafts remain in their existing management flow; this change does not rewrite their source snapshots or immutable audit history.

## Verification

- Frontend regression suite: 210 tests passed across 70 files.
- New tests exercise 400/422/401/403/500, network loss, timeout, native required fields, double submission, X/Cancel/Escape/backdrop, browser Back, continue/discard, failed draft saving, incomplete draft saving without execution, multi-signer/field recovery after remount, public authentication errors, and retaining drafts when an intermediate upload succeeds but the overall workflow fails.
- Backend full regression suite passed (318 passed, 4 skipped at that run), followed by the expanded six-test draft suite covering revisions, owner isolation, selected-organization isolation, stale-account rejection, authentication and invalid/oversized content.
- Frontend lint and production build passed; new backend files pass Ruff.
- PostgreSQL migration 036 upgrade, downgrade to 035 and re-upgrade passed. The new table matches its model. A full historical model/schema comparison still reports differences in older tables (timestamps, defaults and indexes); those are outside this migration.
- Existing frontend warnings about chunk size and test act/router future behavior remain. Production browser acceptance with real employee accounts, notification delivery and uploaded documents has not been run for this change.

## Rollout

Apply migration 036 before deploying the frontend that uses private drafts. Existing workflows continue using their current tables. No notification/provider credentials or infrastructure changes are needed. Keep the migration when rolling back only the frontend; downgrading 036 deletes stored preparation drafts.

Before production release, exercise one HR signing draft through Save → Leave → Resume → Send using two employee accounts, then validate signing completion and employee-file storage. Also exercise a network failure and an expired session in the deployed browser environment.
