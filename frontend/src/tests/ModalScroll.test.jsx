import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';

import Button from '../components/ui/Button.jsx';
import Modal from '../components/ui/Modal.jsx';

test(
  'ports the modal to the viewport and keeps actions outside scrolling',
  () => {
    render(
      <Modal
        open
        title="Create employee"
        description="Employee information"
        onClose={vi.fn()}
        footer={
          <>
            <Button type="button" variant="secondary">
              Cancel
            </Button>

            <Button type="submit">
              Save employee
            </Button>
          </>
        }
      >
        <div>Scrollable employee form</div>
      </Modal>,
    );

    const dialog = screen.getByRole('dialog');
    const overlay = document.querySelector(
      '[data-modal-overlay]',
    );
    const scrollRegion = document.querySelector(
      '[data-modal-scroll-region]',
    );
    const footer = document.querySelector(
      '[data-modal-footer]',
    );
    const saveButton = screen.getByRole('button', {
      name: 'Save employee',
    });

    expect(document.body).toContainElement(dialog);

    expect(overlay).toBeInTheDocument();
    expect(overlay).toHaveClass('fixed');
    expect(overlay).toHaveClass('inset-0');

    expect(scrollRegion).toBeInTheDocument();
    expect(scrollRegion).toHaveClass('overflow-y-auto');

    expect(footer).toBeInTheDocument();

    expect(scrollRegion).not.toContainElement(
      saveButton,
    );

    expect(footer).toContainElement(saveButton);
  },
);

test('allows modal footer actions to wrap instead of overflowing', () => {
  render(
    <Modal
      open
      title="Duplicate job title"
      description="Review this organizational role before continuing."
      onClose={vi.fn()}
      size="sm"
      footer={
        <>
          <Button type="button" variant="secondary">
            No, go back to editing
          </Button>

          <Button type="button">
            Yes, continue. This role is independent.
          </Button>
        </>
      }
    >
      <p>Duplicate-title warning</p>
    </Modal>,
  );

  const footer = document.querySelector('[data-modal-footer]');

  expect(footer).toBeInTheDocument();
  expect(footer).toHaveClass('flex-wrap');
});
