import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GlobalSearch from '../components/navigation/GlobalSearch.jsx';

vi.mock('../hooks/useAuth.js', () => ({
  default: () => ({
    user: {
      employee_profile: {
        id: 'employee-1',
      },
    },
  }),
}));

import usePermissions from '../hooks/usePermissions.js';

vi.mock('../hooks/usePermissions.js', () => ({ default: vi.fn() }));

beforeEach(() => {
  usePermissions.mockReturnValue({
    hasPermission: () => true,
    hasRole: () => false,
  });
});

test('supports combobox keyboard navigation', () => {
  render(
    <MemoryRouter>
      <GlobalSearch open onClose={vi.fn()} />
    </MemoryRouter>,
  );

  const input = screen.getByRole('combobox', { name: 'Quick navigation' });
  expect(input).toHaveAttribute('aria-controls', 'quick-navigation-results');
  fireEvent.change(input, { target: { value: 'time' } });
  fireEvent.keyDown(document, { key: 'ArrowDown' });
  expect(screen.getAllByRole('option').some(
    (option) => option.getAttribute('aria-selected') === 'true',
  )).toBe(true);
});
