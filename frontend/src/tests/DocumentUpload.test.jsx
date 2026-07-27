import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DocumentUpload from '../components/documents/DocumentUpload.jsx';

describe('DocumentUpload', () => {
  it('submits the selected organization for a platform administrator', () => {
    const onSubmit = vi.fn();

    render(
      <DocumentUpload
        onSubmit={onSubmit}
        isSuperAdmin
        tenants={[
          {
            id: '4f93671f-477b-4a21-97f1-2c720793c135',
            name: 'Northstar Logistics',
          },
        ]}
      />,
    );

    fireEvent.change(screen.getByLabelText('Organization'), {
      target: {
        value: '4f93671f-477b-4a21-97f1-2c720793c135',
      },
    });

    fireEvent.change(screen.getByLabelText('Title'), {
      target: {
        value: 'Board resolution',
      },
    });

    const file = new File(
      ['board resolution'],
      'board-resolution.docx',
      {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      },
    );

    const fileInput = document.querySelector('input[type="file"]');

    fireEvent.change(fileInput, {
      target: {
        files: [file],
      },
    });

    const form = fileInput.closest('form');

    expect(form).not.toBeNull();
    fireEvent.submit(form);

    expect(onSubmit).toHaveBeenCalledTimes(1);

    const submitted = onSubmit.mock.calls[0][0];

    expect(submitted.get('tenant_id')).toBe(
      '4f93671f-477b-4a21-97f1-2c720793c135',
    );
    expect(submitted.get('title')).toBe('Board resolution');
    expect(submitted.get('file')).toBe(file);
  });
});
