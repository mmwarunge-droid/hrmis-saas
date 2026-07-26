import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test } from 'vitest';
import AuthLayout from '../layouts/AuthLayout.jsx';

function LoginPlaceholder() {
  return <div>Login content</div>;
}

describe('AuthLayout', () => {
  test('keeps the sign-in experience single-column until the extra-large breakpoint', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPlaceholder />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const main = container.querySelector('main');
    const promotionalPanel = screen
      .getByText('Modern people operations')
      .closest('section');

    expect(main).toHaveClass('xl:grid');
    expect(main).not.toHaveClass('lg:grid');

    expect(promotionalPanel).toHaveClass('hidden');
    expect(promotionalPanel).toHaveClass('xl:flex');
    expect(promotionalPanel).not.toHaveClass('lg:flex');
  });

  test('renders the connected people operations infographic', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPlaceholder />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByLabelText('Connected people operations'),
    ).toBeInTheDocument();

    expect(screen.getByText('People directory')).toBeInTheDocument();
    expect(screen.getByText('Org structure')).toBeInTheDocument();
    expect(screen.getByText('Workflows')).toBeInTheDocument();
    expect(screen.getByText('Secure access')).toBeInTheDocument();

    expect(
      screen.getByText(
        'One operational record connects every employee, decision and workflow.',
      ),
    ).toBeInTheDocument();
  });

  test('renders the four existing feature cards', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPlaceholder />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('Living org structure')).toBeInTheDocument();
    expect(screen.getByText('People analytics')).toBeInTheDocument();
    expect(screen.getByText('Guided workflows')).toBeInTheDocument();
    expect(screen.getByText('Secure by design')).toBeInTheDocument();

    expect(
      screen.getByText('See teams, reporting lines and roles at a glance.'),
    ).toBeInTheDocument();
  });
});