import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { notificationApi } from '../api/notificationApi.js';
import NotificationMenu from '../components/notifications/NotificationMenu.jsx';

vi.mock('../api/notificationApi.js', () => ({
  notificationApi: {
    list: vi.fn(),
    read: vi.fn(),
    readAll: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  notificationApi.list.mockResolvedValue({
    data: {
      unread_count: 2,
      items: [
        {
          id: 'notification-1',
          title: 'Leave request needs review',
          body: 'Neema Hassan requested annual leave.',
          notification_type: 'leave_approval',
          action_url: '/leave',
          read_at: null,
          created_at: new Date().toISOString(),
        },
        {
          id: 'notification-2',
          title: 'Onboarding task assigned',
          notification_type: 'onboarding',
          action_url: '/onboarding',
          read_at: null,
          created_at: new Date().toISOString(),
        },
      ],
    },
  });
  notificationApi.read.mockResolvedValue({ data: {} });
  notificationApi.readAll.mockResolvedValue({ data: { updated: 2 } });
});

test('shows numerical unread notifications and persists read state', async () => {
  render(
    <MemoryRouter>
      <NotificationMenu />
    </MemoryRouter>,
  );

  const trigger = await screen.findByRole('button', {
    name: 'Notifications, 2 unread',
  });
  fireEvent.click(trigger);

  expect(await screen.findByText('Leave request needs review')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Leave request needs review'));

  await waitFor(() => {
    expect(notificationApi.read).toHaveBeenCalledWith('notification-1');
  });
});

test('marks every notification as read', async () => {
  render(
    <MemoryRouter>
      <NotificationMenu />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole('button', {
    name: 'Notifications, 2 unread',
  }));
  fireEvent.click(await screen.findByRole('button', { name: 'Mark all read' }));
  await waitFor(() => expect(notificationApi.readAll).toHaveBeenCalled());
});
