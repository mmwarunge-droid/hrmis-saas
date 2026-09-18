import { createHmac } from 'node:crypto';
import { expect, test } from '@playwright/test';

const apiBase = process.env.E2E_API_BASE_URL || 'http://localhost:5000/api';
const password = process.env.E2E_DEMO_PASSWORD;
function otp(secret) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const bits = [...secret].map((c) => alphabet.indexOf(c).toString(2).padStart(5, '0')).join('');
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = createHmac('sha1', key).update(counter).digest();
  const offset = digest.at(-1) & 15;
  return ((digest.readUInt32BE(offset) & 0x7fffffff) % 1000000).toString().padStart(6, '0');
}
function pdf() {
  const stream = 'BT /F1 18 Tf 72 720 Td (MVP employment agreement) Tj ET';
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let source = '%PDF-1.4\n';
  const offsets = [];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(source)); source += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(source);
  source += `xref\n0 6\n0000000000 65535 f \n${offsets.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(source);
}
async function login(page, email, mfa = false) {
  await page.goto('/login');
  await page.getByLabel('Work email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  if (mfa) {
    const input = page.getByLabel('Authenticator or recovery code');
    await expect(input).toBeVisible();
    await input.fill(otp(process.env.E2E_DEMO_MFA_SECRET || 'JBSWY3DPEHPK3PXP'));
    await page.getByRole('button', { name: 'Verify', exact: true }).click();
  }
  await expect(page).not.toHaveURL(/login|mfa/);
}
async function api(context, path, method = 'GET', data) {
  const cookies = await context.cookies(apiBase);
  const csrf = cookies.find((c) => c.name === 'csrf_access_token')?.value;
  return context.request.fetch(apiBase + path, { method, data, headers: csrf ? { 'X-CSRF-TOKEN': csrf } : {} });
}

test('admin uploads, places fields, sends, and recipient signs an immutable PDF', async ({ browser, baseURL, viewport, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(120000);
  const admin = await browser.newContext({ baseURL, viewport, isMobile, hasTouch, deviceScaleFactor, storageState: { cookies: [], origins: [] } });
  const recipient = await browser.newContext({ baseURL, viewport, isMobile, hasTouch, deviceScaleFactor, storageState: { cookies: [], origins: [] } });
  const page = await admin.newPage();
  const signer = await recipient.newPage();
  const crashes = [];
  for (const p of [page, signer]) {
    p.on('pageerror', (error) => crashes.push(error.message));
    p.on('response', (response) => { if (response.status() >= 500) crashes.push(`${response.status()} ${response.url()}`); });
  }
  try {
    await login(page, process.env.E2E_ADMIN_EMAIL || 'admin@kinetic.demo', true);
    // This disposable demo account may retain an autosaved upload from a failed run.
    const priorDraft = (await (await api(admin, '/form-drafts/document.upload')).json()).data;
    const clearedDraft = await api(admin, `/form-drafts/document.upload?revision=${priorDraft?.revision || 0}`, 'DELETE');
    expect([200, 404]).toContain(clearedDraft.status());
    await page.goto('/documents');
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await page.getByRole('button', { name: 'Upload file', exact: true }).click();
    const title = `MVP signing ${Date.now()}`;
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Title', { exact: true }).fill(title);
    await dialog.getByLabel('Choose file').setInputFiles({ name: 'mvp-agreement.pdf', mimeType: 'application/pdf', buffer: pdf() });
    const uploaded = page.waitForResponse((r) => r.url().endsWith('/documents/upload') && r.request().method() === 'POST', { timeout: 15000 });
    await dialog.getByRole('button', { name: 'Upload document', exact: true }).click();
    const upload = await uploaded;
    expect(upload.status()).toBe(201);
    const document = (await upload.json()).data;
    await expect(dialog).not.toBeVisible();
    const row = page.getByRole('row').filter({ hasText: title });
    await expect(row).toBeVisible();
    // Open the authorized original before configuring the signing copy.
    const original = await api(admin, `/documents/${document.id}/content`);
    expect(original.status()).toBe(200);
    expect((await original.body()).subarray(0, 5).toString()).toBe('%PDF-');
    await row.getByRole('button', { name: 'Send for signature', exact: true }).click();
    await dialog.getByLabel('Completion date', { exact: false }).fill(new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10));
    await dialog.getByLabel('Deadline time', { exact: false }).fill('17:00');
    const employeeOption = dialog.getByLabel('Signatory 1', { exact: true }).locator('option').filter({ hasText: 'Neema Hassan' });
    await expect(employeeOption).toHaveCount(1);
    const employeeId = await employeeOption.getAttribute('value');
    await dialog.getByLabel('Signatory 1', { exact: true }).selectOption(employeeId);
    await dialog.getByRole('combobox', { name: 'Employee file', exact: true }).selectOption(employeeId);
    await dialog.getByRole('button', { name: 'Signature', exact: true }).click();
    const surface = dialog.getByRole('button', { name: 'Place signature field on PDF page 1', exact: true });
    await expect(surface.locator('canvas')).toBeVisible();
    await surface.click({ position: { x: 90, y: 240 } });
    await dialog.getByRole('button', { name: 'Date', exact: true }).click();
    await dialog.getByRole('button', { name: 'Place date field on PDF page 1', exact: true }).click({ position: { x: 90, y: 330 } });
    const created = page.waitForResponse((r) => r.url().endsWith('/signature-requests') && r.request().method() === 'POST', { timeout: 15000 });
    await dialog.getByRole('button', { name: 'Send for signature', exact: true }).click();
    const sent = await created;
    expect(sent.status()).toBe(201);
    const workflow = (await sent.json()).data;
    const taskId = workflow.recipients[0].id;
    await login(signer, 'employee@kinetic.demo');
    const notifications = (await (await api(recipient, '/notifications')).json()).data;
    expect(notifications.items.some((n) => n.action_url === `/signature-tasks/${taskId}`)).toBe(true);
    const tasks = (await (await api(recipient, '/signature-requests/my-tasks')).json()).data.items;
    expect(tasks.some((item) => item.recipient_id === taskId || item.id === taskId)).toBe(true);
    await signer.goto(`/signature-tasks/${taskId}`);
    await expect(signer.locator('canvas').first()).toBeVisible();
    await expect.poll(async () => (await (await api(recipient, `/signature-requests/recipients/${taskId}`)).json()).data.status).toBe('viewed');
    await signer.getByRole('checkbox', { name: /I have reviewed this document/ }).check();
    const submitted = signer.waitForResponse((r) => r.url().endsWith(`/${taskId}/submit`) && r.request().method() === 'POST', { timeout: 15000 });
    await signer.getByRole('button', { name: /Sign & submit/i }).click();
    expect((await submitted).status()).toBe(200);
    await expect(signer.getByText('signed', { exact: true }).first()).toBeVisible();
    const complete = (await (await api(admin, `/signature-requests/${workflow.id}`)).json()).data;
    expect(complete.status).toBe('completed');
    expect(complete.completed_at).toBeTruthy();
    expect(complete.document.signature_status).toBe('signed');
    expect(complete.signed_document.checksum_sha256).toHaveLength(64);
    const signed = await api(recipient, `/signature-requests/recipients/${taskId}/signed-document`);
    expect(signed.status()).toBe(200);
    expect((await signed.body()).subarray(0, 5).toString()).toBe('%PDF-');
    const adminNotifications = (await (await api(admin, '/notifications')).json()).data.items;
    expect(adminNotifications.some((n) => n.title.startsWith('Signing completed:'))).toBe(true);
    await signer.reload();
    await expect(signer.getByText('signed', { exact: true }).first()).toBeVisible();
    expect((await api(recipient, `/signature-requests/recipients/${taskId}/submit`, 'POST', { consent: true })).status()).toBe(200);
    const retried = (await (await api(admin, `/signature-requests/${workflow.id}`)).json()).data;
    expect(retried.signed_document.id).toBe(complete.signed_document.id);
    expect(retried.events.filter((e) => e.event_type === 'signature.request_completed')).toHaveLength(1);
    expect(crashes).toEqual([]);
  } finally {
    await admin.close().catch(() => {});
    await recipient.close().catch(() => {});
  }
});
