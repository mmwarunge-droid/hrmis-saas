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

function futureLocalDate(days = 7) {
  const date = new Date(Date.now() + (days * 86400000));
  date.setMinutes(0, 0, 0);
  const localDate = new Date(
    date.getTime() - (date.getTimezoneOffset() * 60000),
  );
  return localDate.toISOString().slice(0, 16);
}

const document = {
  id: 'document-1',
  tenant_id: 'tenant-1',
  title: 'Employment contract',
  original_filename: 'contract.pdf',
};

const employees = [
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
];

describe('SignatureRequestForm', () => {
  it('creates a standard ACE signature request by default', () => {
    const onSubmit = vi.fn();
    const deadline = futureLocalDate();

    render(
      <SignatureRequestForm
        document={document}
        employees={employees}
        isSuperAdmin
        onSubmit={onSubmit}
      />,
    );

    expect(
      screen.getByLabelText('Signature assurance'),
    ).toHaveValue('standard');

    expect(
      screen.queryByText('Identity-verified provider signing'),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Add signatory' }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Sequence')).toBeEnabled();

    fireEvent.change(
      screen.getByLabelText('Completion deadline'),
      { target: { value: deadline } },
    );
    fireEvent.change(
      screen.getByLabelText('Signatory 1'),
      { target: { value: 'employee-1' } },
    );
    fireEvent.change(
      screen.getByLabelText('Role for signatory 1'),
      { target: { value: 'Employee' } },
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
      assurance_level: 'standard',
      signing_mode: 'sequential',
      due_at: new Date(deadline).toISOString(),
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

  it('retains multi-signer controls for standard ACE signing', () => {
    const onSubmit = vi.fn();
    const deadline = futureLocalDate();

    render(
      <SignatureRequestForm
        document={document}
        employees={[
          employees[0],
          {
            id: 'employee-3',
            tenant_id: 'tenant-1',
            full_name: 'Musa Kamau',
          },
        ]}
        isSuperAdmin
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(
      screen.getByLabelText('Signature assurance'),
      { target: { value: 'standard' } },
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Add signatory' }),
    );
    fireEvent.change(
      screen.getByLabelText('Completion deadline'),
      { target: { value: deadline } },
    );
    fireEvent.change(
      screen.getByLabelText('Signing order'),
      { target: { value: 'parallel' } },
    );
    fireEvent.change(
      screen.getByLabelText('Signatory 1'),
      { target: { value: 'employee-1' } },
    );
    fireEvent.change(
      screen.getByLabelText('Signatory 2'),
      { target: { value: 'employee-3' } },
    );

    const submitButton = screen.getByRole(
      'button',
      { name: 'Send for signature' },
    );
    fireEvent.submit(submitButton.closest('form'));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.assurance_level).toBe('standard');
    expect(payload.signing_mode).toBe('parallel');
    expect(payload.recipients).toHaveLength(2);
    expect(payload.recipients.every(
      (recipient) => recipient.sequence === 1,
    )).toBe(true);
  });
});
