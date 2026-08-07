import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import Tabs from '../components/ui/Tabs.jsx';
import NotFound from '../pages/NotFound.jsx';

function TabFixture() {
  const [value, setValue] = useState('overview');
  return (
    <>
      <Tabs
        ariaLabel="Profile sections"
        idPrefix="profile-sections"
        value={value}
        onChange={setValue}
        items={[
          { value: 'overview', label: 'Overview' },
          { value: 'performance', label: 'Performance' },
          { value: 'activity', label: 'Activity' },
        ]}
      />
      <section
        id={`profile-sections-panel-${value}`}
        role="tabpanel"
        aria-labelledby={`profile-sections-tab-${value}`}
      >
        {value}
      </section>
    </>
  );
}

test('tabs support roving focus and keyboard selection', () => {
  render(<TabFixture />);

  const overview = screen.getByRole('tab', { name: 'Overview' });
  const performance = screen.getByRole('tab', { name: 'Performance' });
  overview.focus();
  fireEvent.keyDown(overview, { key: 'ArrowRight' });

  expect(performance).toHaveFocus();
  expect(performance).toHaveAttribute('aria-selected', 'true');
  expect(performance).toHaveAttribute(
    'aria-controls',
    'profile-sections-panel-performance',
  );

  fireEvent.keyDown(performance, { key: 'End' });
  expect(screen.getByRole('tab', { name: 'Activity' })).toHaveFocus();
});

test('unknown routes provide a recoverable not-found experience', () => {
  render(
    <MemoryRouter>
      <NotFound />
    </MemoryRouter>,
  );

  expect(screen.getByRole('heading', { name: /page is not available/i })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /open home/i })).toHaveAttribute('href', '/dashboard');
});
