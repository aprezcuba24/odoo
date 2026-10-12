import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'
import { loadBuildEnv, rootDir } from './manifest.shared.ts'

/**
 * Service worker + popup build. Run after the content script build.
 * Does not empty dist/ so content.js and icons are kept.
 */
export default defineConfig(({ mode }) => {
  const env = loadBuildEnv(mode)
  const odooOrigin = env.VITE_ODOO_ORIGIN || process.env.VITE_ODOO_ORIGIN || 'http://localhost:8069'

  return {
    base: './',
    define: {
      'process.env.NODE_ENV': JSON.stringify('production'),
      'import.meta.env.VITE_ODOO_ORIGIN': JSON.stringify(odooOrigin),
    },
    plugins: [react()],
    publicDir: false as const,
    resolve: {
      alias: {
        '@': path.resolve(rootDir, './src'),
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: false,
      cssCodeSplit: false,
      modulePreload: false,
      target: 'es2022',
      minify: true,
      rollupOptions: {
        input: {
          background: path.resolve(rootDir, 'src/background/index.ts'),
          popup: path.resolve(rootDir, 'popup.html'),
        },
        output: {
          entryFileNames: (chunk) =>
            chunk.name === 'background' ? 'background.js' : 'assets/[name]-[hash].js',
          chunkFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash][extname]',
        },
      },
    },
  }
})
