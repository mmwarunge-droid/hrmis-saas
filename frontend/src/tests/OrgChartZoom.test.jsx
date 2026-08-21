import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import { employeeApi } from '../api/employeeApi';
import OrgChart from '../pages/OrgChart.jsx';

vi.mock('../api/employeeApi', () => ({
  employeeApi: {
    orgChart: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();

  employeeApi.orgChart.mockResolvedValue({
    data: {
      roots: [
        {
          id: 'employee-1',
          full_name: 'Amina Otieno',
          profile_photo_url: '/api/employee-home/profile-images/employee-1/photo.jpg',
          job_title: 'Chief People Officer',
          department_name: 'People',
          work_location: 'Nairobi',
          direct_report_count: 1,
          children: [
            {
              id: 'employee-2',
              full_name: 'Brian Kimani',
              job_title: 'People Partner',
              department_name: 'People',
              work_location: 'Nairobi',
              direct_report_count: 0,
              children: [],
            },
          ],
        },
      ],
      meta: {
        total: 2,
        root_count: 1,
        manager_count: 1,
        max_depth: 2,
      },
    },
  });
});

test('zooms only the organization chart canvas', async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <OrgChart />
    </MemoryRouter>,
  );

  await screen.findByText('Amina Otieno');

  const canvas = screen.getByLabelText('Organization chart canvas');
  const tree = canvas.querySelector('.org-tree');

  expect(tree).toHaveStyle({
    transform: 'scale(1)',
  });

  expect(screen.getByText('100%')).toBeInTheDocument();

  await user.click(
    screen.getByRole('button', {
      name: 'Zoom out organization chart',
    }),
  );

  expect(screen.getByText('90%')).toBeInTheDocument();
  expect(tree).toHaveStyle({
    transform: 'scale(0.9)',
  });

  await user.click(
    screen.getByRole('button', {
      name: 'Zoom in organization chart',
    }),
  );

  expect(screen.getByText('100%')).toBeInTheDocument();
  expect(tree).toHaveStyle({
    transform: 'scale(1)',
  });
});

test('resets the organization chart zoom to 100 percent', async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <OrgChart />
    </MemoryRouter>,
  );

  await screen.findByText('Amina Otieno');

  await user.click(
    screen.getByRole('button', {
      name: 'Zoom out organization chart',
    }),
  );

  expect(screen.getByText('90%')).toBeInTheDocument();

  await user.click(
    screen.getByRole('button', {
      name: 'Reset organization chart zoom',
    }),
  );

  expect(screen.getByText('100%')).toBeInTheDocument();
});

test('fits a wider organization chart into the viewport', async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <OrgChart />
    </MemoryRouter>,
  );

  await screen.findByText('Amina Otieno');

  const canvas = screen.getByLabelText('Organization chart canvas');
  const tree = canvas.querySelector('.org-tree');

  Object.defineProperty(canvas, 'clientWidth', {
    configurable: true,
    value: 600,
  });

  Object.defineProperty(tree, 'scrollWidth', {
    configurable: true,
    value: 1200,
  });

  await user.click(
    screen.getByRole('button', {
      name: 'Fit organization chart to view',
    }),
  );

  expect(screen.getByText('50%')).toBeInTheDocument();
  expect(tree).toHaveStyle({
    transform: 'scale(0.5)',
  });
});


test('renders employee profile photos supplied by the organization chart API', async () => {
  render(
    <MemoryRouter>
      <OrgChart />
    </MemoryRouter>,
  );

  const photo = await screen.findByRole('img', {
    name: 'Amina Otieno',
  });

  expect(photo).toHaveAttribute(
    'src',
    '/api/employee-home/profile-images/employee-1/photo.jpg',
  );
});
