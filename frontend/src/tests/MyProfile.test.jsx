import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { employeeHomeApi } from '../api/employeeHomeApi.js';
import MyProfile from '../pages/MyProfile.jsx';

vi.mock('../api/employeeHomeApi.js', () => ({
  employeeHomeApi: {
    get: vi.fn(),
    updateProfile: vi.fn(),
    uploadProfileImage: vi.fn(),
  },
}));

const viewer = {
  id: 'employee-1',
  employee_number: 'EMP-001',
  first_name: 'Amina',
  full_name: 'Amina Otieno',
  email: 'amina@example.test',
  phone: '',
  job_title: 'Operations Analyst',
  department_name: 'Operations',
  work_location: 'Nairobi',
  preferred_name: '',
  birthday_visibility: 'colleagues',
  hobbies: ['Hiking'],
};

describe('MyProfile', () => {
  beforeEach(() => {
    employeeHomeApi.get.mockResolvedValue({
      data: {
        branding: { organization_name: 'Acme Ltd', banner_url: null },
        viewer,
      },
    });
    employeeHomeApi.updateProfile.mockResolvedValue({
      data: { ...viewer, preferred_name: 'Mina' },
    });
    employeeHomeApi.uploadProfileImage.mockResolvedValue({
      data: { ...viewer, profile_photo_url: '/api/profile-photo.png' },
    });
  });

  it('lets an employee update details and upload a profile photo', async () => {
    render(
      <MemoryRouter>
        <MyProfile />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Amina Otieno' }))
      .toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Preferred name'), {
      target: { value: 'Mina' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save profile/i }));

    await waitFor(() => {
      expect(employeeHomeApi.updateProfile).toHaveBeenCalledWith(
        expect.objectContaining({ preferred_name: 'Mina' }),
      );
    });

    const photo = new File(['profile'], 'profile.png', { type: 'image/png' });
    fireEvent.change(screen.getByLabelText('Upload profile photo'), {
      target: { files: [photo] },
    });

    await waitFor(() => {
      expect(employeeHomeApi.uploadProfileImage).toHaveBeenCalledWith('photo', photo);
    });
  });
});
