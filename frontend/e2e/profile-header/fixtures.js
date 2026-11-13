export const employee = {
  id: 'synthetic-person', tenant_id: 'synthetic-tenant', user_id: null,
  employee_number: 'TEST-001', first_name: 'Mary', last_name: 'Example',
  full_name: 'Mary Example', email: 'mary@example.test', hire_date: '2020-01-01',
  employment_status: 'active', employment_type: 'full_time',
  job_title: 'People Operations Specialist', department_id: 'department',
  department_name: 'People Operations', hobbies: [], work_location: 'Nairobi',
};
export async function mockProfile(page, overrides = {}, readOnly = false, tenantCover = null) {
  const person = { ...employee, ...overrides };
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, '');
    let data = { items: [], meta: { total: 0, pages: 1 }, unread_count: 0 };
    if (path === '/auth/me') data = { id: 'synthetic-user', full_name: 'Test Administrator', roles: ['CLIENT_ADMIN'], permissions: readOnly ? ['employee:read'] : ['employee:read', 'employee:update', 'user:create', 'user:update', 'user:read', 'payroll:read', 'leave:create', 'attendance:read', 'document:read', 'goal:read'] };
    if (path === '/employees/synthetic-person') data = person;
    if (path === '/employees/departments') data = { items: person.department_id ? [{ id: 'department', name: person.department_name }] : [] };
    if (path === '/employee-home') data = { viewer: person, branding: { organization_name: 'Synthetic Organization', banner_url: tenantCover }, enabled_sections: [], section_order: [], sections: {} };
    await route.fulfill({ json: { data } });
  });
  return person;
}
export const coverImage = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="200"><rect width="800" height="200" fill="white"/><path d="M0 0L800 200H0" fill="#101010"/></svg>')}`;
export const avatarImage = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"><rect width="120" height="120" fill="#1d4ed8"/><circle cx="60" cy="45" r="20" fill="white"/><path d="M20 115Q20 65 60 65Q100 65 100 115" fill="white"/></svg>')}`;
