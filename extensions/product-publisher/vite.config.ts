import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import { viteStaticCopy } from 'vite-plugin-static-copy'
import { buildManifest, loadBuildEnv, rootDir } from './manifest.shared.ts'

function writeManifestPlugin(mode: string): Plugin {
  return {
    name: 'odoo-pp-write-manifest',
    closeBundle() {
      const env = loadBuildEnv(mode)
      if (env.VITE_ODOO_ORIGIN) process.env.VITE_ODOO_ORIGIN = env.VITE_ODOO_ORIGIN
      const manifest = buildManifest()
      const outPath = path.resolve(rootDir, 'dist/manifest.json')
      fs.mkdirSync(path.dirname(outPath), { recursive: true })
      fs.writeFileSync(outPath, `${JSON.stringify(manifest, null, 2)}\n`)
      console.info(`[product-publisher] wrote ${outPath}`)
    },
  }
}

/** Content script build (IIFE). Run first; empties dist/. */
export default defineConfig(({ mode }) => {
  const env = loadBuildEnv(mode)
  const odooOrigin = env.VITE_ODOO_ORIGIN || process.env.VITE_ODOO_ORIGIN || 'http://localhost:8069'

  return {
    define: {
      'process.env.NODE_ENV': JSON.stringify('production'),
      'import.meta.env.VITE_ODOO_ORIGIN': JSON.stringify(odooOrigin),
    },
    plugins: [
      react(),
      viteStaticCopy({
        targets: [{ src: 'public/icons', dest: '.' }],
      }),
      writeManifestPlugin(mode),
    ],
    publicDir: false as const,
    resolve: {
      alias: {
        '@': path.resolve(rootDir, './src'),
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      cssCodeSplit: false,
      modulePreload: false,
      target: 'es2022',
      minify: true,
      rollupOptions: {
        input: path.resolve(rootDir, 'src/content.ts'),
        output: {
          format: 'iife',
          name: 'OdooProductPublisher',
          entryFileNames: 'content.js',
          inlineDynamicImports: true,
          assetFileNames: 'assets/[name][extname]',
        },
      },
    },
  }
})
