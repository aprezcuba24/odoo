import { createRoot, type Root } from 'react-dom/client'
import { SIDEBAR_HOST_ID, SIDEBAR_WIDTH_PX } from '../constants'
import { syncSidebarChrome } from '../layout'
import { App } from './App'
import styles from './styles.css?inline'

export type SidebarHandle = {
  unmount: () => void
}

export function mountSidebar(): SidebarHandle {
  let host = document.getElementById(SIDEBAR_HOST_ID)
  if (!host) {
    host = document.createElement('div')
    host.id = SIDEBAR_HOST_ID
    document.documentElement.appendChild(host)
  }

  Object.assign(host.style, {
    position: 'fixed',
    top: '0',
    right: '0',
    width: `${SIDEBAR_WIDTH_PX}px`,
    height: '100vh',
    zIndex: '2147483000',
    pointerEvents: 'auto',
  } satisfies Partial<CSSStyleDeclaration>)
  syncSidebarChrome(true)

  const shadow = host.shadowRoot ?? host.attachShadow({ mode: 'open' })
  shadow.replaceChildren()

  const styleEl = document.createElement('style')
  styleEl.textContent = styles
  shadow.appendChild(styleEl)

  const mountPoint = document.createElement('div')
  mountPoint.style.height = '100%'
  shadow.appendChild(mountPoint)

  const root: Root = createRoot(mountPoint)
  root.render(<App />)

  return {
    unmount: () => {
      root.unmount()
      host?.remove()
    },
  }
}
