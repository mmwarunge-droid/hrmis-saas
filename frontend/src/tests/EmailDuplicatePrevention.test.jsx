import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { userApi } from '../api/userApi.js';
import EmployeeForm from '../components/employees/EmployeeForm.jsx';
import UserProvisionForm from '../components/users/UserProvisionForm.jsx';

vi.mock('../api/userApi.js', () => ({
  userApi: {
    emailAvailability: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test('user provisioning blocks a duplicate email before submission', async () => {
  userApi.emailAvailability.mockResolvedValue({
    data: {
      available: false,
      code: 'EMAIL_ALREADY_REGISTERED',
      message: 'An account with this email address already exists on the platform.',
    },
  });

  const onSubmit = vi.fn();
  const user = userEvent.setup();

  render(<UserProvisionForm onSubmit={onSubmit} />);

  const email = screen.getByLabelText(/work email/i);
  await user.type(email, ' Existing.User@Acme.Test ');
  fireEvent.blur(email);

  await waitFor(() => {
    expect(userApi.emailAvailability).toHaveBeenCalledWith(
      'existing.user@acme.test',
      '',
    );
  });

  expect(
    await screen.findByText(/account with this email address already exists/i),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: /create account/i }),
  ).toBeDisabled();

  fireEvent.submit(email.closest('form'));
  expect(onSubmit).not.toHaveBeenCalled();
});

test('user provisioning normalizes an available email before submission', async () => {
  userApi.emailAvailability.mockResolvedValue({
    data: {
      available: true,
      code: null,
      message: '',
    },
  });

  const onSubmit = vi.fn();
  const user = userEvent.setup();

  render(<UserProvisionForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText(/first name/i), 'Jane');
  await user.type(screen.getByLabelText(/last name/i), 'Doe');
  const email = screen.getByLabelText(/work email/i);
  await user.type(email, ' Jane.Doe@Acme.Test ');
  fireEvent.blur(email);

  await waitFor(() => {
    expect(
      screen.getByRole('button', { name: /create account/i }),
    ).not.toBeDisabled();
  });

  fireEvent.submit(email.closest('form'));

  expect(onSubmit).toHaveBeenCalledWith(
    expect.objectContaining({
      email: 'jane.doe@acme.test',
    }),
  );
});

test('employee creation blocks a duplicate email preflight', async () => {
  const checkEmailAvailability = vi.fn().mockResolvedValue({
    available: false,
    code: 'EMAIL_ALREADY_REGISTERED',
    message: 'An employee or user with this email address already exists.',
  });
  const onSubmit = vi.fn();
  const user = userEvent.setup();

  render(
    <EmployeeForm
      onSubmit={onSubmit}
      checkEmailAvailability={checkEmailAvailability}
    />,
  );

  const email = screen.getByLabelText(/^email$/i);
  await user.type(email, ' Duplicate.Employee@Acme.Test ');
  fireEvent.blur(email);

  await waitFor(() => {
    expect(checkEmailAvailability).toHaveBeenCalledWith(
      'duplicate.employee@acme.test',
    );
  });
  expect(
    await screen.findByText(/employee or user with this email address already exists/i),
  ).toBeInTheDocument();

  fireEvent.submit(email.closest('form'));
  expect(onSubmit).not.toHaveBeenCalled();
});
