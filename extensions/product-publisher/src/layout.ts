import { SIDEBAR_HOST_ID, SIDEBAR_WIDTH_PX } from './constants'

const STYLE_ID = 'odoo-pp-layout-style'

/**
 * Reserves horizontal space on the right so the host page UI is not
 * covered by our fixed sidebar.
 */
export function applySidebarLayout(): void {
  let style = document.getElementById(STYLE_ID) as HTMLStyleElement | null
  if (!style) {
    style = document.createElement('style')
    style.id = STYLE_ID
    document.documentElement.appendChild(style)
  }

  style.textContent = `
    html {
      box-sizing: border-box;
    }
    body {
      padding-right: ${SIDEBAR_WIDTH_PX}px !important;
      box-sizing: border-box;
    }
  `
}

export function clearSidebarLayout(): void {
  document.getElementById(STYLE_ID)?.remove()
}

/** Resize the extension host for open vs collapsed modes. */
export function syncSidebarChrome(open: boolean): void {
  const host = document.getElementById(SIDEBAR_HOST_ID)
  if (!host) return

  if (open) {
    Object.assign(host.style, {
      position: 'fixed',
      top: '0',
      right: '0',
      width: `${SIDEBAR_WIDTH_PX}px`,
      height: '100vh',
      zIndex: '2147483000',
      pointerEvents: 'auto',
    } satisfies Partial<CSSStyleDeclaration>)
    applySidebarLayout()
  } else {
    Object.assign(host.style, {
      position: 'fixed',
      top: 'auto',
      bottom: '80px',
      right: '20px',
      width: 'auto',
      height: 'auto',
      zIndex: '2147483000',
      pointerEvents: 'auto',
    } satisfies Partial<CSSStyleDeclaration>)
    clearSidebarLayout()
  }
}
