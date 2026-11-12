import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

// In Docker the API lives at http://backend:8000; locally at http://localhost:8010.
const target = process.env.API_PROXY_TARGET ?? 'http://localhost:8010';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'prompt',  // a new version waits until the person taps Refresh (see components/UpdateBar.tsx)
      includeAssets: ['icon.svg', 'apple-touch-icon.png'],
      manifest: {
        id: '/',
        name: 'SpenDrip',
        short_name: 'SpenDrip',
        description: 'Money that shows up on time. Schedule money to yourself and the people you look after.',
        lang: 'en-NG',
        categories: ['finance', 'productivity'],
        orientation: 'portrait',
        theme_color: '#0B1040',
        background_color: '#0B1040',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
        // Android shows these in its install dialog, like an app store listing.
        screenshots: [
          { src: '/screenshots/home.png', sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Your balance, protected money and what your month needs' },
          { src: '/screenshots/plans.png', sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Plans in priority order' },
          { src: '/screenshots/welcome.png', sizes: '780x1688', type: 'image/png', form_factor: 'narrow', label: 'Top up once. Relax all month.' },
        ],
      },
      // push-sw.js (public/) shows notifications and opens the right screen when one is tapped.
      // Never cache API responses: balances must always be live. Do precache Kobo (kobo.riv + the Rive engine) for offline use.
      workbox: { importScripts: ['push-sw.js'], clientsClaim: true, cleanupOutdatedCaches: true, navigateFallbackDenylist: [/^\/api\//, /^\/admin\//], runtimeCaching: [], globPatterns: ['**/*.{js,css,html,svg,png,riv,wasm}'], globIgnores: ['screenshots/**'], maximumFileSizeToCacheInBytes: 3 * 1024 * 1024 },
    }),
  ],
  server: { port: 5173, proxy: { '/api': { target, changeOrigin: false }, '/admin': { target, changeOrigin: false }, '/static': { target, changeOrigin: false } } },
});
