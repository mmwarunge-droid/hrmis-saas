# Kinetic HR Platform — BambooHR-Inspired Redesign

## 1. Executive summary

This redesign retains the existing React/Vite and Flask application architecture while replacing the fragmented, high-radius, gradient-heavy interface with a compact enterprise HR workspace inspired by the navigation density, page hierarchy, profile organization, and task-oriented workflows observed in the supplied BambooHR recordings.

The implementation uses original Kinetic branding, a blue visual system, Lucide icons, and existing application data. No BambooHR logo, trademark, copy, proprietary illustration, or source asset is included.

### Delivered in this pass

- New responsive application shell with grouped, permission-aware sidebar navigation.
- Collapsible desktop navigation and accessible mobile drawer.
- Utility header with page context, global keyboard search, notifications, tenant context, and account actions.
- Kinetic logo and complete user-facing Ace → Kinetic migration.
- New compact dashboard using the existing employee, leave, dashboard, and task APIs.
- Rebuilt People directory with search, filters, sorting, pagination, bulk selection, card/table views, and existing CRUD workflows.
- Rebuilt employee profile with a cover summary and horizontal tabs for personal, job, time off, attendance, files, payroll, performance, notes, and activity.
- Reworked Files, Attendance, Onboarding, Access & Users, Settings, Employee Experience, Signatures, Departments, Time Off, Tasks, Organizations, and Org Chart surfaces through the shared design system and targeted page updates.
- Shared table, form, modal, card, badge, avatar, pagination, tabs, skeleton, empty-state, alert, and button primitives.
- Responsive, reduced-motion, keyboard, focus, loading, and empty-state behavior.
- Existing API paths, backend service contracts, authentication, RBAC, tenant scoping, signature provider keys, and legacy deep links preserved.

## 2. Source analysis

### Reference recordings

Seven supplied recordings were reviewed. The recurring interaction patterns were:

1. A narrow white sidebar with simple icon-and-label navigation, a clear active state, and a collapse affordance.
2. A lightweight utility bar containing search, contextual actions, notifications, and user controls.
3. Compact white cards on a quiet gray canvas rather than large marketing-style hero sections.
4. Data-dense tables with restrained headers, direct row actions, and low visual noise.
5. Employee profiles organized around a strong identity header and horizontal tab navigation.
6. Forms grouped into short semantic sections with persistent cancel/save actions.
7. Modal and inline workflows for focused edits instead of frequent full-page navigation.
8. Information hierarchy driven by spacing, typography, and alignment more than decoration.

### Existing repository

#### Frontend

- React 19 and React Router 6.
- Vite and Tailwind CSS.
- Axios API client modules.
- Auth and tenant context providers.
- Permission and role route guards.
- Existing reusable domain forms for employees, leave, documents, signatures, organizations, security, and users.
- Twenty-seven page modules and forty-plus reusable component modules.

#### Backend

- Flask application factory.
- JWT authentication and MFA.
- Tenant isolation and role-based permissions.
- Employee, department, leave, attendance, documents, signatures, onboarding, users, organizations, dashboard, and employee-home services.
- Existing email, notification, evidence, and provider workflows.

### Architectural decision

The redesign is intentionally frontend-led. Existing backend domain logic and routes remain the source of truth. Backend changes are limited to user-facing Kinetic naming in configuration, email text, validation messages, signature status copy, and documentation.

## 3. Gap analysis

| Area | Previous state | Kinetic target | Implementation |
|---|---|---|---|
| Application shell | Dark/gradient-heavy surfaces and uneven navigation hierarchy | Quiet white sidebar, slim utility header, grouped workspace navigation | Rebuilt `Sidebar`, `Navbar`, and `DashboardLayout` |
| Navigation | Flat links with limited page context | BambooHR-like grouped navigation, active states, responsive collapse, permission visibility | Centralized in `config/navigation.js` |
| Global search | No unified application navigation search | Command-style search from header with Ctrl/Cmd+K | Added `GlobalSearch` |
| Dashboard | Large promotional presentation and inconsistent card density | Compact KPI row, actions, approvals, events, and activity | Rebuilt `Dashboard.jsx` |
| People directory | Basic listing | Search, filters, sorting, pagination, bulk actions, table/card density | Rebuilt `Employees.jsx` |
| Employee profile | Vertical collection of information | Identity cover, summary, horizontal tabs, domain panels | Rebuilt `EmployeeDetails.jsx` |
| Tables | Static rendering and inconsistent spacing | Sortable, keyboard-enabled, loading, compact density, pagination | Rebuilt shared `Table` and added `Pagination` |
| Forms | Inconsistent controls and focus treatment | Unified labels, help/error text, focus rings, compact spacing | Rebuilt shared inputs/selects/buttons and retained domain forms |
| Dialogs | Inconsistent sizing and dismissal behavior | Accessible header, backdrop, keyboard dismissal, responsive sizing | Rebuilt shared `Modal` |
| Loading | Large generic pulses or absent loading feedback | Page and component skeletons | Added `Skeleton`; integrated in tables, shell, stats, and key pages |
| Empty states | Plain text or missing | Consistent descriptive empty states with optional action | Rebuilt `EmptyState` |
| Visual system | Cyan/violet mixtures, oversized radii, strong gradients | Original Kinetic blue, 8–12px radii, quiet borders, subtle shadows | New tokens and global class normalization |
| Branding | Ace references across UI, legal, email, MFA, signature copy, metadata | Kinetic throughout user-facing product | Migrated all user-facing references |
| Compatibility | Risk of replacing working architecture | Preserve APIs, routes, RBAC, tenant data, provider values | Compatibility aliases and internal keys retained |

## 4. Information architecture

### Workspace

- Home
- My info
- My tasks
- Ask Kinetic

### People

- People
- Org chart
- Departments

### Time

- Time off
- Attendance

### Workflows

- Files
- Signatures
- Onboarding

### Administration

- Organizations
- Access & users
- Employee experience
- Settings

Visibility is resolved from existing permissions and roles. The navigation config is also the source for global search and page titles, reducing drift between routing and presentation.

## 5. Page-by-page redesign plan and status

### Authentication

- Kinetic brand panel, product value statement, security cues, and compact authentication card.
- Existing login, MFA, password reset, and email verification flows preserved.
- Responsive single-column behavior on smaller screens.

### Home / Dashboard

- Compact welcome context rather than a dominant marketing hero.
- KPI cards for headcount, leave, tasks, and operational status.
- Quick actions and approval queues using existing permissions.
- Upcoming activity and organization context in balanced columns.

### Employee Home

- Organization-branded but more compact cover surface.
- Profile summary, quick actions, Ask Kinetic handoff, events, birthdays, new hires, people out, essentials, anniversaries, and protected people insights.
- Existing organization configuration and employee profile edit flows preserved.

### People

- Default table view with search, status/department filters, sortable columns, pagination, and bulk selection.
- Optional card view for visual browsing.
- Add employee, edit, provision access, transfer, and department workflows retained.

### Employee Profile

- Identity header with avatar, job context, status, manager, department, and primary actions.
- Tabs: Personal, Job, Time off, Attendance, Files, Payroll, Performance, Notes, Activity.
- Existing APIs power personal, job, leave, attendance, documents, and activity views.
- Payroll and performance panels explicitly identify that no dedicated API currently exists; the UI does not fabricate records.

### Time Off

- Existing request, approval, balance, ledger, setup, and calendar flows retained.
- Shared compact cards, form controls, status badges, alerts, and modal styling applied.

### Attendance

- Check-in/check-out actions remain permission-aware.
- Summary cards plus sortable, paginated attendance table.
- Loading and self-service-only states included.

### Files and Signatures

- “Files” terminology is used consistently in navigation and page copy.
- Folder/search/filter/upload workflows preserved.
- Signature request, provider handoff, evidence, internal signing, and QES behavior retained.
- All user-facing provider explanations now refer to Kinetic.

### Onboarding and Tasks

- Onboarding now has a dedicated page header, progress metrics, status badges, completion feedback, sorting, and pagination.
- Existing task completion API remains unchanged.
- Combined task workspace retains onboarding and signature task flows.

### Administration

- Departments, organizations, access/users, employee experience, and security settings use the same information hierarchy and control density.
- User access adds search across person, email, role, and organization.
- Existing MFA policy, tenant provisioning, employee-experience branding, events, and essential-document workflows remain intact.

## 6. Kinetic design system

### Color

- Primary: blue 600–800.
- Interactive wash: blue 50–100.
- Canvas: neutral gray `#f4f6f8`.
- Surface: white.
- Borders: slate 200.
- Text: slate 950 / slate 500.
- Semantic statuses: emerald, amber, rose, slate.

### Typography

- System-first sans-serif stack for performance and platform consistency.
- Page title: 28px desktop, 24px small screens.
- Section title: 18–20px.
- Body: 14px with 20–24px line height.
- Label: 13px semibold.
- Eyebrow/table header: 10–11px uppercase with restrained tracking.

### Spacing and grid

- Base spacing unit: 4px.
- Page stack: 24px.
- Card padding: 16–20px.
- Dense table cells: 10px vertical; comfortable cells: 14px.
- Responsive grids collapse to one column before content becomes compressed.

### Shape and elevation

- Primary radius: 12px.
- Control radius: 8px.
- Avatars and status pills may remain circular.
- Shadows are limited to a subtle one-pixel surface lift.

### Interaction

- Blue focus rings with visible keyboard states.
- Hover states use color and subtle background change rather than large movement.
- Row interactions support Enter and Space.
- Modals support Escape and backdrop dismissal.
- Page and drawer transitions are 180ms and disabled under reduced-motion preferences.

### Reusable components

- `KineticLogo`
- `GlobalSearch`
- `Button`
- `Card`
- `Input`
- `Select`
- `Modal`
- `PageHeader`
- `StatCard`
- `Badge`
- `Avatar`
- `Alert`
- `EmptyState`
- `Spinner`
- `Skeleton`
- `Table`
- `Pagination`
- `Tabs`

## 7. Branding migration

### Replaced

- Product and browser title.
- Login and authentication copy.
- Dashboard and navigation labels.
- Employee-help experience (“Ask Kinetic”).
- Legal privacy and terms content.
- Environment defaults.
- Password recovery and email-verification subjects/bodies.
- MFA TOTP issuer default.
- Signature and evidence workflow messages.
- Backend validation messages.
- Tests and engineering documentation.

### Intentionally retained for backward compatibility

- `/ask-ace` as a redirect to `/ask-kinetic` so existing bookmarks do not break.
- `ace.activeTenantId` as a one-time legacy storage key read during migration.
- Internal signature provider value `ace`, because persisted records and callback routing depend on that stable contract.
- Existing test fixture IDs such as `ace-request-1`, because they are opaque identifiers rather than user-facing product names.

No retained compatibility value is rendered as product branding.

## 8. Incremental migration roadmap

### Phase 0 — Inventory and safeguards

- Map routes, contexts, API modules, role guards, and reusable components.
- Review supplied reference recordings.
- Record baseline repository state.

### Phase 1 — Foundations (implemented)

- Tokens, typography, canvas, spacing, radius, focus, motion.
- Shared UI primitives.
- Application shell, navigation config, header, search, tenant and account controls.
- Kinetic branding migration.

### Phase 2 — Core people workflows (implemented)

- Dashboard.
- People directory.
- Employee profile.
- Files.
- Time off and attendance consistency.

### Phase 3 — Operational workflows (implemented in shared system; targeted upgrades included)

- Tasks and onboarding.
- Signatures.
- Departments and org chart.
- Organizations and access/users.
- Employee experience and settings.

### Phase 4 — Recommended next backend-enabled work

- Add dedicated payroll domain APIs and permission scopes.
- Add performance review cycles, goals, feedback, and rating APIs.
- Enrich onboarding assignment responses with task title/description to avoid displaying an opaque task reference.
- Add server-side table pagination/filtering for very large tenants.
- Add notification read/unread and command-search APIs if cross-entity search expands beyond navigation.

## 9. Regression strategy

### Static validation completed

- All frontend JavaScript/JSX files parse successfully through the TypeScript parser.
- All relative frontend imports resolve to repository files.
- Python backend modules compile successfully.
- Git whitespace/error validation passes.
- Brand scan confirms only documented internal compatibility values retain the old token.

### Functional regression matrix

| Capability | Required check |
|---|---|
| Authentication | Login, logout, protected routes, MFA challenge/enrollment, reset, verify email |
| Tenant isolation | Super-admin tenant selection and scoped API headers |
| Permissions | Sidebar visibility and permission/role route guards |
| Employees | List, filter, sort, paginate, create, edit, transfer, provision access |
| Employee profile | Load each tab; edit; validate unavailable payroll/performance state |
| Leave | Request, approve/reject, balance, ledger, policy setup |
| Attendance | Check in, check out, list visibility by permission |
| Files | Search, folder filter, upload, download, approval flows |
| Signatures | Standard internal signing, provider handoff, QES evidence, cancellation |
| Tasks/onboarding | Load, complete, refresh status |
| Administration | Tenant provision, user create, department archive/transfer, MFA policy |
| Responsive | Sidebar drawer, header actions, tables, profile tabs, modals |
| Accessibility | Keyboard navigation, focus visibility, labels, status semantics, reduced motion |

### Environment limitation

Automated npm and pytest suites could not be executed in the provided environment because the configured package registries did not expose the repository’s pinned npm or Python packages. This is an environment dependency-resolution issue, not a reported test failure. Run the commands below in the project’s normal CI environment:

```bash
cd frontend
npm ci
npm run lint
npm test
npm run build

cd ../backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
ruff check app
```

## 10. Acceptance criteria

The redesign is considered accepted when:

1. Every existing protected route remains reachable for the same roles and permissions.
2. Existing API calls and payloads remain compatible.
3. No user-facing Ace product reference remains.
4. Desktop, tablet, and mobile navigation are usable without horizontal shell overflow.
5. Tables expose search/filter/sort/pagination where data volume warrants it.
6. Employee identity and domain information are discoverable through the profile tabs.
7. Empty, loading, error, success, focus, hover, and disabled states are visible and consistent.
8. Authentication, tenant isolation, leave, attendance, files, signatures, onboarding, and administration pass the regression matrix.
