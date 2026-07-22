import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), '');
  const apiBaseUrl =
    process.env.VITE_API_BASE_URL ||
    fileEnv.VITE_API_BASE_URL;

  if (mode === 'production' && !apiBaseUrl?.trim()) {
    throw new Error(
      'VITE_API_BASE_URL must be configured for production builds',
    );
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
    },
  };
});
