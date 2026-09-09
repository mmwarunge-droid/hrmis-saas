import { useState } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import Form from '../components/forms/Form.jsx';
import Modal from '../components/ui/Modal.jsx';
import Input from '../components/ui/Input.jsx';
import apiClient from '../api/apiClient.js';
import { AuthContext } from '../context/AuthContext.jsx';
import { formDraftApi } from '../api/formDraftApi.js';
import { SESSION_EXPIRED_EVENT } from '../utils/sessionExpiry.js';

function Example({ submit, drafts = false, close = () => {} }) {
  const [value, setValue] = useState('');
  return <Modal open title="Edit employee" onClose={close}><Form onSubmit={submit} draft={drafts ? { key: 'employee.new', title: 'Employee', data: { name: value }, onRestore: (data) => setValue(data.name) } : undefined}>
    <Input label="Full name" name="name" value={value} onChange={(e) => setValue(e.target.value)} required />
    <button type="submit">Submit</button><button type="button" onClick={close}>Cancel</button>
  </Form></Modal>;
}
const originalAdapter = apiClient.defaults.adapter;
afterEach(() => { apiClient.defaults.adapter = originalAdapter; vi.restoreAllMocks(); });
it.each([400, 422, 401, 403, 500, 'network', 'timeout'])('preserves entries and displays %s inside the modal', async (status) => {
  const expired = vi.fn(); window.addEventListener(SESSION_EXPIRED_EVENT, expired);
  apiClient.defaults.adapter = async (config) => { throw { config, isAxiosError: true, code: status === 'timeout' ? 'ECONNABORTED' : undefined, ...(typeof status === 'number' ? { response: { status, data: { error: { message: { name: ['Please use your official name.'] } } } } } : {}) }; };
  render(<Example submit={async () => { try { await apiClient.post('/employees', {}); } catch { /* The page catches errors too. */ } }} />);
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Preserved name' } });
  fireEvent.click(screen.getByText('Submit'));
  await waitFor(() => expect(within(screen.getByRole('dialog')).getByRole('alert')).toBeVisible());
  expect(screen.getByLabelText('Full name')).toHaveValue('Preserved name');
  expect(expired).not.toHaveBeenCalled();
  if (status === 422) { expect(screen.getByLabelText('Full name')).toHaveAttribute('aria-invalid', 'true'); fireEvent.click(screen.getByText('name: Please use your official name.')); expect(screen.getByLabelText('Full name')).toHaveFocus(); }
  window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
});
it('validates incomplete fields and prevents double submissions', async () => {
  let finish;
  const submit = vi.fn(() => new Promise((resolve) => { finish = resolve; }));
  render(<Example submit={submit} />);
  fireEvent.click(screen.getByText('Submit')); expect(submit).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toHaveTextContent('correct');
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Valid name' } });
  fireEvent.click(screen.getByText('Submit')); fireEvent.click(screen.getByText('Submit'));
  expect(submit).toHaveBeenCalledTimes(1); expect(screen.getByText('Submit')).toBeDisabled();
  await act(async () => finish({ success: true }));
  expect(screen.getByRole('status')).toHaveTextContent('saved successfully');
});
it.each(['Close dialog', 'Cancel', 'Escape', 'backdrop'])('guards %s and supports continue/discard', async (action) => {
  const close = vi.fn(); render(<Example close={close} />);
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Unsaved' } });
  if (action === 'Escape') fireEvent.keyDown(document, { key: 'Escape' });
  else if (action === 'backdrop') fireEvent.mouseDown(document.querySelector('[data-modal-overlay]'));
  else fireEvent.click(screen.getByRole('button', { name: action }));
  expect(close).not.toHaveBeenCalled(); expect(screen.getByRole('alertdialog')).toBeVisible();
  fireEvent.click(screen.getByText('Continue editing')); expect(screen.getByLabelText('Full name')).toHaveValue('Unsaved');
  fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
  fireEvent.click(screen.getByText('Discard changes')); await waitFor(() => expect(close).toHaveBeenCalledTimes(1));
});
it('saves incomplete drafts without executing and resumes after remount', async () => {
  let saved;
  vi.spyOn(formDraftApi, 'get').mockImplementation(async () => ({ data: saved || {} }));
  vi.spyOn(formDraftApi, 'save').mockImplementation(async (key, payload) => ({ data: saved = { key, ...payload, revision: 1, updated_at: '2026-09-09T09:00:00Z' } }));
  const submit = vi.fn();
  const tree = () => <AuthContext.Provider value={{ user: { id: 'owner' } }}><Example drafts submit={submit} /></AuthContext.Provider>;
  const first = render(tree()); await act(async () => {});
  fireEvent.click(screen.getByText('Save draft'));
  await screen.findByText(/Draft saved/); expect(submit).not.toHaveBeenCalled(); expect(saved.data).toEqual({ name: '' });
  first.unmount(); render(tree()); await screen.findByText('Resume draft');
  fireEvent.click(screen.getByText('Resume draft')); expect(screen.getByLabelText('Full name')).toHaveValue('');
});

it('protects browser back navigation and allows continuing editing', async () => {
  const { createMemoryRouter, RouterProvider } = await import('react-router-dom');
  const { default: WorkflowNavigationGuard } = await import('../components/forms/WorkflowNavigationGuard.jsx');
  const router = createMemoryRouter([
    { path: '/edit', element: <><WorkflowNavigationGuard /><Example /></> },
    { path: '/previous', element: <p>Previous page</p> },
  ], { initialEntries: ['/previous', '/edit'], initialIndex: 1 });
  render(<RouterProvider router={router} />);
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Do not lose this' } });
  await act(async () => router.navigate(-1));
  expect(screen.getByRole('alertdialog')).toBeVisible();
  fireEvent.click(screen.getByText('Continue editing'));
  expect(screen.getByLabelText('Full name')).toHaveValue('Do not lose this');
  await act(async () => router.navigate(-1));
  fireEvent.click(screen.getByText('Discard changes'));
  await screen.findByText('Previous page');
});
it('keeps the form open when saving a draft fails', async () => {
  vi.spyOn(formDraftApi, 'get').mockResolvedValue({ data: {} });
  vi.spyOn(formDraftApi, 'save').mockRejectedValue({ error: { message: 'Unable to save draft. Try again.' } });
  const close = vi.fn();
  render(<AuthContext.Provider value={{ user: { id: 'owner' } }}><Example drafts close={close} /></AuthContext.Provider>);
  await act(async () => {});
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Preserve on failure' } });
  fireEvent.click(screen.getByLabelText('Close dialog'));
  fireEvent.click(screen.getByText('Save draft and exit'));
  await screen.findByText('Unable to save draft. Try again.');
  expect(close).not.toHaveBeenCalled(); expect(screen.getByLabelText('Full name')).toHaveValue('Preserve on failure');
});

it('keeps invalid-login errors distinct from an expired working session', async () => {
  apiClient.defaults.adapter = async (config) => { throw { config, response: { status: 401, data: { error: { message: 'Incorrect email or password.' } } } }; };
  render(<Example submit={() => apiClient.post('/auth/login', {})} />);
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Entered' } });
  fireEvent.click(screen.getByText('Submit'));
  await screen.findByText('Incorrect email or password.');
  expect(screen.queryByText(/Sign in in a new tab/)).not.toBeInTheDocument();
});

it('does not clear a draft when an intermediate upload succeeds but the workflow fails', async () => {
  vi.spyOn(formDraftApi, 'get').mockResolvedValue({ data: {} });
  vi.spyOn(formDraftApi, 'save').mockImplementation(async (key, payload) => ({ data: { key, ...payload, revision: 1, updated_at: '2026-09-09T09:00:00Z' } }));
  const discard = vi.spyOn(formDraftApi, 'discard');
  apiClient.defaults.adapter = async (config) => ({ config, status: 200, data: { success: true, data: { id: 'resource' } }, headers: {} });
  render(<AuthContext.Provider value={{ user: { id: 'owner' } }}><Example drafts submit={async () => {
    await apiClient.post('/onboarding/resources', {});
    return { success: false, error: new Error('Add the second training document before creating this template.') };
  }} /></AuthContext.Provider>);
  await act(async () => {});
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Keep this workflow' } });
  fireEvent.click(screen.getByText('Save draft')); await screen.findByText(/Draft saved/);
  fireEvent.click(screen.getByText('Submit'));
  await screen.findByText('Add the second training document before creating this template.');
  expect(discard).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Full name')).toHaveValue('Keep this workflow');
  expect(screen.queryByText('Changes saved successfully.')).not.toBeInTheDocument();
});

it('shows an asynchronous modal action failure after event capture has ended', async () => {
  apiClient.defaults.adapter = async (config) => { throw { config, response: { status: 422, data: { error: { message: 'Choose a signatory with an email address.' } } } }; };
  render(<Modal open title="Prepare signing" onClose={() => {}}><button type="button" onClick={async () => {
    await Promise.resolve(); await Promise.resolve();
    try { await apiClient.get('/employees/validate'); } catch { /* legacy page catches it */ }
  }}>Validate signatories</button></Modal>);
  fireEvent.click(screen.getByText('Validate signatories'));
  expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('Choose a signatory');
});

it('automatically saves changed draft data and does not submit it', async () => {
  vi.spyOn(formDraftApi, 'get').mockResolvedValue({ data: {} });
  const save = vi.spyOn(formDraftApi, 'save').mockImplementation(async (key, payload) => ({ data: { key, ...payload, revision: payload.revision + 1, updated_at: '2026-09-09T11:42:00Z' } }));
  const submit = vi.fn();
  render(<AuthContext.Provider value={{ user: { id: 'owner' } }}><Example drafts submit={submit} /></AuthContext.Provider>);
  await act(async () => {});
  expect(save).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Autosaved employee' } });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1), { timeout: 3000 });
  expect(save.mock.calls[0][1].data.name).toBe('Autosaved employee');
  expect(submit).not.toHaveBeenCalled();
  // Reverting to the initial value must replace the older saved value too.
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: '' } });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2), { timeout: 3000 });
  expect(save.mock.calls[1][1].data.name).toBe('');
});

it('does not overwrite an existing draft or recreate it immediately after discard', async () => {
  vi.spyOn(formDraftApi, 'get').mockResolvedValue({ data: { key: 'employee.new', revision: 3, data: { name: 'Older saved work' }, updated_at: '2026-09-09T11:42:00Z' } });
  const save = vi.spyOn(formDraftApi, 'save');
  const discard = vi.spyOn(formDraftApi, 'discard').mockResolvedValue({ data: {} });
  render(<AuthContext.Provider value={{ user: { id: 'owner' } }}><Example drafts /></AuthContext.Provider>);
  await screen.findByText('Resume draft');
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'New unsaved entries' } });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1300)); });
  expect(save).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Discard saved draft'));
  await waitFor(() => expect(discard).toHaveBeenCalled());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1300)); });
  expect(save).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Full name')).toHaveValue('New unsaved entries');
});

it('does not pull focus away while correcting an external form error', async () => {
  function ExternalError() {
    const [value, setValue] = useState('');
    return <Form error="Please correct your name." onSubmit={() => {}}><Input label="Name to correct" value={value} onChange={e => setValue(e.target.value)} /></Form>;
  }
  render(<ExternalError />);
  const input=screen.getByLabelText('Name to correct');
  input.focus();
  fireEvent.change(input, { target: { value: 'Correction' } });
  expect(input).toHaveFocus();
  expect(screen.getByRole('alert')).toBeVisible();
});
