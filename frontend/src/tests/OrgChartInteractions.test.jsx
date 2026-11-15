import { act, render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import OrgChart from '../pages/OrgChart';
import { employeeApi } from '../api/employeeApi';
import { AuthContext } from '../context/AuthContext';
import { TenantContext } from '../context/TenantContext';
vi.mock('../api/employeeApi', () => ({
  employeeApi: { orgChart: vi.fn(), update: vi.fn() },
}));
const items = [
  {
    id: 'a',
    full_name: 'Amina Leader',
    job_title: 'CEO',
    department_name: 'Leadership',
    employment_status: 'active',
    direct_report_count: 1,
    indirect_report_count: 1,
  },
  {
    id: 'b',
    manager_id: 'a',
    full_name: 'Brian Manager',
    department_name: 'Engineering',
    employment_status: 'active',
    direct_report_count: 1,
    indirect_report_count: 0,
  },
  {
    id: 'c',
    manager_id: 'b',
    full_name: 'Carol Engineer',
    department_name: 'Engineering',
    employment_status: 'probation',
    direct_report_count: 0,
    indirect_report_count: 0,
  },
];
const auth = {
  user: { id: 'u', permissions: ['employee:read', 'employee:update'] },
};
const renderChart = (tenantId = 'one') =>
  render(
    <AuthContext.Provider value={auth}>
      <TenantContext.Provider value={{ tenantId }}>
        <MemoryRouter>
          <OrgChart />
        </MemoryRouter>
      </TenantContext.Provider>
    </AuthContext.Provider>,
  );
beforeEach(() => {
  vi.clearAllMocks();
  employeeApi.orgChart.mockResolvedValue({
    data: { items, meta: { total: 3, manager_count: 2 } },
  });
});
test('search reveals ancestors, selection opens details, filters and layout preserve selection', async () => {
  const user = userEvent.setup();
  renderChart();
  await screen.findByRole('button', { name: 'View Amina Leader' });
  expect(
    screen.queryByRole('button', { name: 'View Carol Engineer' }),
  ).not.toBeInTheDocument();
  await user.type(
    screen.getByPlaceholderText('Search people, roles or departments'),
    'Carol',
  );
  await user.click(
    await screen.findByRole('button', {
      name: 'Carol Engineer · Role not assigned',
    }),
  );
  const panel = screen.getByRole('complementary', { name: 'Employee details' });
  expect(within(panel).getByText('Carol Engineer')).toBeInTheDocument();
  expect(
    within(panel).getByRole('link', { name: 'View employee profile' }),
  ).toHaveAttribute('href', '/employees/c');
  await user.click(screen.getByText('View settings and filters'));
  await user.selectOptions(screen.getByLabelText('Layout'), 'stacked');
  expect(within(panel).getByText('Carol Engineer')).toBeInTheDocument();
  await user.selectOptions(
    screen.getByLabelText('Filter Department'),
    'Engineering',
  );
  expect(screen.getByText(/2 matching employees/)).toBeInTheDocument();
  await user.click(
    within(panel).getAllByRole('button', { name: 'Brian Manager' })[0],
  );
  expect(within(panel).getByText('Brian Manager')).toBeInTheDocument();
  await user.click(
    within(panel).getByRole('button', { name: 'Close employee details' }),
  );
  expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  expect(employeeApi.orgChart).toHaveBeenCalledTimes(1);
});
test('authorized manager change confirms through existing API and refreshes', async () => {
  const user = userEvent.setup();
  employeeApi.update.mockResolvedValue({ data: {} });
  renderChart();
  await user.click(
    await screen.findByRole('button', { name: 'View Brian Manager' }),
  );
  await user.click(
    screen.getByRole('button', { name: 'Change reporting manager' }),
  );
  expect(
    screen.queryByRole('option', { name: 'Carol Engineer' }),
  ).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('New reporting manager'), '');
  await user.click(screen.getByRole('button', { name: 'Confirm change' }));
  await waitFor(() =>
    expect(employeeApi.update).toHaveBeenCalledWith('b', { manager_id: null }),
  );
  await waitFor(() => expect(employeeApi.orgChart).toHaveBeenCalledTimes(2));
});
test('failed fetch offers retry and no misleading empty state', async () => {
  employeeApi.orgChart.mockRejectedValueOnce(new Error('offline'));
  const user = userEvent.setup();
  renderChart();
  await user.click(await screen.findByRole('button', { name: 'Retry' }));
  await screen.findByRole('button', { name: 'View Amina Leader' });
});

test('switching tenant clears old results and ignores an outdated pending response', async () => {
  let resolveFirst;
  employeeApi.orgChart.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveFirst = resolve;
      }),
  );
  const wrapper = (tenantId) => (
    <AuthContext.Provider value={auth}>
      <TenantContext.Provider value={{ tenantId }}>
        <MemoryRouter>
          <OrgChart />
        </MemoryRouter>
      </TenantContext.Provider>
    </AuthContext.Provider>
  );
  const view = render(wrapper('one'));
  view.rerender(wrapper('two'));
  await screen.findByRole('button', { name: 'View Amina Leader' });
  await act(async () => {
    resolveFirst({
      data: { items: [{ id: 'private', full_name: 'Previous tenant person' }] },
    });
  });
  await waitFor(() =>
    expect(
      screen.queryByText('Previous tenant person'),
    ).not.toBeInTheDocument(),
  );
  expect(employeeApi.orgChart).toHaveBeenCalledTimes(2);
});

test('read-only users have no manager mutation action', async () => {
  const user = userEvent.setup();
  render(
    <AuthContext.Provider
      value={{ user: { id: 'read', permissions: ['employee:read'] } }}
    >
      <MemoryRouter>
        <OrgChart />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
  await user.click(
    await screen.findByRole('button', { name: 'View Amina Leader' }),
  );
  expect(
    screen.queryByRole('button', { name: 'Change reporting manager' }),
  ).not.toBeInTheDocument();
});
