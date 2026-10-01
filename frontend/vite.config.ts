import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

// In Docker the API lives at http://backend:8000; locally at http://localhost:8010.
const target = process.env.API_PROXY_TARGET ?? 'http://localhost:8010';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'SpenDrip',
        short_name: 'SpenDrip',
        description: 'Money that shows up on time.',
        theme_color: '#0B1040',
        background_color: '#0B1040',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
      // Never cache API responses: balances must always be live.
      workbox: { navigateFallbackDenylist: [/^\/api\//, /^\/admin\//], runtimeCaching: [] },
    }),
  ],
  server: { port: 5173, proxy: { '/api': { target, changeOrigin: false }, '/admin': { target, changeOrigin: false }, '/static': { target, changeOrigin: false } } },
});
