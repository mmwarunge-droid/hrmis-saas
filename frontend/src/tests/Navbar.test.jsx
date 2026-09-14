import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Navbar from '../components/navigation/Navbar.jsx';

vi.mock('../hooks/useAuth.js', () => ({
  default: () => ({
    user: {
      full_name: 'Amina Njeri',
      email: 'amina@example.com',
      roles: ['HR_ADMIN'],
    },
    logout: vi.fn(),
  }),
}));

vi.mock('../components/notifications/NotificationMenu.jsx', () => ({
  default: () => <div data-testid="notification-menu" />,
}));

vi.mock('../components/navigation/GlobalSearch.jsx', () => ({
  default: () => null,
}));

test('closes the account menu with Escape and restores focus to its trigger', () => {
  render(
    <MemoryRouter>
      <Navbar onMenu={vi.fn()} />
    </MemoryRouter>,
  );

  const trigger = screen.getByRole('button', {
    name: 'Account options',
  });

  fireEvent.click(trigger);

  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  expect(
    screen.getByRole('link', { name: 'My info' }),
  ).toBeInTheDocument();

  fireEvent.keyDown(document, { key: 'Escape' });

  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(
    screen.queryByRole('link', { name: 'My info' }),
  ).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
