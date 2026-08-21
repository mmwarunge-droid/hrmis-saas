import {
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import EmployeeExperienceSettings from '../pages/EmployeeExperienceSettings.jsx';

vi.mock('../hooks/useTenant.js', () => ({
  default: () => ({
    tenantId: 'tenant-1',
  }),
}));

vi.mock('../api/employeeHomeApi.js', () => ({
  employeeHomeApi: {
    settings: vi.fn(),
    updateSettings: vi.fn(),
    uploadBranding: vi.fn(),
    events: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
    removeEvent: vi.fn(),
    documentOptions: vi.fn(),
    essentials: vi.fn(),
    createEssential: vi.fn(),
    updateEssential: vi.fn(),
    removeEssential: vi.fn(),
  },
}));

const sections = [
  'birthdays',
  'essentials',
  'people_out_today',
  'events_this_week',
  'new_hires',
  'anniversaries',
  'our_people',
];

const baseSettings = {
  id: 'settings-1',
  tenant_id: 'tenant-1',
  banner_url: null,
  logo_url: null,
  welcome_message: 'Welcome to Acme.',
  enabled_sections: sections,
  section_order: sections,
  new_hire_window_days: 30,
  birthday_visibility_enabled: true,
  anniversaries_enabled: true,
  people_statistics_enabled: true,
  assistant_enabled: false,
  assistant_url: null,
};

beforeEach(() => {
  vi.clearAllMocks();

  employeeHomeApi.settings.mockResolvedValue({
    data: { ...baseSettings },
  });
  employeeHomeApi.events.mockResolvedValue({
    data: { items: [] },
  });
  employeeHomeApi.essentials.mockResolvedValue({
    data: { items: [] },
  });
  employeeHomeApi.documentOptions.mockResolvedValue({
    data: { items: [] },
  });

  employeeHomeApi.uploadBranding.mockImplementation(
    (_tenantId, asset) => Promise.resolve({
      data: {
        ...baseSettings,
        banner_url: asset === 'banner'
          ? '/api/employee-home/branding/tenant-1/banner-test.jpg'
          : null,
        logo_url: asset === 'logo'
          ? '/api/employee-home/branding/tenant-1/logo-test.png'
          : null,
      },
    }),
  );

  employeeHomeApi.updateSettings.mockImplementation(
    (_tenantId, payload) => Promise.resolve({
      data: {
        ...baseSettings,
        ...payload,
      },
    }),
  );
});

test('Save homepage uploads selected branding before saving settings', async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <EmployeeExperienceSettings />
    </MemoryRouter>,
  );

  await screen.findByText('Branding and welcome');

  const banner = new File(
    ['banner'],
    'banner.jpg',
    { type: 'image/jpeg' },
  );
  const logo = new File(
    ['logo'],
    'logo.png',
    { type: 'image/png' },
  );

  await user.upload(
    screen.getByLabelText('Upload company banner'),
    banner,
  );
  await user.upload(
    screen.getByLabelText('Upload company logo'),
    logo,
  );

  await user.click(
    screen.getByRole('button', { name: 'Save homepage' }),
  );

  await waitFor(() => {
    expect(employeeHomeApi.uploadBranding).toHaveBeenCalledTimes(2);
  });

  expect(employeeHomeApi.uploadBranding).toHaveBeenNthCalledWith(
    1,
    'tenant-1',
    'banner',
    banner,
  );
  expect(employeeHomeApi.uploadBranding).toHaveBeenNthCalledWith(
    2,
    'tenant-1',
    'logo',
    logo,
  );

  await waitFor(() => {
    expect(employeeHomeApi.updateSettings).toHaveBeenCalledWith(
      'tenant-1',
      expect.objectContaining({
        banner_url:
          '/api/employee-home/branding/tenant-1/banner-test.jpg',
        logo_url:
          '/api/employee-home/branding/tenant-1/logo-test.png',
        welcome_message: 'Welcome to Acme.',
      }),
    );
  });

  expect(
    await screen.findByText('Employee homepage settings saved.'),
  ).toBeInTheDocument();
});

test('does not claim homepage settings were saved when branding upload fails', async () => {
  const user = userEvent.setup();

  employeeHomeApi.uploadBranding.mockRejectedValueOnce({
    error: {
      message: 'Banner upload failed.',
    },
  });

  render(
    <MemoryRouter>
      <EmployeeExperienceSettings />
    </MemoryRouter>,
  );

  await screen.findByText('Branding and welcome');

  const banner = new File(
    ['banner'],
    'banner.jpg',
    { type: 'image/jpeg' },
  );

  await user.upload(
    screen.getByLabelText('Upload company banner'),
    banner,
  );

  await user.click(
    screen.getByRole('button', { name: 'Save homepage' }),
  );

  expect(
    await screen.findByText('Banner upload failed.'),
  ).toBeInTheDocument();

  expect(employeeHomeApi.updateSettings).not.toHaveBeenCalled();
  expect(
    screen.queryByText('Employee homepage settings saved.'),
  ).not.toBeInTheDocument();
});


test('retains a successful banner upload when a later logo upload fails', async () => {
  const user = userEvent.setup();

  employeeHomeApi.uploadBranding
    .mockResolvedValueOnce({
      data: {
        ...baseSettings,
        banner_url:
          '/api/employee-home/branding/tenant-1/banner-partial.jpg',
        logo_url: null,
      },
    })
    .mockRejectedValueOnce({
      error: {
        message: 'Logo upload failed.',
      },
    });

  render(
    <MemoryRouter>
      <EmployeeExperienceSettings />
    </MemoryRouter>,
  );

  await screen.findByText('Branding and welcome');

  const banner = new File(
    ['banner'],
    'banner.jpg',
    { type: 'image/jpeg' },
  );
  const logo = new File(
    ['logo'],
    'logo.png',
    { type: 'image/png' },
  );

  await user.upload(
    screen.getByLabelText('Upload company banner'),
    banner,
  );
  await user.upload(
    screen.getByLabelText('Upload company logo'),
    logo,
  );

  await user.click(
    screen.getByRole('button', { name: 'Save homepage' }),
  );

  expect(
    await screen.findByText('Logo upload failed.'),
  ).toBeInTheDocument();

  expect(employeeHomeApi.uploadBranding).toHaveBeenCalledTimes(2);
  expect(employeeHomeApi.updateSettings).not.toHaveBeenCalled();

  expect(
    screen.getByLabelText('Company banner URL (optional)'),
  ).toHaveValue(
    '/api/employee-home/branding/tenant-1/banner-partial.jpg',
  );

  expect(
    screen.queryByText('Employee homepage settings saved.'),
  ).not.toBeInTheDocument();
});


test('renders structured homepage validation errors without crashing', async () => {
  const user = userEvent.setup();

  employeeHomeApi.updateSettings.mockRejectedValueOnce({
    error: {
      code: 'VALIDATION_ERROR',
      message: {
        banner_url: ['Not a valid URL.'],
        logo_url: ['Not a valid URL.'],
      },
    },
  });

  render(
    <MemoryRouter>
      <EmployeeExperienceSettings />
    </MemoryRouter>,
  );

  await screen.findByText('Branding and welcome');

  await user.click(
    screen.getByRole('button', { name: 'Save homepage' }),
  );

  expect(
    await screen.findByText(
      'banner url: Not a valid URL. logo url: Not a valid URL.',
    ),
  ).toBeInTheDocument();

  expect(
    screen.queryByText('Employee homepage settings saved.'),
  ).not.toBeInTheDocument();
});
