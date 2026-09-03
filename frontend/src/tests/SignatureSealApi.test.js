import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}));

vi.mock('../api/apiClient', () => ({
  default: {
    get: mocks.get,
    post: mocks.post,
    patch: mocks.patch,
    defaults: {
      baseURL: '/api',
    },
  },
}));

import { signatureApi } from '../api/signatureApi.js';

describe('signature seal API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads a management artifact as a blob', () => {
    signatureApi.artifact(
      'request-1',
      'artifact-1',
    );

    expect(mocks.get).toHaveBeenCalledWith(
      '/signature-requests/request-1/artifacts/artifact-1/download',
      {
        responseType: 'blob',
      },
    );
  });

  it('loads the persisted company seal image as a blob', () => {
    signatureApi.sealImage('request-1');

    expect(mocks.get).toHaveBeenCalledWith(
      '/signature-requests/request-1/seal/image',
      {
        responseType: 'blob',
      },
    );
  });

  it('uploads the company seal image as multipart form data', () => {
    const file = new File(
      ['seal'],
      'company-seal.png',
      {
        type: 'image/png',
      },
    );

    signatureApi.uploadSealImage(
      'request-1',
      file,
    );

    expect(mocks.post).toHaveBeenCalledTimes(1);

    const [
      url,
      payload,
    ] = mocks.post.mock.calls[0];

    expect(url).toBe(
      '/signature-requests/request-1/seal/image',
    );

    expect(payload).toBeInstanceOf(FormData);
    expect(payload.get('file')).toBe(file);
  });

  it('applies the company seal explicitly', () => {
    signatureApi.applySeal('request-1');

    expect(mocks.post).toHaveBeenCalledWith(
      '/signature-requests/request-1/seal/apply',
    );
  });

  it('persists normalized company seal placement', () => {
    const placement = {
      page_number: 2,
      x: 0.625,
      y: 0.125,
      width: 0.2,
      height: 0.1,
    };

    signatureApi.updateSealPlacement(
      'request-1',
      placement,
    );

    expect(mocks.patch).toHaveBeenCalledWith(
      '/signature-requests/request-1/seal/placement',
      placement,
    );
  });
});
