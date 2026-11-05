import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      frontendRoute: '/lyqd',
      buildConfig: {
        outDir: '../lyqd/public/frontend',
        indexHtmlPath: '../lyqd/www/lyqd.html',
        emptyOutDir: true,
        sourcemap: true,
      },
    }),
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      devOptions: {
        enabled: false,
      },
      workbox: {
        // Avoid workbox+terser "Unexpected early exit" on some Node builds.
        mode: 'development',
        cleanupOutdatedCaches: true,
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        globPatterns: ['**/*.{js,css,html,svg,png,ico,webp}'],
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.destination === 'document',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'lyqd-html-cache',
            },
          },
        ],
      },
      // Manifest is served by lyqd.api.spa.get_pwa_manifest (LMS-style), not embedded.
      manifest: false,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      // frappe-ui 0.1.x exports `toast` from the package root but not the host.
      'frappe-ui/toasts': path.resolve(
        __dirname,
        'node_modules/frappe-ui/src/components/Toast/index.ts',
      ),
    },
  },
  build: {
    outDir: '../lyqd/public/frontend',
    emptyOutDir: true,
    target: 'esnext',
    commonjsOptions: {
      include: [/tailwind.config.js/, /node_modules/],
    },
    sourcemap: true,
  },
  optimizeDeps: {
    include: ['feather-icons', 'tailwind.config.js', 'engine.io-client'],
  },
  server: {
    port: 8081,
  },
})
