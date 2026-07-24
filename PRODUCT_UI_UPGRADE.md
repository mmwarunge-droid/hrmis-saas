# People Experience Upgrade

This implementation translates the supplied HR platform references into an original HRMIS experience rather than reproducing another product's interface.

## Delivered in this upgrade

### People-first workspace
- Branded navigation shell with grouped modules, global search, profile context and responsive mobile navigation.
- Action-led homepage with workforce KPIs, compliance alerts, recent hires, upcoming leave and a visual organization pulse.
- Infographic components built with lightweight SVG and CSS; no charting dependency was introduced.

### People and organization
- Searchable people directory with card/list views, quick filters, department and location context.
- Interactive-style organization chart generated from employee manager relationships.
- Modern employee cards and clearer status signals.

### Time, documents and tasks
- Calendar-led time-off workspace with approved leave overlays, balances and an approval queue.
- Folder-led document library with signature, expiry and access-state indicators.
- Unified personal task queue for onboarding and employee workflow actions.
- Updated attendance workspace with self-service check-in/out and daily status indicators.

### Multi-tenant administration
- New super-admin Organizations workspace.
- Atomic organization provisioning creates:
  1. the tenant workspace; and
  2. the first `CLIENT_ADMIN`.
- Organization administrators can create `MANAGER` and `EMPLOYEE` accounts.
- Employee accounts can be created together with their employee profile in one transaction.
- Tenant-scoped administrators cannot grant `CLIENT_ADMIN` or `SUPER_ADMIN`.

## API additions

### `POST /api/tenants/provision`

Creates an organization and its first administrator.

```json
{
  "organization": {
    "name": "Northstar Logistics",
    "slug": "northstar-logistics",
    "legal_name": "Northstar Logistics Limited",
    "country": "Kenya",
    "industry": "Logistics",
    "compliance_region": "East Africa"
  },
  "admin": {
    "first_name": "Amina",
    "last_name": "Otieno",
    "email": "admin@northstar.example",
    "password": "temporary-strong-password"
  }
}
```

### `POST /api/users`

Now accepts an optional `employee_profile` object. When supplied, the user account and employee record are committed atomically.

## Suggested next product phases

1. Announcements, birthdays, anniversaries and social recognition feed.
2. Configurable workflow builder for onboarding, offboarding and employee changes.
3. Position management, headcount planning and vacancy visualization.
4. Goals, continuous feedback, performance reviews and talent calibration.
5. Custom reporting builder with saved dashboards and scheduled exports.
6. Electronic signatures and policy acknowledgement campaigns.
7. Recruiting and applicant tracking.
8. Payroll and benefits connectors.
