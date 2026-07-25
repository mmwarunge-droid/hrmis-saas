# Department Management and Workforce Transfers

The department workspace gives organization administrators a controlled way to maintain the operating structure as people join, transfer, receive promotions, or leave.

## Product workflow

- **Administration → Departments** creates, edits, archives, restores, and assigns department heads.
- **People directory → select employees → Change department** performs an atomic bulk transfer.
- **Employee profile → Edit employment details** updates department, manager, title, status, location, effective date, and change reason.
- Employment history records department, manager, and title changes with their effective dates and reasons.

Assigning a department head automatically places the selected employee in that department. Moving or terminating a department head clears the leadership assignment so stale department ownership is not displayed.

## API additions

```text
GET    /api/employees/departments?include_archived=true
POST   /api/employees/departments
PATCH  /api/employees/departments/<department_id>
POST   /api/employees/departments/<department_id>/archive
POST   /api/employees/departments/<department_id>/restore
POST   /api/employees/bulk-department-transfer
GET    /api/employees/<employee_id>/job-history
```

Bulk transfer payload:

```json
{
  "employee_ids": ["employee-uuid-1", "employee-uuid-2"],
  "department_id": "department-uuid",
  "effective_date": "2026-07-25",
  "reason": "Operating model restructure"
}
```

Use `null` for `department_id` to move employees into the unassigned pool. Transfers are tenant-scoped and atomic. The effective date cannot be in the future or before an employee's hire date.

## Deployment

Migration `008_department_management` adds the optional department-head relationship. Render runs `flask --app run.py db upgrade` through the existing pre-deploy command.
