import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { employeeApi } from '../api/employeeApi.js';
import { onboardingApi } from '../api/onboardingApi.js';
import OnboardingAdminPanel from '../components/onboarding/OnboardingAdminPanel.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';

vi.mock('../api/employeeApi.js', () => ({
  employeeApi: { options: vi.fn() },
}));

vi.mock('../api/onboardingApi.js', () => ({
  onboardingApi: {
    templates: vi.fn(),
    assignments: vi.fn(),
    summary: vi.fn(),
    createTemplate: vi.fn(),
    uploadResource: vi.fn(),
    assign: vi.fn(),
    updateAssignment: vi.fn(),
    attempts: vi.fn(),
    retake: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  employeeApi.options.mockResolvedValue({ data: { items: [] } });
  onboardingApi.templates.mockResolvedValue({ data: { items: [] } });
  onboardingApi.summary.mockResolvedValue({
    data: { total: 1, open: 0, overdue: 0, completed: 1, waived: 0 },
  });
  onboardingApi.assignments.mockResolvedValue({
    data: {
      items: [{
        id: 'assignment-1',
        employee_name: 'John Doe',
        employee_number: 'EMP-001',
        task_title: 'Workplace ethics training',
        template_name: 'Compliance',
        task_type: 'video',
        due_date: '2026-09-30',
        status: 'completed',
        current_attempt_number: 1,
        attempt_limit: 1,
        attempts_remaining: 0,
        resource: {
          id: 'resource-1',
          original_filename: 'ethics.mp4',
        },
      }],
      meta: { page: 1, pages: 1, total: 1 },
    },
  });
  onboardingApi.attempts.mockResolvedValue({
    data: {
      items: [{
        id: 'attempt-1',
        attempt_number: 1,
        status: 'completed',
      }],
    },
  });
  onboardingApi.retake.mockResolvedValue({ data: {} });
});

test('client admin grants a retake without recreating training content', async () => {
  render(
    <ToastProvider>
      <OnboardingAdminPanel />
    </ToastProvider>,
  );

  fireEvent.click(await screen.findByRole('button', { name: 'Grant attempt' }));

  const retakeDialog = await screen.findByRole(
    'dialog',
    { name: 'Grant additional attempt' },
  );

  expect(
    within(retakeDialog).getByText('John Doe'),
  ).toBeInTheDocument();
  expect(
    within(retakeDialog).getByText('Workplace ethics training'),
  ).toBeInTheDocument();
  expect(
    within(retakeDialog).getByText('ethics.mp4'),
  ).toBeInTheDocument();
  expect(
    within(retakeDialog).getByText('Attempt 1'),
  ).toBeInTheDocument();

  fireEvent.change(
    within(retakeDialog).getByLabelText(
      'Reason for resubmission',
    ),
    {
      target: {
        value: 'Connectivity issue during the first attempt',
      },
    },
  );

  fireEvent.click(
    within(retakeDialog).getByRole(
      'button',
      { name: 'Grant & resubmit' },
    ),
  );

  await waitFor(() => {
    expect(onboardingApi.retake).toHaveBeenCalledWith('assignment-1', {
      reason: 'Connectivity issue during the first attempt',
      due_date: '2026-09-30',
      grant_additional_attempts: 1,
    });
  });
});
