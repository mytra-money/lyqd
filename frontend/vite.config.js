import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

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
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
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
