# Employee profile header layout fix — 13 November 2026

## Root cause (recorded before implementation)

Based on current main `36a52f2`, in isolated branch `fix/employee-profile-header`; unrelated IDE changes and the org-chart PR are preserved.

EmployeeDetails applies `-mt-10` to the entire identity/actions flex row, lifting text and actions 40px across the cover boundary. Bottom alignment sometimes hides this for short text, but wrapping or taller identity content makes the overlap visible. Name/title `truncate` classes also discard important information. MyProfile repeats the pattern with `-mt-14` (56px) and a wrapping identity row. Neither reserves an independent normal-flow identity section below the cover.

Two full profile-header implementations exist: `/employees/:id` (administrator and authorized employee views share it) and `/profile` (self-service). EmployeeHome has a separate welcome hero and compact person strip, not a cover-boundary profile header. Its personalization modal edits the same photo/cover URLs. EmployeeExperienceSettings configures company banner/logo images and URLs; it does not render another profile-header preview. Directory cards and org-chart cards link to employee details and have no cover-boundary header. No additional preview/profile pages were found.

Existing cover selection: EmployeeDetails uses employee cover or its blue gradient; MyProfile uses employee cover, then tenant banner, then its dark gradient. Company branding supports logo/banner images, organization/welcome text, and homepage sections. No configurable profile text colors or dark-theme selector were found. Preserve these image-selection and gradient rules; solid white identity surfaces retain the existing slate text independent of image brightness.

The changes and executed validation are recorded below. Additional recurring infrastructure cost: $0/month.

## Implemented layout

`components/employees/ProfileHeader.jsx` owns three ordered sections: decorative cover; identity/avatar/actions; optional tabs. The cover has explicit responsive height. Only the avatar slot has a negative half-height margin; identity and actions have normal-flow grid positions and positive padding. Names, titles and department names wrap, including long unbroken names. Actions wrap without displacing the identity; tabs keep their existing horizontal scrolling and keyboard behavior. Scoped action CSS cannot affect other pages.

EmployeeDetails and MyProfile use this component. Existing employee cover, tenant-banner fallback and gradient overlays remain unchanged. MyProfile's cover-upload control is in the actions section; its handler, accepted file types and pending/disabled behavior are preserved. The public-profile link uses the existing Button `as={Link}` support to avoid nesting an interactive button inside a link. Photo uploading, alt text, object-cover cropping, avatar shape and initials fallback retain their existing implementations. No employee/action permissions or API calls were changed.

EmployeeHome's distinct welcome hero remains a hero; only its compact person strip gains shrinkable, wrapping text. Its personalization modal, company branding settings and all profile routes remain unchanged. Payroll currently displays the existing “Payroll is not connected” placeholder; this task neither adds payroll access nor claims to test an integration that does not exist. No localization layer or translated-label configuration was found in these screens.

## Browser evidence

Synthetic desktop baseline after entrance animations settled: employee name top 229px versus cover bottom 249px (20px overlap); MyProfile name top 241px versus cover bottom 249px (8px overlap). At 768px, wrapped action buttons can instead extend into the banner, even when the name happens to sit below it. Before screenshots preserve this difference.

| Width | Employee details | My Profile |
|---|---|---|
| 320 | Geometry and content variants pass | Geometry and content variants pass |
| 390 | Geometry and content variants pass | Geometry and content variants pass |
| 768 | Geometry and content variants pass | Geometry and content variants pass |
| 1024 | Geometry and content variants pass | Geometry and content variants pass |
| 1440 | Geometry and content variants pass | Geometry and content variants pass |
| 1920 | Geometry and content variants pass | Geometry and content variants pass |

Each viewport checks default content, long names/title/department, an unbroken long name, missing job/department and short name, active/inactive/probation states, read-only actions, custom avatar/cover, and tenant-banner fallback. Bounding-box assertions require the identity, name/status and every action to start below the cover bottom; avatar/identity/actions must not intersect, and tabs must follow the full body. Page width must remain within the viewport. Custom images use generated SVG data, not customer photos. These are intercepted-API browser tests of actual application pages, not authenticated backend or production acceptance.

Twenty initial browser scenarios passed in 2.3 minutes: the content matrix, six reduced-CSS-viewport zoom reflow scenarios, action dialogs, keyboard tab navigation, time-off/attendance/payroll tabs, public-profile routing and homepage personalization. Axe scans of both headers at all six widths found zero violations in the scanned scope. All matrix pages recorded zero JavaScript exceptions. Complete screen-reader, Safari/iOS and whole-application WCAG certification are not claimed.

## Functionality and validation boundary

Existing employee/profile retrieval, editing, access provisioning/linking, homepage branding upload and profile-image upload unit tests are retained. The MyProfile test now checks both photo and cover upload calls. New unit tests verify semantic section order, identity/status placement, decorative cover isolation, actions/tabs, initials and custom-avatar alt text. Browser tests open all three employee action dialogs and preserve route/tab behavior without writing any real records.

An initial browser harness matched Vite source-module paths as APIs; it was corrected to match only `/api/`. The original IDE dependency tree was missing PDF.js, so the complete existing installation was reused. A borrowed dependency symlink later caused one unrelated PDF worker import to be denied in the full unit run; worktree-local dependencies resolve that environment issue. No package manifest or lockfile was changed to work around these failures. After copying the existing dependencies into this isolated worktree, the complete rerun passed.

## Reproduction

Use the repository lockfiles (`npm ci` in frontend and frontend/e2e), the existing Chromium Playwright installation, and a local Vite server on port 5193 with `VITE_API_BASE_URL=/api`. From `frontend/e2e`, run `npx playwright test --config profile-header.config.js`. No backend, credentials or database is required: all API responses are explicitly synthetic. This dedicated suite lives outside the default `tests` directory, so it does not alter the existing authenticated browser CI setup.

The native-zoom tests use a temporary local-only Chromium extension to call the browser's tab-zoom API; no extension or dependency is shipped with the application. Temporary browser profiles/extensions are removed after each test. The six reduced-viewport tests are separately labeled reflow equivalents and are not represented as native zoom.

## Release boundary

No code was pushed, merged or deployed. No production employee records, tenant settings, database schema, backend code or infrastructure was changed. Existing IDE modifications and PR #78 remain untouched. Additional recurring infrastructure cost: **$0/month**. Reverting the frontend changes restores the prior layout without any data or schema rollback.


## Final validation and screenshots

- **235 frontend tests passed, 75 files**, two workers, 86.19 seconds; includes profile editing, access provisioning/linking, branding configuration, both profile-image upload handlers and the new shared-header tests.
- **20 browser layout/interaction scenarios passed**; 72 page/content/width combinations plus six reflow-equivalent checks and the workflow/homepage scenarios.
- **3 native Chromium zoom scenarios passed**, each testing both pages at 125%, 150% or 200%; the test verifies actual browser tab zoom, changed devicePixelRatio and reduced CSS viewport width before checking geometry. These are not CSS/pinch-zoom substitutes.
- **12 scoped axe scans: zero violations**, covering both profile headers at all six requested widths. Canvas/image data and all employee records are synthetic. No page JavaScript exceptions in the matrix.
- **ESLint, production Vite build (`VITE_API_BASE_URL=/api`) and `git diff --check` passed.** Existing React Router/test `act` warnings and the approximately 1.3 MB bundle warning remain. No unresolved test or layout failure remains.

| View | Before | After |
|---|---|---|
| Employee details, desktop | [Original overlap](profile-header-evidence/before-employee-1440.png) | [Corrected identity/actions](profile-header-evidence/after-employee-1440-default.png) |
| My Profile, desktop | [Original overlap](profile-header-evidence/before-self-1440.png) | [Corrected identity/actions](profile-header-evidence/after-self-1440-default.png) |
| Employee details, mobile | — | [320px](profile-header-evidence/after-employee-320-default.png) · [390px long name](profile-header-evidence/after-employee-390-long.png) |
| My Profile, mobile | — | [320px](profile-header-evidence/after-self-320-default.png) · [390px long name](profile-header-evidence/after-self-390-long.png) |

Modified application paths: `frontend/src/components/employees/ProfileHeader.jsx`, its scoped `ProfileHeader.css`, and `frontend/src/pages/{EmployeeDetails,MyProfile,EmployeeHome}.jsx`. Test changes: `frontend/src/tests/{ProfileHeader,MyProfile}.test.jsx`, `frontend/e2e/profile-header.config.js`, and `frontend/e2e/profile-header/{fixtures,geometry,layout.spec,zoom.spec}.js`. This report and the synthetic screenshots complete the review artifacts.

The original reference screenshot was described in the task but not supplied as an image file; before/after evidence comes from the repository's actual UI. Visual and mocked interaction verification does not certify production authentication, backend storage writes, real-device touch behavior, Safari/iOS or a complete accessibility audit. No separate native localization behavior exists to certify. **Ready for review; publication and deployment require explicit approval.**
