import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { employeeApi } from '../api/employeeApi';
import { leaveApi } from '../api/leaveApi';
import usePermissions from '../hooks/usePermissions.js';
import LeaveRequests from '../pages/LeaveRequests.jsx';

vi.mock('../api/employeeApi', () => ({
  employeeApi: {
    list: vi.fn(),
  },
}));

vi.mock('../api/leaveApi', () => ({
  leaveApi: {
    requests: vi.fn(),
    types: vi.fn(),
    balances: vi.fn(),
    setup: vi.fn(),
    ledger: vi.fn(),
  },
}));

vi.mock('../hooks/usePermissions.js', () => ({
  default: vi.fn(),
}));

vi.mock('../components/leave/LeaveLedgerPanel.jsx', () => ({
  default: () => null,
}));

vi.mock('../components/leave/LeaveRequestForm.jsx', () => ({
  default: () => null,
}));

vi.mock('../components/leave/LeaveSetupPanel.jsx', () => ({
  default: () => null,
}));

vi.mock('../components/ui/Modal.jsx', () => ({
  default: ({ open, children }) => (
    open ? <div>{children}</div> : null
  ),
}));

const missingRequirements = [
  {
    code: 'leave_policies',
    title: 'Configure leave policies',
    description: 'Apply the standard policy pack.',
  },
  {
    code: 'organization_owner',
    title: 'Appoint the business owner',
    description: 'Choose an organization owner approver.',
  },
  {
    code: 'alternate_approver',
    title: 'Appoint an alternate approver',
    description: 'Choose an independent alternate approver.',
  },
];

function configureResponses(canConfigure) {
  usePermissions.mockReturnValue({
    hasPermission: () => false,
  });

  leaveApi.requests.mockResolvedValue({
    data: { items: [] },
  });

  employeeApi.list.mockResolvedValue({
    data: {
      items: [
        {
          id: 'employee-1',
          full_name: 'Employee One',
        },
      ],
    },
  });

  leaveApi.types.mockResolvedValue({
    data: { items: [] },
  });

  leaveApi.balances.mockResolvedValue({
    data: { items: [] },
  });

  leaveApi.ledger.mockResolvedValue({
    data: { items: [] },
  });

  leaveApi.setup.mockResolvedValue({
    data: {
      ready_to_request: false,
      can_configure: canConfigure,
      can_submit_for_others: false,
      current_employee: {
        id: 'employee-1',
      },
      missing_requirements: missingRequirements,
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

test(
  'employee does not see administrative leave setup guidance',
  async () => {
    configureResponses(false);

    const user = userEvent.setup();
    render(<LeaveRequests />);

    const requestButton = screen.getByRole(
      'button',
      { name: /request time off/i },
    );

    await waitFor(() => {
      expect(requestButton).toBeEnabled();
    });

    expect(
      screen.queryByText(
        'Complete time-off setup before requesting leave',
      ),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText('Configure leave policies'),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText('Appoint the business owner'),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText('Appoint an alternate approver'),
    ).not.toBeInTheDocument();

    await user.click(requestButton);

    expect(
      await screen.findByText(
        /Time-off requests are not available yet\./i,
      ),
    ).toHaveTextContent(
      'Contact HR or your organization administrator.',
    );

    expect(
      screen.queryByText('Complete setup'),
    ).not.toBeInTheDocument();
  },
);

test(
  'administrator still sees incomplete leave setup guidance',
  async () => {
    configureResponses(true);

    render(<LeaveRequests />);

    expect(
      await screen.findByText(
        'Complete time-off setup before requesting leave',
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Configure leave policies'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Appoint the business owner'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Appoint an alternate approver'),
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', { name: 'Complete setup' }),
    ).toBeInTheDocument();
  },
);
