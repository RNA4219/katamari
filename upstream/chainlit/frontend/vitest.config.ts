/// <reference types="vitest" />
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';
import tsconfigPaths from 'vite-tsconfig-paths';

const reactClientStub = fileURLToPath(
  new URL('./tests/stubs/chainlit-react-client.ts', import.meta.url)
);

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  resolve: {
    alias: {
      '@chainlit/react-client': reactClientStub
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: './tests/setup-tests.ts',
    include: ['./**/*.{test,spec}.?(c|m)[jt]s?(x)']
  }
});
