import {
  fireEvent,
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
    viewed: vi.fn(),
    videoProgress: vi.fn(),
    resourceContentUrl: vi.fn((id) => `/api/onboarding/resources/${id}/content`),
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

test('video training stays locked until verified viewing is complete', async () => {
  const hasFocus = vi.spyOn(document, 'hasFocus').mockReturnValue(true);
  const pause = vi.spyOn(
    window.HTMLMediaElement.prototype,
    'pause',
  ).mockImplementation(() => {});

  onboardingApi.myTasks.mockResolvedValue({
    data: {
      items: [{
        id: 'assignment-video-1',
        tenant_id: 'tenant-1',
        task_title: 'AML training',
        task_description: 'Watch the training and acknowledge completion.',
        template_name: 'Compliance onboarding',
        task_type: 'video',
        requires_acknowledgement: true,
        status: 'pending',
        due_date: '2026-09-05',
        video_progress: {
          duration_seconds: 20,
          verified_seconds: 0,
          remaining_seconds: 20,
          verified_percent: 0,
          resume_position_seconds: 0,
          completion_ready: false,
        },
        resource: {
          id: 'resource-video-1',
          resource_type: 'video',
          original_filename: 'aml.mp4',
        },
      }],
    },
  });
  onboardingApi.videoProgress.mockResolvedValue({
    data: {
      id: 'assignment-video-1',
      tenant_id: 'tenant-1',
      task_title: 'AML training',
      task_description: 'Watch the training and acknowledge completion.',
      template_name: 'Compliance onboarding',
      task_type: 'video',
      requires_acknowledgement: true,
      status: 'in_progress',
      due_date: '2026-09-05',
      video_progress: {
        duration_seconds: 20,
        verified_seconds: 20,
        remaining_seconds: 0,
        verified_percent: 100,
        resume_position_seconds: 20,
        completion_ready: true,
      },
      resource: {
        id: 'resource-video-1',
        resource_type: 'video',
        original_filename: 'aml.mp4',
      },
    },
  });
  onboardingApi.complete.mockResolvedValue({ data: {} });

  const { container } = render(<Tasks />);

  expect(await screen.findByText('AML training')).toBeInTheDocument();
  const video = container.querySelector('video');
  expect(video).toHaveAttribute(
    'src',
    '/api/onboarding/resources/resource-video-1/content',
  );

  const completeButton = screen.getByRole(
    'button',
    { name: 'Acknowledge & complete' },
  );
  expect(completeButton).toBeDisabled();
  expect(
    screen.getByText(/watch the full video to unlock completion/i),
  ).toBeInTheDocument();

  Object.defineProperty(video, 'currentTime', {
    configurable: true,
    writable: true,
    value: 19,
  });
  fireEvent.seeking(video);
  expect(video.currentTime).toBe(0);

  fireEvent.ended(video);
  await waitFor(() => {
    expect(onboardingApi.videoProgress).toHaveBeenCalledWith(
      'assignment-video-1',
      {
        event: 'ended',
        position_seconds: 0,
      },
    );
  });

  await waitFor(() => {
    expect(
      screen.getByRole(
        'button',
        { name: 'Acknowledge & complete' },
      ),
    ).toBeEnabled();
  });

  fireEvent.click(
    screen.getByRole(
      'button',
      { name: 'Acknowledge & complete' },
    ),
  );
  await waitFor(() => {
    expect(onboardingApi.complete).toHaveBeenCalledWith(
      'assignment-video-1',
      { acknowledged: true },
    );
  });

  Object.defineProperty(video, 'paused', {
    configurable: true,
    value: false,
  });
  Object.defineProperty(document, 'hidden', {
    configurable: true,
    value: true,
  });
  fireEvent(document, new Event('visibilitychange'));
  expect(pause).toHaveBeenCalled();

  Object.defineProperty(document, 'hidden', {
    configurable: true,
    value: false,
  });
  pause.mockRestore();
  hasFocus.mockRestore();
});
