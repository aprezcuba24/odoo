import { useEffect, useState } from 'react'
import { SIDEBAR_OPEN_STORAGE_KEY } from '../constants'
import { syncSidebarChrome } from '../layout'
import AppIcon from '../icon'
import { Queue } from './Queue'

function readTheme(): 'dark' | 'light' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readSidebarOpen(): boolean {
  try {
    const raw = localStorage.getItem(SIDEBAR_OPEN_STORAGE_KEY)
    if (raw === null) return true
    return raw === '1' || raw === 'true'
  } catch {
    return true
  }
}

function writeSidebarOpen(open: boolean): void {
  try {
    localStorage.setItem(SIDEBAR_OPEN_STORAGE_KEY, open ? '1' : '0')
  } catch {
    // ignore
  }
}

function CloseIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  )
}

export function App() {
  const [theme, setTheme] = useState<'dark' | 'light'>(readTheme)
  const [open, setOpen] = useState(readSidebarOpen)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const sync = () => setTheme(mq.matches ? 'dark' : 'light')
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    syncSidebarChrome(open)
    writeSidebarOpen(open)
  }, [open])

  if (!open) {
    return (
      <button
        type="button"
        className="fab-show"
        data-theme={theme}
        title="Mostrar Publicador de productos"
        aria-label="Mostrar Publicador de productos"
        onClick={() => setOpen(true)}
      >
        <AppIcon size={28} alt="Publicador" />
      </button>
    )
  }

  return (
    <div className="panel" data-theme={theme}>
      <header className="header">
        <div className="header-top">
          <div className="brand">
            <div className="brand-icon">
              <AppIcon size={22} alt="Publicador" />
            </div>
            <div>
              <h1 className="brand-title">Publicador</h1>
              <p className="brand-subtitle">WhatsApp</p>
            </div>
          </div>
          <div className="header-actions">
            <button
              type="button"
              className="btn-hide"
              title="Ocultar panel"
              aria-label="Ocultar panel"
              onClick={() => setOpen(false)}
            >
              <CloseIcon />
            </button>
          </div>
        </div>
      </header>

      <div className="body">
        <Queue />
      </div>
    </div>
  )
}
