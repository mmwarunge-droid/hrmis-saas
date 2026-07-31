import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import EmployeeHome from '../pages/EmployeeHome.jsx';

vi.mock('../api/employeeHomeApi.js', () => ({
  employeeHomeApi: {
    get: vi.fn(),
    updateProfile: vi.fn(),
  },
}));

const response = {
  data: {
    branding: {
      organization_name: 'Acme Ltd',
      banner_url: 'https://cdn.example.test/banner.jpg',
      logo_url: 'https://cdn.example.test/logo.png',
      welcome_message: 'Make today count.',
    },
    viewer: {
      id: 'employee-1',
      first_name: 'Amina',
      full_name: 'Amina Otieno',
      job_title: 'Operations Analyst',
      hobbies: [],
      birthday_visibility: 'colleagues',
    },
    assistant: { enabled: false, url: null },
    enabled_sections: [
      'birthdays',
      'essentials',
      'people_out_today',
      'events_this_week',
      'new_hires',
      'anniversaries',
      'our_people',
    ],
    section_order: [
      'birthdays',
      'essentials',
      'people_out_today',
      'events_this_week',
      'new_hires',
      'anniversaries',
      'our_people',
    ],
    birthdays: [{
      id: 'employee-2',
      full_name: 'Brian Kamau',
      date: '2026-08-02',
      is_today: false,
    }],
    essentials: [{
      id: 'essential-1',
      title: 'Employee handbook',
      document_type: 'policy',
      importance: 'required',
      download_url: '/api/documents/document-1/download',
    }],
    people_out_today: [{
      id: 'employee-3',
      full_name: 'Faith Wanjiku',
      expected_return_date: '2026-08-04',
      availability_label: 'Out today',
    }],
    events_this_week: [{
      id: 'event-1',
      title: 'Company all-hands',
      starts_at: '2026-08-01T09:00:00',
      location: 'Town hall',
    }],
    new_hires: [{
      id: 'employee-4',
      full_name: 'Noah Kiptoo',
      job_title: 'Designer',
      hire_date: '2026-07-28',
    }],
    anniversaries: [{
      id: 'employee-5',
      full_name: 'Lydia Njeri',
      date: '2026-08-03',
      years: 3,
      is_today: false,
    }],
    people_statistics: {
      total_employees: 34,
      locations: [{ key: 'Nairobi', label: 'Nairobi', count: 20 }],
      departments: [{ key: 'Operations', label: 'Operations', count: 8 }],
      gender: [],
      hobbies: [{ key: 'Hiking', label: 'Hiking', count: 6 }],
      minimum_group_size: 3,
    },
  },
};

describe('EmployeeHome', () => {
  beforeEach(() => {
    employeeHomeApi.get.mockResolvedValue(response);
  });

  it('renders the branded people-centred employee homepage', async () => {
    render(
      <MemoryRouter>
        <EmployeeHome />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Hi Amina, glad you’re here/i)).toBeInTheDocument();
    expect(screen.getByText('Make today count.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Request time off/i })).toHaveAttribute('href', '/leave');
    expect(screen.getByText('Employee handbook')).toBeInTheDocument();
    expect(screen.getByText('Brian Kamau')).toBeInTheDocument();
    expect(screen.getByText('Faith Wanjiku')).toBeInTheDocument();
    expect(screen.getByText('Company all-hands')).toBeInTheDocument();
    expect(screen.getByText('Noah Kiptoo')).toBeInTheDocument();
    expect(screen.getByText('Lydia Njeri')).toBeInTheDocument();
    expect(screen.getByText('34')).toBeInTheDocument();

    expect(screen.getByText('Brian Kamau').closest('a')).toHaveAttribute(
      'href',
      '/employees/employee-2',
    );
    expect(screen.getByText('Company all-hands').closest('a')).toHaveAttribute(
      'href',
      '/events/event-1',
    );
    expect(screen.queryByText(/medical|maternity|bereavement/i)).not.toBeInTheDocument();
  });
});
