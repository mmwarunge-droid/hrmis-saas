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

vi.mock(
  '../components/documents/SignatureFieldPlacement.jsx',
  () => ({
    default: () => (
      <div data-testid="signature-field-placement">
        PDF field editor
      </div>
    ),
  }),
);

import SignatureRequestForm from '../components/documents/SignatureRequestForm.jsx';

function futureLocalDate(days = 7) {
  const date = new Date(Date.now() + (days * 86400000));
  date.setMinutes(0, 0, 0);
  const localDate = new Date(
    date.getTime() - (date.getTimezoneOffset() * 60000),
  );
  return localDate.toISOString().slice(0, 16);
}

function setCompletionDeadline(deadline) {
  const [date, time] = deadline.split('T');

  fireEvent.change(
    screen.getByLabelText('Completion date'),
    { target: { value: date } },
  );

  fireEvent.change(
    screen.getByLabelText('Deadline time'),
    { target: { value: time } },
  );
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
  it('defaults PDF signing to direct document preparation', () => {
    render(
      <SignatureRequestForm
        document={document}
        employees={employees}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.getByRole(
        'radio',
        { name: /Prepare fields on PDF/i },
      ),
    ).toBeChecked();

    expect(
      screen.getByTestId('signature-field-placement'),
    ).toBeInTheDocument();
  });

  it('uses separate date and time controls for the completion deadline', () => {
    render(
      <SignatureRequestForm
        document={document}
        employees={employees}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.getByLabelText('Completion date'),
    ).toHaveAttribute('type', 'date');

    expect(
      screen.getByLabelText('Deadline time'),
    ).toHaveAttribute('type', 'time');

    expect(
      screen.queryByLabelText('Completion deadline'),
    ).not.toBeInTheDocument();
  });

  it('creates a standard Kinetic signature request by default', () => {
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

    fireEvent.click(
      screen.getByRole(
        'radio',
        { name: /Signing record page/i },
      ),
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

    setCompletionDeadline(deadline);
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
      seal_required: false,
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

  it('can require a company seal after signing completes', () => {
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

    fireEvent.click(
      screen.getByRole(
        'radio',
        { name: /Signing record page/i },
      ),
    );

    const sealToggle = screen.getByRole(
      'checkbox',
      { name: /Require company seal after signing/i },
    );

    expect(sealToggle).not.toBeChecked();

    fireEvent.click(sealToggle);

    expect(sealToggle).toBeChecked();

    setCompletionDeadline(deadline);

    fireEvent.change(
      screen.getByLabelText('Signatory 1'),
      { target: { value: 'employee-1' } },
    );

    const submitButton = screen.getByRole(
      'button',
      { name: 'Send for signature' },
    );

    fireEvent.submit(
      submitButton.closest('form'),
    );

    expect(onSubmit).toHaveBeenCalledTimes(1);

    const payload = onSubmit.mock.calls[0][0];

    expect(payload.seal_required).toBe(true);
    expect(payload.assurance_level).toBe('standard');
    expect(payload.signing_mode).toBe('sequential');
  });

  it('retains multi-signer controls for standard Kinetic signing', () => {
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
      screen.getByRole(
        'radio',
        { name: /Signing record page/i },
      ),
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Add signatory' }),
    );
    setCompletionDeadline(deadline);
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

  it('accepts Word DOCX documents for standard Kinetic signing', () => {
    const onSubmit = vi.fn();
    const deadline = futureLocalDate();

    const wordDocument = {
      ...document,
      id: 'document-docx',
      title: 'Word employment contract',
      original_filename: 'employment-contract.docx',
      mime_type: (
        'application/vnd.openxmlformats-officedocument.'
        + 'wordprocessingml.document'
      ),
    };

    render(
      <SignatureRequestForm
        document={wordDocument}
        employees={employees}
        isSuperAdmin
        onSubmit={onSubmit}
      />,
    );

    expect(
      screen.getByText(
        /converts this Word document once to an immutable PDF signing snapshot/i,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'radio',
        { name: /Signing record page/i },
      ),
    ).toBeChecked();

    expect(
      screen.getByRole(
        'radio',
        { name: /Prepare fields on PDF/i },
      ),
    ).toBeDisabled();

    setCompletionDeadline(deadline);
    fireEvent.change(
      screen.getByLabelText('Signatory 1'),
      { target: { value: 'employee-1' } },
    );

    fireEvent.submit(
      screen.getByRole(
        'button',
        { name: 'Send for signature' },
      ).closest('form'),
    );

    expect(onSubmit).toHaveBeenCalledTimes(1);

    const payload = onSubmit.mock.calls[0][0];
    expect(payload.document_id).toBe('document-docx');
    expect(payload.assurance_level).toBe('standard');

    expect(
      screen.queryByText(
        'Standard Kinetic signing supports PDF and Word (.docx) documents only.',
      ),
    ).not.toBeInTheDocument();
  });

  it('rejects unsupported documents for standard Kinetic signing', () => {
    const onSubmit = vi.fn();
    const deadline = futureLocalDate();

    const unsupportedDocument = {
      ...document,
      id: 'document-text',
      original_filename: 'notes.txt',
      mime_type: 'text/plain',
    };

    render(
      <SignatureRequestForm
        document={unsupportedDocument}
        employees={employees}
        isSuperAdmin
        onSubmit={onSubmit}
      />,
    );

    setCompletionDeadline(deadline);
    fireEvent.change(
      screen.getByLabelText('Signatory 1'),
      { target: { value: 'employee-1' } },
    );

    fireEvent.submit(
      screen.getByRole(
        'button',
        { name: 'Send for signature' },
      ).closest('form'),
    );

    expect(onSubmit).not.toHaveBeenCalled();

    expect(
      screen.getByText(
        'Standard Kinetic signing supports PDF and Word (.docx) documents only.',
      ),
    ).toBeInTheDocument();
  });


  it('caps standard requests at four signatories', () => {
    const eligible = Array.from(
      { length: 5 },
      (_, index) => ({
        id: `employee-limit-${index + 1}`,
        tenant_id: 'tenant-1',
        full_name: `Signer ${index + 1}`,
      }),
    );

    render(
      <SignatureRequestForm
        document={document}
        employees={eligible}
        isSuperAdmin
        onSubmit={vi.fn()}
      />,
    );

    const addButton = screen.getByRole(
      'button',
      { name: 'Add signatory' },
    );

    // One signatory exists initially. Three additions reach
    // the supported maximum of four.
    fireEvent.click(addButton);
    fireEvent.click(addButton);
    fireEvent.click(addButton);

    expect(
      screen.getAllByLabelText(
        /^Signatory \d+$/,
      ),
    ).toHaveLength(4);

    expect(addButton).toBeDisabled();

    fireEvent.click(addButton);

    expect(
      screen.getAllByLabelText(
        /^Signatory \d+$/,
      ),
    ).toHaveLength(4);
  });

});
