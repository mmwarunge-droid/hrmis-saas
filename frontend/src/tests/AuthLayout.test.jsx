import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test } from 'vitest';

import AuthLayout from '../layouts/AuthLayout.jsx';

function LoginPlaceholder() {
  return <div>Login content</div>;
}

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPlaceholder />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('AuthLayout', () => {
  test(
    'keeps the sign-in experience single-column until the extra-large breakpoint',
    () => {
      const { container } = renderLayout();

      const main = container.querySelector('main');
      const promotionalPanel = screen
        .getByText('Built for ambitious African teams')
        .closest('section');

      expect(main).toHaveClass('xl:grid');
      expect(main).not.toHaveClass('lg:grid');

      expect(promotionalPanel).toHaveClass('hidden');
      expect(promotionalPanel).toHaveClass('xl:block');
      expect(promotionalPanel).not.toHaveClass('lg:block');
    },
  );

  test('renders the African connected people operations story', () => {
    renderLayout();

    expect(
      screen.getByText('Built for ambitious African teams'),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'People in motion. Teams in sync. Growth with momentum.',
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText('Connected people operations'),
    ).toBeInTheDocument();

    expect(screen.getByText('People')).toBeInTheDocument();
    expect(screen.getByText('Structure')).toBeInTheDocument();
    expect(screen.getByText('Workflows')).toBeInTheDocument();
    expect(screen.getByText('Momentum')).toBeInTheDocument();

    expect(screen.getByText('Employee records')).toBeInTheDocument();
    expect(screen.getByText('Teams and reporting')).toBeInTheDocument();
    expect(
      screen.getByText('Onboarding and time off'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Built for African teams'),
    ).toBeInTheDocument();
  });

  test('renders the new Kinetic feature cards', () => {
    renderLayout();

    expect(screen.getByText('Connected teams')).toBeInTheDocument();
    expect(screen.getByText('Clear people signals')).toBeInTheDocument();
    expect(screen.getByText('Work that keeps moving')).toBeInTheDocument();
    expect(screen.getByText('Enterprise foundations')).toBeInTheDocument();

    expect(
      screen.getByText(
        'Keep people, reporting lines and workflows in one shared operating system.',
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'Secure access, tenant isolation and role-aware controls by design.',
      ),
    ).toBeInTheDocument();
  });

  test('loads both Kinetic Africa hero images', () => {
    const { container } = renderLayout();

    expect(
      container.querySelector(
        'img[src="/kinetic-africa-hero-1.png"]',
      ),
    ).toBeInTheDocument();

    expect(
      container.querySelector(
        'img[src="/kinetic-africa-hero-2.png"]',
      ),
    ).toBeInTheDocument();
  });
});
