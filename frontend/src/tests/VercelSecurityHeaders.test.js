import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const vercelConfig = JSON.parse(
  readFileSync(
    resolve(process.cwd(), 'vercel.json'),
    'utf8',
  ),
);

function contentSecurityPolicy() {
  const catchAll = vercelConfig.headers.find(
    (entry) => entry.source === '/(.*)',
  );

  const header = catchAll?.headers?.find(
    (entry) => entry.key === 'Content-Security-Policy',
  );

  return header?.value || '';
}

test('production CSP allows blob-backed training video metadata', () => {
  const policy = contentSecurityPolicy();

  expect(policy).toContain("media-src 'self' blob:");
});
