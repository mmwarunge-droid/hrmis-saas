# Kinetic deterministic demo environment

The demo environment is a local and non-production dataset for repeatable product walkthroughs, screenshots, UAT and sales rehearsals. Every person, organization, document and workflow is fictional.

## Safety boundaries

- Demo seeding and reset commands refuse to run when `APP_ENV=production`.
- Reset removes only these managed organization slugs: `kinetic-demo`, `northstar-sandbox` and `archive-collective`.
- Reset also removes accounts in the `@kinetic.demo` domain.
- The commands do not truncate shared role, permission or unrelated tenant data.
- Do not reuse the demo password or TOTP secret outside a disposable environment.

## Configure local credentials

Add these values to `backend/.env`:

```dotenv
DEMO_PASSWORD=KineticDemo2026!
# Optional. Omit to anchor relative records to the day the command runs.
DEMO_REFERENCE_DATE=2026-08-06
# Local demo TOTP only. Replace this value in any shared environment.
DEMO_MFA_SECRET=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP
```

The reference date controls attendance, upcoming leave, events, birthdays, anniversaries, recent hires and document-expiry dates. Use the same date for repeatable screenshots. Use the current date for a live demonstration so time-sensitive cards remain populated.

## Create or refresh deterministic records

From `backend/`:

```bash
flask --app run.py db upgrade
flask --app run.py demo-seed --as-of 2026-08-06
flask --app run.py demo-status --as-of 2026-08-06
```

`demo-seed` is idempotent for a given reference date. It restores deterministic records by stable UUID without duplicating them. It does not remove extra records created during a demonstration.

The legacy convenience entry point now loads the same rich dataset:

```bash
python seed.py
```

## Reset after a walkthrough

```bash
flask --app run.py demo-reset --yes --as-of 2026-08-06
```

The reset command deletes only managed demo tenants, users and their generated local files, then recreates the baseline. The repository helper performs the migration, reset and status checks in one operation:

```bash
../scripts/reset_demo.sh 2026-08-06
```

## Baseline dataset

The primary `Kinetic Demo Group` workspace contains:

- 42 employees across 7 departments;
- 40 governed documents, including 5 pending acknowledgements;
- 320 attendance records across 8 business days;
- 10 leave requests in pending, approved, rejected and cancelled states;
- 4 leave policies and reconciled annual/sick balances;
- 2 signature workflows;
- 2 onboarding templates and 15 employee task assignments;
- 9 organization, department, and employee goals with 15 progress check-ins;
- employee-home events, essentials, recent hires, birthdays and people statistics;
- notifications and audit events for presentation context.

Two additional workspaces demonstrate lifecycle state: one suspended sandbox and one archived organization.

## Demo account matrix

All active accounts use `DEMO_PASSWORD`.

| Account | Role | Recommended use | MFA |
|---|---|---|---|
| `platform@kinetic.demo` | SUPER ADMIN | Organization lifecycle and platform scope | Yes |
| `owner@kinetic.demo` | ORGANIZATION OWNER | Governance and owner approval | No |
| `consultant@kinetic.demo` | HR CONSULTANT | Primary admin walkthrough | No |
| `admin@kinetic.demo` | CLIENT ADMIN | Tenant administration and MFA controls | Yes |
| `manager@kinetic.demo` | MANAGER | Revenue team approvals and scoped records | No |
| `manager.ops@kinetic.demo` | MANAGER | Operations team scope | No |
| `employee@kinetic.demo` | EMPLOYEE | Self-service leave, attendance and signing | No |
| `newhire@kinetic.demo` | EMPLOYEE | Onboarding and employee-home story | No |
| `inactive@kinetic.demo` | EMPLOYEE | Deactivated-account lifecycle state | No |
| `sandbox.admin@kinetic.demo` | CLIENT ADMIN | Suspended-workspace login rejection | Yes |

Generate the current TOTP code for a privileged demo account:

```bash
flask --app run.py demo-mfa-code --email platform@kinetic.demo
flask --app run.py demo-mfa-code --email admin@kinetic.demo
```

The code is intentionally available only in non-production environments and only for the known privileged demo accounts.

## Connected demo story

1. Sign in as `consultant@kinetic.demo` and open the organization dashboard.
2. Review complete employee totals, recent hires, upcoming leave, goal health and expiring documents.
3. Open Goals & KPIs, review at-risk outcomes, and record a progress check-in.
4. Find Neema Hassan in People and review her manager, profile, job history and individual goals.
5. Sign in as `employee@kinetic.demo`, submit or review leave, check out the open attendance session, and acknowledge the security policy.
6. Sign in as `manager@kinetic.demo` and review direct-report leave and document scope.
7. Sign in as `newhire@kinetic.demo` and complete an onboarding task.
8. Sign in as `platform@kinetic.demo` with the generated TOTP code to demonstrate active, suspended and archived workspaces.

## Screenshot and presentation checks

After each reset, verify the following at desktop widths of 1366 px and 1920 px:

- dashboard totals remain stable across pagination;
- People, Files, Attendance, People access and Organizations have populated first pages;
- employee-home essentials, events, birthdays, recent hires and people statistics render without empty placeholders;
- modal forms fit without horizontal clipping;
- table controls and pagination remain visible;
- no real names, email addresses, secrets or customer documents are present.

The React Router future-flag notices and the current Vite bundle-size notice are non-blocking development warnings; no uncaught application error should appear during the walkthrough.
