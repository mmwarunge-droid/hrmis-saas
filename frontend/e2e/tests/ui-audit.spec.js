import { expect, test } from '@playwright/test';

test('employee dashboard and goal filters fit supported viewport widths', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  for (const path of ['/dashboard', '/goals']) {
    await page.goto(path);
    await expect(page.locator('h1')).toBeVisible();
    for (const width of [1440, 1280, 1024, 768, 430, 390, 360]) {
      await page.setViewportSize({ width, height: 900 });
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    }
  }
  expect(errors).toEqual([]);
});

test('mobile navigation contains keyboard focus and restores it on Escape', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto('/dashboard');
  const trigger = page.getByRole('button', { name: 'Open navigation' });
  await trigger.click();
  const drawer = page.getByRole('dialog', { name: 'Navigation' });
  await expect(drawer).toBeVisible();
  for (let index = 0; index < 20; index += 1) {
    await page.keyboard.press('Tab');
    expect(await drawer.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  }
  await page.keyboard.press('Escape');
  await expect(drawer).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test('notifications fit narrow screens and recover from a read-state failure', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 600 });
  await page.route('**/notifications?*', (route) => route.fulfill({ json: { data: { unread_count: 1, items: [{ id: 'audit', title: 'Please review this document', read_at: null, notification_type: 'signature', created_at: new Date().toISOString() }] } } }));
  await page.route('**/notifications/read-all', (route) => route.fulfill({ status: 503, json: { error: { message: 'Please try again shortly.' } } }));
  await page.goto('/dashboard');
  const trigger = page.getByRole('button', { name: 'Notifications, 1 unread' });
  await trigger.click();
  const panel = page.getByRole('region', { name: 'Notifications' });
  const box = await panel.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(360);
  await panel.getByRole('button', { name: 'Mark all read' }).click();
  await expect(panel.getByRole('alert')).toBeVisible();
  await expect(trigger).toHaveAccessibleName('Notifications, 1 unread');
  await page.keyboard.press('Escape');
  await expect(panel).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

function longPdf() {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', `<< /Type /Pages /Kids [${Array.from({ length: 12 }, (_, i) => `${i + 3} 0 R`).join(' ')}] /Count 12 >>`];
  for (let index = 0; index < 12; index += 1) objects.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> >>');
  let source = '%PDF-1.4\n';
  const offsets = [];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(source)); source += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(source);
  source += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(source);
}

test('long signing documents recover from loading failures and explain closed states', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  let requestStatus = 'sent';
  let taskFailure = true;
  let pdfFailure = true;
  let submissions = 0;
  const name = 'Alexandria Catherine Njeri Mwangi Long Recipient Name';
  const task = () => ({ id: 'audit-recipient', status: requestStatus === 'completed' ? 'signed' : 'viewed', request_status: requestStatus, name, signature_preview: name, recipient_count: 1, signed_count: requestStatus === 'completed' ? 1 : 0, viewed_at: new Date().toISOString(), document: { id: 'audit-document', title: 'Long employment agreement with several required fields' }, signers: [], fields: [1, 2].map((pageNumber) => ({ id: `field-${pageNumber}`, field_type: 'text', label: `Required entry ${pageNumber}`, required: true, is_current_recipient: true, page_number: pageNumber, x: 0.1, y: 0.2, width: 0.4, height: 0.05 })) });
  await page.route('**/signature-requests/recipients/audit-recipient', (route) => {
    if (taskFailure) { return route.fulfill({ status: 503, json: { error: { message: 'Task temporarily unavailable.' } } }); }
    return route.fulfill({ json: { data: task() } });
  });
  await page.route('**/signature-requests/recipients/audit-recipient/document', (route) => {
    if (pdfFailure) { return route.fulfill({ status: 503, json: { error: { message: 'Document temporarily unavailable.' } } }); }
    return route.fulfill({ contentType: 'application/pdf', body: longPdf() });
  });
  await page.route('**/signature-requests/recipients/audit-recipient/discussion', (route) => route.fulfill({ json: { data: { comments: [], status: 'open' } } }));
  await page.route('**/signature-requests/recipients/audit-recipient/submit', (route) => {
    submissions += 1;
    if (submissions === 1) return route.fulfill({ status: 422, json: { error: { message: 'Please review the required entries.' } } });
    if (submissions === 2) return route.fulfill({ status: 503, json: { error: { message: 'Signing temporarily unavailable. Please retry.' } } });
    requestStatus = 'completed';
    return route.fulfill({ json: { data: task() } });
  });
  await page.goto('/signature-tasks/audit-recipient');
  await expect(page.getByRole('button', { name: 'Retry loading task' })).toBeVisible();
  taskFailure = false;
  await page.getByRole('button', { name: 'Retry loading task' }).click();
  await expect(page.getByRole('button', { name: 'Retry loading PDF' })).toBeVisible();
  pdfFailure = false;
  await page.getByRole('button', { name: 'Retry loading PDF' }).click();
  await expect(page.locator('canvas')).toHaveCount(12);
  await expect(page.getByLabel('Required entry 1', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Required entry 2', { exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  const submit = page.getByRole('button', { name: /sign & submit/i });
  await expect(submit).toBeDisabled();
  await page.getByLabel('Required entry 1', { exact: true }).fill('Reviewed');
  await page.getByLabel('Required entry 2', { exact: true }).fill('Confirmed');
  await page.getByRole('checkbox', { name: /I have reviewed this document/ }).check();
  await submit.click();
  await expect(page.getByText('Please review the required entries.').first()).toBeVisible();
  await submit.click();
  await expect(page.getByText(/The server could not complete this action/).first()).toBeVisible();
  await expect(page.getByLabel('Required entry 1', { exact: true })).toHaveValue('Reviewed');
  await submit.click();
  await expect(submit).toHaveCount(0);
  for (const status of ['cancelled', 'expired', 'completed']) {
    requestStatus = status;
    await page.reload();
    await expect(page.locator('canvas')).toHaveCount(12);
    await expect(page.getByRole('button', { name: /sign & submit/i })).toHaveCount(0);
    if (status === 'cancelled') await expect(page.getByText(/This signature request was cancelled/)).toBeVisible();
    if (status === 'expired') await expect(page.getByText(/The signing deadline has passed/)).toBeVisible();
  }
  expect(errors).toEqual([]);
});
