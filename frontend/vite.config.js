import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), '');
  const apiBaseUrl =
    process.env.VITE_API_BASE_URL ||
    fileEnv.VITE_API_BASE_URL;

  if (mode === 'production') {
    if (!apiBaseUrl?.trim()) {
      throw new Error(
        'VITE_API_BASE_URL must be configured for production builds',
      );
    }

    let apiUrl;
    try {
      apiUrl = new URL(apiBaseUrl);
    } catch {
      throw new Error(
        'VITE_API_BASE_URL must be a valid absolute URL for production builds',
      );
    }

    const developmentHosts = new Set([
      'localhost',
      '127.0.0.1',
      '0.0.0.0',
    ]);

    if (developmentHosts.has(apiUrl.hostname)) {
      throw new Error(
        'VITE_API_BASE_URL cannot use a local development host '
        + 'for production builds',
      );
    }

    if (apiUrl.protocol !== 'https:') {
      throw new Error(
        'VITE_API_BASE_URL must use HTTPS for production builds',
      );
    }
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/tests/setup.js',
      alias: [
        {
          find: /^pdfjs-dist$/,
          replacement: 'pdfjs-dist/legacy/build/pdf.mjs',
        },
      ],
    },
  };
});
