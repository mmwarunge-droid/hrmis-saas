import {
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import {
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import SignatureRequestForm from '../components/documents/SignatureRequestForm.jsx';

describe('SignatureRequestForm', () => {
  it('creates an organization-scoped sequential request', () => {
    const onSubmit = vi.fn();

    render(
      <SignatureRequestForm
        document={{
          id: 'document-1',
          tenant_id: 'tenant-1',
          title: 'Employment contract',
          original_filename: 'contract.pdf',
        }}
        employees={[
          {
            id: 'employee-1',
            tenant_id: 'tenant-1',
            full_name: 'Amina Otieno',
            job_title: 'Finance Manager',
          },
          {
            id: 'employee-2',
            tenant_id: 'tenant-2',
            full_name: 'Other Tenant Employee',
          },
        ]}
        isSuperAdmin
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(
      screen.getByLabelText('Completion deadline'),
      {
        target: {
          value: '2026-08-10T17:00',
        },
      },
    );

    fireEvent.change(
      screen.getByLabelText('Signatory 1'),
      {
        target: {
          value: 'employee-1',
        },
      },
    );

    fireEvent.change(
      screen.getByLabelText('Role for signatory 1'),
      {
        target: {
          value: 'Employee',
        },
      },
    );

    fireEvent.change(
      screen.getByLabelText('Sequence'),
      {
        target: {
          value: '1',
        },
      },
    );

    const submitButton = screen.getByRole(
      'button',
      { name: 'Send for signature' },
    );

    fireEvent.submit(submitButton.closest('form'));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      tenant_id: 'tenant-1',
      document_id: 'document-1',
      subject: 'Please sign: Employment contract',
      message: null,
      signing_mode: 'sequential',
      due_at: new Date(
        '2026-08-10T17:00',
      ).toISOString(),
      recipients: [{
        employee_id: 'employee-1',
        role_label: 'Employee',
        sequence: 1,
      }],
      reminder: {
        first_reminder_after_days: 2,
        reminder_interval_days: 2,
        escalation_days_before_due: 1,
        is_active: true,
      },
    });

    expect(
      screen.queryByText('Other Tenant Employee'),
    ).not.toBeInTheDocument();
  });
});
