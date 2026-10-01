import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In Docker the API lives at http://backend:8000; locally at http://localhost:8000.
const target = process.env.API_PROXY_TARGET ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target, changeOrigin: true } } },
});
