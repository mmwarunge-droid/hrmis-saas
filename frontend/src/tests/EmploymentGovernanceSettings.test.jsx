import {
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import { tenantApi } from '../api/tenantApi.js';
import EmploymentGovernanceSettings from '../pages/EmploymentGovernanceSettings.jsx';

const tenantState = vi.hoisted(() => ({
  tenantId: 'tenant-1',
}));

vi.mock('../hooks/useTenant.js', () => ({
  default: () => tenantState,
}));

vi.mock('../api/tenantApi.js', () => ({
  tenantApi: {
    employmentGovernance: vi.fn(),
    updateEmploymentGovernance: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  tenantState.tenantId = 'tenant-1';

  tenantApi.employmentGovernance.mockResolvedValue({
    data: {
      duplicate_job_title_warning_titles: [
        'CEO',
        'Chief Financial Officer',
      ],
    },
  });

  tenantApi.updateEmploymentGovernance.mockImplementation(
    (_tenantId, payload) => Promise.resolve({
      data: payload,
    }),
  );
});

test('loads and saves duplicate job-title warning configuration', async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <EmploymentGovernanceSettings />
    </MemoryRouter>,
  );

  const titles = await screen.findByLabelText(
    /job titles that require duplicate confirmation/i,
  );

  expect(tenantApi.employmentGovernance).toHaveBeenCalledWith(
    'tenant-1',
  );

  expect(titles).toHaveValue(
    'CEO\nChief Financial Officer',
  );

  await user.clear(titles);
  await user.type(
    titles,
    ' CEO \nceo\nChief People Officer\n\n',
  );

  await user.click(
    screen.getByRole('button', {
      name: /save governance/i,
    }),
  );

  await waitFor(() => {
    expect(
      tenantApi.updateEmploymentGovernance,
    ).toHaveBeenCalledWith(
      'tenant-1',
      {
        duplicate_job_title_warning_titles: [
          'CEO',
          'Chief People Officer',
        ],
      },
    );
  });

  expect(
    await screen.findByText(
      /employment governance settings saved/i,
    ),
  ).toBeInTheDocument();
});

test('requires an active organization before loading governance', () => {
  tenantState.tenantId = null;

  render(
    <MemoryRouter>
      <EmploymentGovernanceSettings />
    </MemoryRouter>,
  );

  expect(
    screen.getByText(
      /select an organization before configuring employment governance/i,
    ),
  ).toBeInTheDocument();

  expect(
    tenantApi.employmentGovernance,
  ).not.toHaveBeenCalled();
});
