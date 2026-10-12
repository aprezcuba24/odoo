import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadEnv } from 'vite'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

export function loadBuildEnv(mode: string): Record<string, string> {
  return loadEnv(mode, rootDir, '')
}

export function resolveOdooOrigin(): string {
  const raw = process.env.VITE_ODOO_ORIGIN || 'http://localhost:8069'
  try {
    return new URL(raw).origin
  } catch {
    return 'http://localhost:8069'
  }
}

export function buildManifest(): Record<string, unknown> {
  const odooOrigin = resolveOdooOrigin()

  return {
    manifest_version: 3,
    name: 'Publicador de productos',
    description:
      'Recibe productos desde Odoo y los prepara para publicar (WhatsApp Web).',
    version: '0.1.0',
    icons: {
      '16': 'icons/icon16.png',
      '48': 'icons/icon48.png',
      '128': 'icons/icon128.png',
    },
    action: {
      default_popup: 'popup.html',
      default_title: 'Publicador de productos',
      default_icon: {
        '16': 'icons/icon16.png',
        '48': 'icons/icon48.png',
        '128': 'icons/icon128.png',
      },
    },
    background: {
      service_worker: 'background.js',
      type: 'module',
    },
    permissions: ['storage', 'tabs'],
    host_permissions: ['https://web.whatsapp.com/*', `${odooOrigin}/*`],
    content_scripts: [
      {
        matches: ['https://web.whatsapp.com/*'],
        js: ['content.js'],
        run_at: 'document_idle',
      },
      {
        matches: [`${odooOrigin}/*`],
        js: ['odoo-bridge.js'],
        run_at: 'document_idle',
      },
    ],
  }
}

export { rootDir }
