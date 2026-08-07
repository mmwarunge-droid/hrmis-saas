import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { tenantApi } from '../api/tenantApi.js';
import useTenant from '../hooks/useTenant.js';
import Organizations from '../pages/Organizations.jsx';

vi.mock('../api/tenantApi.js', () => ({
  tenantApi: {
    list: vi.fn(),
    summary: vi.fn(),
    provision: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('../hooks/useTenant.js', () => ({
  default: vi.fn(),
}));

function organization(index) {
  return {
    id: `tenant-${index}`,
    name: `Organization ${String(index).padStart(2, '0')}`,
    slug: `organization-${index}`,
    legal_name: `Organization ${index} Limited`,
    country: index % 2 ? 'Kenya' : 'Uganda',
    industry: 'Technology',
    status: index === 12 ? 'suspended' : 'active',
    billing_plan: 'mvp',
    compliance_region: 'East Africa',
    user_count: index + 10,
    admin_count: 1,
    primary_admin: {
      full_name: `Admin ${index}`,
      email: `admin-${index}@example.test`,
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();

  useTenant.mockReturnValue({
    tenantId: null,
    setTenantId: vi.fn(),
    reloadTenants: vi.fn().mockResolvedValue([]),
  });

  tenantApi.summary.mockResolvedValue({
    data: {
      total: 30,
      active: 27,
      suspended: 2,
      archived: 1,
      users: 480,
      admins: 30,
    },
  });
  tenantApi.list.mockImplementation((params) => {
    const page = params.page || 1;
    const start = ((page - 1) * 12) + 1;
    return Promise.resolve({
      data: {
        items: Array.from(
          { length: page === 3 ? 6 : 12 },
          (_, offset) => organization(start + offset),
        ),
        meta: {
          page,
          per_page: 12,
          total: 30,
          pages: 3,
        },
      },
    });
  });
  tenantApi.update.mockResolvedValue({
    data: {
      ...organization(1),
      status: 'suspended',
      revoked_sessions: 4,
    },
  });
});

test('uses platform-wide organization totals and server pagination', async () => {
  render(
    <MemoryRouter>
      <Organizations />
    </MemoryRouter>,
  );

  expect(
    await screen.findByText('Showing 12 of 30 matching organizations'),
  ).toBeInTheDocument();
  expect(screen.getByText('1–12 of 30 organizations')).toBeInTheDocument();
  expect(screen.getByText('Tenant users').closest('section'))
    .toHaveTextContent('480');

  fireEvent.click(screen.getByRole('button', { name: /next page/i }));
  await waitFor(() => {
    expect(tenantApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, per_page: 12 }),
    );
  });

  fireEvent.change(screen.getByLabelText('Search organizations'), {
    target: { value: 'Kenya' },
  });
  await waitFor(() => {
    expect(tenantApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, q: 'Kenya' }),
    );
  });

  fireEvent.change(screen.getByLabelText('Sort organizations'), {
    target: { value: 'people:desc' },
  });
  await waitFor(() => {
    expect(tenantApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'people', direction: 'desc' }),
    );
  });
});

test('updates organization lifecycle status from the management dialog', async () => {
  render(
    <MemoryRouter>
      <Organizations />
    </MemoryRouter>,
  );

  await screen.findByText('Showing 12 of 30 matching organizations');
  fireEvent.click(
    screen.getByRole('button', { name: 'Manage Organization 01' }),
  );
  fireEvent.change(screen.getByLabelText('Workspace status'), {
    target: { value: 'suspended' },
  });
  expect(
    screen.getByText(/revokes its active user sessions/i),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole('button', { name: 'Save organization' }),
  );

  await waitFor(() => {
    expect(tenantApi.update).toHaveBeenCalledWith(
      'tenant-1',
      expect.objectContaining({
        name: 'Organization 01',
        status: 'suspended',
      }),
    );
  });

  expect(
    await screen.findByText(
      'Organization 01 updated and 4 active sessions revoked.',
    ),
  ).toBeInTheDocument();
});
