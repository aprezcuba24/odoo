/**
 * Facebook create-post composer fill (unused in current build).
 * Copied from the Vendelo360 Facebook extension for a future Facebook panel.
 * Do not register in the manifest until Facebook support is enabled.
 */

import { SIDEBAR_HOST_ID } from './constants'
import { syncSidebarChrome } from './layout'

export type FillFacebookComposerMessage = {
  type: 'FILL_COMPOSER'
  text: string
  html: string
  imageBase64: string | null
  imageMime: string | null
}

export type FillFacebookComposerResult = {
  ok: true
  filled: boolean
  imageAttached: boolean
  dialogVisible: boolean
}

const BANNER_ID = 'odoo-pp-fb-banner'

let fillInFlight: Promise<FillFacebookComposerResult> | null = null

function showBanner(message: string, tone: 'info' | 'warn' = 'info'): void {
  document.getElementById(BANNER_ID)?.remove()
  const el = document.createElement('div')
  el.id = BANNER_ID
  el.setAttribute('role', 'status')
  el.textContent = message
  Object.assign(el.style, {
    position: 'fixed',
    top: '12px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: '2147483647',
    maxWidth: 'min(520px, 92vw)',
    padding: '12px 16px',
    borderRadius: '10px',
    fontFamily: 'system-ui, sans-serif',
    fontSize: '14px',
    lineHeight: '1.4',
    boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
    background: tone === 'warn' ? '#5c2818' : '#1e3a5f',
    color: '#fff',
  })
  document.documentElement.appendChild(el)
}

function isVisible(el: HTMLElement): boolean {
  const rect = el.getBoundingClientRect()
  if (rect.width < 8 || rect.height < 8) return false
  const style = window.getComputedStyle(el)
  if (
    style.display === 'none' ||
    style.visibility === 'hidden' ||
    style.opacity === '0'
  ) {
    return false
  }
  return true
}

/**
 * The create-post modal (not the inline feed strip / comments).
 */
function findCreatePostDialog(): HTMLElement | null {
  const dialogs = document.querySelectorAll('div[role="dialog"]')
  for (const node of dialogs) {
    if (!(node instanceof HTMLElement) || !isVisible(node)) continue
    const hasEditable = node.querySelector('[contenteditable="true"]')
    if (!hasEditable) continue
    const label = (
      node.getAttribute('aria-label') ||
      node.innerText ||
      ''
    ).toLowerCase()
    if (
      label.includes('crear publicación') ||
      label.includes('create post') ||
      label.includes('publicar') ||
      label.includes('post') ||
      label.includes('escribe') ||
      label.includes('write')
    ) {
      return node
    }
    // Large centered dialog with a textbox is almost always the composer.
    const rect = node.getBoundingClientRect()
    if (rect.width >= 320 && rect.height >= 200) return node
  }
  return null
}

function findComposerBoxInDialog(dialog: HTMLElement): HTMLElement | null {
  const textboxes = dialog.querySelectorAll(
    '[contenteditable="true"][role="textbox"]',
  )
  let best: HTMLElement | null = null
  for (const node of textboxes) {
    if (!(node instanceof HTMLElement) || !isVisible(node)) continue
    if (!best || best.contains(node)) best = node
  }
  if (best) return best

  const any = dialog.querySelector('[contenteditable="true"]')
  return any instanceof HTMLElement && isVisible(any) ? any : null
}

function findComposerTrigger(): HTMLElement | null {
  const candidates: HTMLElement[] = []
  const selectors = [
    '[aria-label*="Escribe algo" i]',
    '[aria-label*="Write something" i]',
    '[aria-label*="Create a public post" i]',
    '[aria-label*="Crear una publicación" i]',
    '[role="button"]',
  ]
  for (const sel of selectors) {
    for (const node of document.querySelectorAll(sel)) {
      if (!(node instanceof HTMLElement) || !isVisible(node)) continue
      const label = (
        node.getAttribute('aria-label') ||
        node.textContent ||
        ''
      ).toLowerCase()
      if (
        label.includes('escribe algo') ||
        label.includes('write something') ||
        label.includes('crear una publicación') ||
        label.includes('create a public post') ||
        label.includes("what's on your mind") ||
        label.includes('qué estás pensando')
      ) {
        candidates.push(node)
      }
    }
  }
  // Prefer triggers near the top of the feed (create post), not comments.
  candidates.sort(
    (a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top,
  )
  return candidates[0] ?? null
}

function readComposerPlain(box: HTMLElement): string {
  return (box.innerText || box.textContent || '').replace(/\u00a0/g, ' ').trim()
}

/** True when our post appears. */
function composerLooksFilled(box: HTMLElement, text: string): boolean {
  const content = readComposerPlain(box)
  if (!content) return false
  // Check if the first line of our text appears
  const firstLine = text.split('\n')[0]?.trim()
  if (!firstLine) return false
  return content.includes(firstLine)
}

function selectAllIn(box: HTMLElement): void {
  box.focus()
  try {
    document.execCommand('selectAll', false)
  } catch {
    const selection = window.getSelection()
    if (!selection) return
    const range = document.createRange()
    range.selectNodeContents(box)
    selection.removeAllRanges()
    selection.addRange(range)
  }
}

function clearComposerBox(box: HTMLElement): void {
  box.focus()
  selectAllIn(box)
  // Delete current selection
  try {
    document.execCommand('delete', false)
  } catch {
    // Fallback: set innerHTML empty (may not work with Lexical)
    box.innerHTML = ''
  }
  // Ensure it's empty
  box.textContent = ''
}

/**
 * Lexical (Facebook) duplicates text if you use execCommand('insertText')
 * and/or synthetic InputEvent with data — native insert + beforeinput both fire.
 * Paste replaces the current selection in one Lexical update. Do that only.
 * Include text/html so the price can stay bold and links stay real links.
 */
function pasteReplacingSelection(
  box: HTMLElement,
  text: string,
  html?: string,
): void {
  box.focus()
  selectAllIn(box)
  const dt = new DataTransfer()
  dt.setData('text/plain', text)
  if (html) dt.setData('text/html', html)
  box.dispatchEvent(
    new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: dt,
    }),
  )
}

async function waitFrames(n = 2): Promise<void> {
  for (let i = 0; i < n; i++) {
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  }
}

/** 
 * Clear composer and paste new content.
 * Always clears first to avoid duplicates when reopening.
 */
async function setComposerText(
  box: HTMLElement,
  text: string,
  html?: string,
): Promise<boolean> {
  // First, clear any existing content
  clearComposerBox(box)
  await waitFrames(1)
  
  // Then paste the new content
  pasteReplacingSelection(box, text, html)
  await waitFrames(2)
  if (composerLooksFilled(box, text)) return true

  // Retry if it didn't work
  clearComposerBox(box)
  await waitFrames(1)
  pasteReplacingSelection(box, text, html)
  await waitFrames(2)
  
  return composerLooksFilled(box, text)
}

function findFileInput(dialog: HTMLElement): HTMLInputElement | null {
  const inputs = dialog.querySelectorAll('input[type="file"]')
  for (const input of inputs) {
    if (input instanceof HTMLInputElement) return input
  }
  return null
}

/**
 * Remove any previously attached images by clicking close/remove buttons.
 * Facebook shows a small X button on attached images.
 */
function clearAttachedImages(dialog: HTMLElement): void {
  // Look for close/remove buttons on image previews
  // Common patterns: aria-label contains "remove", "delete", "eliminar", "quitar"
  const removeButtons = dialog.querySelectorAll(
    'div[aria-label*="emove" i], div[aria-label*="liminar" i], div[aria-label*="uitar" i], ' +
    'div[aria-label*="elete" i], div[role="button"][aria-label*="Quitar" i]'
  )
  for (const btn of removeButtons) {
    if (btn instanceof HTMLElement && isVisible(btn)) {
      // Check if this button is near an image (within image preview area)
      const hasImageNearby = btn.closest('[role="dialog"]')?.querySelector('img[src*="blob:"], img[src*="data:"]')
      if (hasImageNearby) {
        btn.click()
      }
    }
  }
}

async function attachImage(
  dialog: HTMLElement,
  base64: string,
  mime: string,
): Promise<boolean> {
  // First, clear any previously attached images
  clearAttachedImages(dialog)
  await sleep(300)
  
  const input = findFileInput(dialog)
  if (!input) return false

  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  const blob = new Blob([bytes], { type: mime })
  const ext = mime.includes('png') ? 'png' : mime.includes('webp') ? 'webp' : 'jpg'
  const file = new File([blob], `product.${ext}`, { type: mime })
  const transfer = new DataTransfer()
  transfer.items.add(file)
  input.files = transfer.files
  input.dispatchEvent(new Event('change', { bubbles: true }))
  input.dispatchEvent(new Event('input', { bubbles: true }))
  return true
}

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms))
}

/** Hide our sidebar so Facebook's centered modal is not covered. */
function hideSidebarForModal(): void {
  const host = document.getElementById(SIDEBAR_HOST_ID)
  if (host) host.style.display = 'none'
  syncSidebarChrome(false)
}

function restoreSidebar(): void {
  const host = document.getElementById(SIDEBAR_HOST_ID)
  if (host) host.style.display = ''
  syncSidebarChrome(true)
}

async function openCreatePostDialog(): Promise<HTMLElement | null> {
  hideSidebarForModal()

  let dialog = findCreatePostDialog()
  if (dialog) return dialog

  const trigger = findComposerTrigger()
  if (!trigger) return null

  trigger.scrollIntoView({ block: 'center', behavior: 'instant' })
  await sleep(200)
  trigger.click()

  for (let i = 0; i < 15; i++) {
    await sleep(400)
    dialog = findCreatePostDialog()
    if (dialog) {
      dialog.scrollIntoView({ block: 'center', behavior: 'instant' })
      return dialog
    }
  }
  return null
}

export async function fillFacebookComposer(message: FillFacebookComposerMessage): Promise<FillFacebookComposerResult> {
  if (fillInFlight) return fillInFlight

  fillInFlight = (async () => {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/plain': new Blob([message.text], { type: 'text/plain' }),
          ...(message.html
            ? {
                'text/html': new Blob([message.html], { type: 'text/html' }),
              }
            : {}),
        }),
      ])
    } catch {
      await navigator.clipboard.writeText(message.text).catch(() => undefined)
    }

    try {
      const dialog = await openCreatePostDialog()
      if (!dialog) {
        showBanner(
          'No se abrió el diálogo «Crear publicación». Usa Reintentar en el panel o ábrelo a mano y pega (Ctrl+V).',
          'warn',
        )
        restoreSidebar()
        return { ok: true, filled: false, imageAttached: false, dialogVisible: false }
      }

      const box = findComposerBoxInDialog(dialog)
      if (!box) {
        showBanner(
          'Se abrió el diálogo pero no hay cuadro de texto. Usa Reintentar en el panel o pega con Ctrl+V.',
          'warn',
        )
        return { ok: true, filled: false, imageAttached: false, dialogVisible: true }
      }

      // Attach image first when possible — Facebook sometimes resets caption on photo add.
      let imageAttached = false
      if (message.imageBase64 && message.imageMime) {
        imageAttached = await attachImage(dialog, message.imageBase64, message.imageMime)
        await sleep(600)
      }

      const dialogNow = findCreatePostDialog() ?? dialog
      const boxNow = findComposerBoxInDialog(dialogNow) ?? box

      // Exactly one write path (paste-replace). Do not stack insertText / InputEvent.
      let filled = await setComposerText(boxNow, message.text, message.html)

      const dialogStillOpen = Boolean(findCreatePostDialog())

      if (filled && dialogStillOpen) {
        // showBanner(
        //   imageAttached
        //     ? 'Listo: mira el diálogo «Crear publicación» en el centro y pulsa Publicar.'
        //     : message.imageBase64
        //       ? 'Texto listo en el diálogo. Adjunta la foto a mano y pulsa Publicar.'
        //       : 'Texto listo en el diálogo. Revisa y pulsa Publicar.',
        // )
      } else if (filled && !dialogStillOpen) {
        showBanner(
          'El texto se escribió pero el diálogo se cerró. Usa Reintentar en el panel o ábrelo y pega con Ctrl+V.',
          'warn',
        )
        filled = false
      } else {
        showBanner(
          'No se pudo escribir el texto. Usa Reintentar en el panel o pega con Ctrl+V y publica.',
          'warn',
        )
      }

      return {
        ok: true,
        filled: filled && dialogStillOpen,
        imageAttached,
        dialogVisible: dialogStillOpen,
      }
    } finally {
      setTimeout(() => restoreSidebar(), 2500)
    }
  })()

  try {
    return await fillInFlight
  } finally {
    fillInFlight = null
  }
}

