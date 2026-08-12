import {
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { onboardingApi } from '../api/onboardingApi.js';
import { signatureApi } from '../api/signatureApi.js';
import Tasks from '../pages/Tasks.jsx';

vi.mock('../api/onboardingApi.js', () => ({
  onboardingApi: {
    myTasks: vi.fn(),
    templates: vi.fn(),
    complete: vi.fn(),
  },
}));

vi.mock('../api/signatureApi.js', () => ({
  signatureApi: {
    myTasks: vi.fn(),
    viewed: vi.fn(),
    sign: vi.fn(),
    decline: vi.fn(),
  },
}));

vi.mock('../components/documents/SignatureTaskCard.jsx', () => ({
  default: ({ task }) => <div>{task.subject}</div>,
}));

beforeEach(() => {
  vi.clearAllMocks();
  onboardingApi.myTasks.mockResolvedValue({
    data: { items: [] },
  });
  onboardingApi.templates.mockResolvedValue({
    data: { items: [] },
  });
  signatureApi.myTasks.mockResolvedValue({
    data: { items: [] },
  });
});

test('employee task center uses self-service onboarding payload without admin template API', async () => {
  onboardingApi.myTasks.mockResolvedValue({
    data: {
      items: [{
        id: 'assignment-1',
        employee_id: 'employee-1',
        task_id: 'task-1',
        task_title: 'Read security policy',
        task_description: 'Review and acknowledge the policy.',
        template_id: 'template-1',
        template_name: 'First week',
        assignee_role: 'EMPLOYEE',
        status: 'pending',
        due_date: '2026-08-20',
      }],
    },
  });

  render(<Tasks />);

  await waitFor(() => {
    expect(onboardingApi.myTasks).toHaveBeenCalledTimes(1);
  });

  expect(onboardingApi.templates).not.toHaveBeenCalled();
  expect(await screen.findByText('Read security policy')).toBeInTheDocument();
  expect(screen.getByText(/First week/)).toBeInTheDocument();
});

test('declined signature discussions are not counted as documents still awaiting signature', async () => {
  signatureApi.myTasks.mockResolvedValue({
    data: {
      items: [{
        id: 'recipient-1',
        subject: 'Employment contract',
        status: 'declined',
        due_at: '2026-08-01T09:00:00Z',
        document: {
          id: 'document-1',
          title: 'Employment contract',
        },
      }],
    },
  });

  render(<Tasks />);

  await screen.findByText('Employment contract');

  const signatureStat = screen
    .getByText('Documents to sign')
    .closest('section');
  const overdueStat = screen
    .getByText('Overdue')
    .closest('section');

  expect(within(signatureStat).getByText('0')).toBeInTheDocument();
  expect(within(overdueStat).getByText('0')).toBeInTheDocument();
  expect(
    screen.queryByText(/will be enabled through the signing-provider integration phase/i),
  ).not.toBeInTheDocument();
});
