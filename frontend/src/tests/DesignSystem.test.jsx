import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import KineticLogo from '../components/ui/KineticLogo.jsx';
import Table from '../components/ui/Table.jsx';

test('renders the Kinetic product identity', () => {
  render(<KineticLogo />);
  expect(screen.getByLabelText('Kinetic')).toBeInTheDocument();
  expect(screen.getByText('Kinetic')).toBeInTheDocument();
  expect(screen.getByText('People platform')).toBeInTheDocument();
});

test('sorts and paginates compact enterprise tables', () => {
  const rows = [
    { id: '2', name: 'Zara' },
    { id: '1', name: 'Amina' },
    { id: '3', name: 'Brian' },
  ];
  const columns = [{ key: 'name', label: 'Name', sortable: true }];

  render(
    <MemoryRouter>
      <Table columns={columns} rows={rows} pageSize={2} />
    </MemoryRouter>,
  );

  fireEvent.click(screen.getByRole('button', { name: /name/i }));
  expect(screen.getByText('Amina')).toBeInTheDocument();
  expect(screen.getByText('Brian')).toBeInTheDocument();
  expect(screen.queryByText('Zara')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /next page/i }));
  expect(screen.getByText('Zara')).toBeInTheDocument();
});

test('supports keyboard activation on interactive rows', () => {
  const onRowClick = vi.fn();
  render(
    <Table
      columns={[{ key: 'name', label: 'Name' }]}
      rows={[{ id: '1', name: 'Amina' }]}
      onRowClick={onRowClick}
    />,
  );

  const row = screen.getByText('Amina').closest('tr');
  fireEvent.keyDown(row, { key: 'Enter' });
  expect(onRowClick).toHaveBeenCalledWith({ id: '1', name: 'Amina' });
});
