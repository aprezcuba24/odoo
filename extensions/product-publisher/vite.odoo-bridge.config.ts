import path from 'node:path'
import { defineConfig } from 'vite'
import { rootDir } from './manifest.shared.ts'

/**
 * Odoo page bridge (IIFE). Run after vite.extension.config.ts.
 */
export default defineConfig(() => {
  return {
    define: {
      'process.env.NODE_ENV': JSON.stringify('production'),
    },
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
        input: path.resolve(rootDir, 'src/odoo-bridge.ts'),
        output: {
          format: 'iife',
          name: 'OdooProductPublisherBridge',
          entryFileNames: 'odoo-bridge.js',
          inlineDynamicImports: true,
        },
      },
    },
  }
})
