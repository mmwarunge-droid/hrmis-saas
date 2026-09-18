import { Blob } from 'node:buffer';
import { expect, it, vi } from 'vitest';
import apiClient from '../api/apiClient.js';

it('decodes JSON errors returned by PDF download endpoints', async () => {
  vi.stubGlobal('Blob', Blob);
  try {
    await expect(apiClient.get('/signature-requests/recipients/test/document', {
      responseType: 'blob',
      adapter: (config) => Promise.reject({ config, response: {
        status: 409,
        data: new Blob([JSON.stringify({ error: { code: 'SIGNING_DOCUMENT_UNAVAILABLE', message: 'The source snapshot is unavailable.' } })], { type: 'application/json' }),
      } }),
    })).rejects.toMatchObject({ httpStatus: 409, error: { message: 'The source snapshot is unavailable.' } });
  } finally {
    vi.unstubAllGlobals();
  }
});
