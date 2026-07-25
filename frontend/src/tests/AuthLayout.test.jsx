import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import AuthLayout from '../layouts/AuthLayout.jsx';

describe('AuthLayout', () => {
  it('keeps the sign-in experience single-column until the extra-large breakpoint', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<div>Authentication form</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const main = screen.getByRole('main');
    const promotionalPanel = screen.getByText('Modern people operations').closest('section');

    expect(main.className).toContain('min-h-dvh');
    expect(main.className).toContain('xl:grid');
    expect(main.className).not.toContain('lg:grid');
    expect(promotionalPanel.className).toContain('xl:flex');
    expect(promotionalPanel.className).not.toContain('lg:flex');
    expect(promotionalPanel.className).toContain('overflow-y-auto');
    expect(screen.getByText('Authentication form')).toBeInTheDocument();
  });
});
