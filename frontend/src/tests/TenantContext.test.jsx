import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { tenantApi } from '../api/tenantApi.js';
import { AuthContext } from '../context/AuthContext.jsx';
import {
  TenantContext,
  TenantProvider,
} from '../context/TenantContext.jsx';
import {
  ACTIVE_TENANT_STORAGE_KEY,
} from '../utils/tenantScope.js';

vi.mock('../api/tenantApi.js', () => ({
  tenantApi: {
    options: vi.fn(),
    list: vi.fn(),
  },
}));

const tenants = [
  {
    id: 'tenant-1',
    name: 'Dundaa Labs Limited',
    status: 'active',
  },
  {
    id: 'tenant-2',
    name: 'James HR Consulting',
    status: 'active',
  },
];

function Consumer() {
  return (
    <TenantContext.Consumer>
      {(context) => (
        <div>
          <span>
            {context.loading
              ? 'loading'
              : `${context.tenantId || 'none'}:${context.tenants.length}`}
          </span>
          <button
            type="button"
            onClick={() => context.setTenantId('tenant-1')}
          >
            Select tenant
          </button>
        </div>
      )}
    </TenantContext.Consumer>
  );
}

function renderProvider(user) {
  return render(
    <AuthContext.Provider
      value={{
        user,
        loading: false,
      }}
    >
      <TenantProvider>
        <Consumer />
      </TenantProvider>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
  tenantApi.options.mockResolvedValue({
    data: {
      items: tenants,
    },
  });
});

test('does not silently select an organization for a super admin', async () => {
  renderProvider({
    id: 'super-admin-1',
    roles: ['SUPER_ADMIN'],
    tenant_id: null,
  });

  expect(await screen.findByText('none:2')).toBeInTheDocument();
  expect(
    sessionStorage.getItem(ACTIVE_TENANT_STORAGE_KEY),
  ).toBeNull();
});

test('persists a super-admin organization selection for the tab', async () => {
  const view = renderProvider({
    id: 'super-admin-1',
    roles: ['SUPER_ADMIN'],
    tenant_id: null,
  });

  await screen.findByText('none:2');
  fireEvent.click(
    screen.getByRole('button', { name: 'Select tenant' }),
  );

  expect(await screen.findByText('tenant-1:2')).toBeInTheDocument();
  expect(
    sessionStorage.getItem(ACTIVE_TENANT_STORAGE_KEY),
  ).toBe('tenant-1');

  view.unmount();

  renderProvider({
    id: 'super-admin-1',
    roles: ['SUPER_ADMIN'],
    tenant_id: null,
  });

  await waitFor(() => {
    expect(screen.getByText('tenant-1:2')).toBeInTheDocument();
  });
});

test('tenant-bound users use their assigned tenant without storage', async () => {
  sessionStorage.setItem(
    ACTIVE_TENANT_STORAGE_KEY,
    'stale-platform-selection',
  );

  renderProvider({
    id: 'client-admin-1',
    roles: ['CLIENT_ADMIN'],
    tenant_id: 'tenant-2',
  });

  expect(await screen.findByText('tenant-2:0')).toBeInTheDocument();
  expect(tenantApi.options).not.toHaveBeenCalled();
  expect(
    sessionStorage.getItem(ACTIVE_TENANT_STORAGE_KEY),
  ).toBeNull();
});
