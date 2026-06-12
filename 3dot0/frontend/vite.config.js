import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // Use 'generateSW' strategy — Vite builds a proper service worker
      strategies: 'generateSW',
      // Expose the SW registration in DevTools
      devOptions: { enabled: true, type: 'module' },
      includeAssets: ['icon-192.png', 'icon-512.png', 'manifest.json'],
      manifest: {
        name: 'JARVIS Command Center',
        short_name: 'JARVIS',
        description: 'JARVIS v3.0 — Your personal asynchronous AI secretary',
        theme_color: '#020917',
        background_color: '#020917',
        display: 'standalone',
        orientation: 'any',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Don't cache the WS endpoint
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api/, /^\/ws/, /^\/docs/, /^\/redoc/],
        runtimeCaching: [
          {
            // API reads: network-first, 60s cache
            urlPattern: /^https?:\/\/.*\/api\/v1\/(feed|tasks|journal|routines|skills|users).*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 },
              networkTimeoutSeconds: 10,
            },
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
