export type FillWhatsAppComposerMessage = {
  type: 'FILL_WHATSAPP_COMPOSER'
  text: string
  imageBase64: string | null
  imageMime: string | null
}

export type FillWhatsAppComposerResult =
  | { ok: true; filled: boolean; imageAttached: boolean }
  | { ok: false; error: string }

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function isVisible(el: HTMLElement): boolean {
  const rect = el.getBoundingClientRect()
  if (rect.width < 4 || rect.height < 4) return false
  const style = window.getComputedStyle(el)
  return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'
}

function findFooterComposer(): HTMLElement | null {
  const main = document.querySelector('#main')
  if (!main) return null
  const footer = main.querySelector('footer')
  if (!footer) return null

  const candidates = footer.querySelectorAll(
    '[contenteditable="true"][data-tab="10"], [contenteditable="true"][role="textbox"]',
  )
  for (const node of candidates) {
    if (node instanceof HTMLElement && isVisible(node)) return node
  }
  const any = footer.querySelector('[contenteditable="true"]')
  return any instanceof HTMLElement && isVisible(any) ? any : null
}

function captionLabel(box: HTMLElement): string {
  return [
    box.getAttribute('aria-label'),
    box.getAttribute('aria-placeholder'),
    box.getAttribute('data-placeholder'),
    box.getAttribute('title'),
  ]
    .filter(Boolean)
    .join(' ')
}

function looksLikeCaption(box: HTMLElement): boolean {
  return /comentario|caption|comment/i.test(captionLabel(box))
}

/** Caption field that appears after pasting a photo into the message box. */
function findCaptionComposer(chatComposer: HTMLElement): HTMLElement | null {
  const editables = document.querySelectorAll('[contenteditable="true"]')
  for (const node of editables) {
    if (!(node instanceof HTMLElement) || !isVisible(node)) continue
    if (looksLikeCaption(node)) return node
  }

  for (const node of editables) {
    if (!(node instanceof HTMLElement) || !isVisible(node)) continue
    if (node === chatComposer) continue
    let parent: HTMLElement | null = node
    for (let depth = 0; depth < 8 && parent; depth++) {
      if (parent.querySelector('img[src^="blob:"], canvas, video')) return node
      parent = parent.parentElement
    }
  }

  return null
}

async function waitForCaptionComposer(
  chatComposer: HTMLElement,
  timeoutMs = 10000,
): Promise<HTMLElement | null> {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const box = findCaptionComposer(chatComposer)
    if (box) return box
    await sleep(200)
  }
  return null
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
  try {
    document.execCommand('delete', false)
  } catch {
    box.textContent = ''
  }
}

/** Paste on the caption node. insertText follows the chat selection and misses the caption. */
function insertComposerText(box: HTMLElement, text: string): void {
  box.focus()
  selectAllIn(box)
  const dt = new DataTransfer()
  dt.setData('text/plain', text)
  box.dispatchEvent(
    new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: dt,
    }),
  )
}

function composerLooksFilled(box: HTMLElement, text: string): boolean {
  const content = (box.innerText || box.textContent || '').replace(/\u00a0/g, ' ').trim()
  if (!content) return false
  const firstLine = text.split('\n')[0]?.trim()
  if (!firstLine) return content.length > 0
  return content.includes(firstLine)
}

async function setComposerText(box: HTMLElement, text: string): Promise<boolean> {
  clearComposerBox(box)
  await sleep(80)
  insertComposerText(box, text)
  await sleep(200)
  if (composerLooksFilled(box, text)) return true

  clearComposerBox(box)
  await sleep(80)
  insertComposerText(box, text)
  await sleep(200)
  return composerLooksFilled(box, text)
}

function base64ToFile(base64: string, mime: string): File {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  const copy = new Uint8Array(bytes.byteLength)
  copy.set(bytes)
  const ext = mime.includes('png') ? 'png' : mime.includes('webp') ? 'webp' : 'jpg'
  return new File([copy], `product.${ext}`, { type: mime })
}

/** Same path as pasting a photo into the message box: image plus caption field. */
function pasteImage(box: HTMLElement, file: File): void {
  box.focus()
  const dt = new DataTransfer()
  dt.items.add(file)
  box.dispatchEvent(
    new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: dt,
    }),
  )
}

function pasteImageIntoComposer(base64: string, mime: string, chatComposer: HTMLElement): void {
  if (findCaptionComposer(chatComposer)) return
  pasteImage(chatComposer, base64ToFile(base64, mime))
}

export async function fillWhatsAppComposer(
  message: FillWhatsAppComposerMessage,
): Promise<FillWhatsAppComposerResult> {
  if (!window.location.hostname.includes('whatsapp.com')) {
    return { ok: false, error: 'Esta acción solo funciona en WhatsApp Web' }
  }

  const footer = findFooterComposer()
  if (!footer) {
    return {
      ok: false,
      error: 'Abre un chat o grupo en WhatsApp y vuelve a pulsar Publicar.',
    }
  }

  const hasImage = Boolean(message.imageBase64 && message.imageMime)

  if (hasImage && message.imageBase64 && message.imageMime) {
    pasteImageIntoComposer(message.imageBase64, message.imageMime, footer)

    // Image-only block: no caption text needed.
    if (!message.text.trim()) {
      await sleep(500)
      return { ok: true, filled: true, imageAttached: true }
    }

    const caption = await waitForCaptionComposer(footer)
    if (!caption) {
      return {
        ok: false,
        error: 'Se abrió la foto sin el cuadro de comentario. Ciérrala y vuelve a pulsar Publicar.',
      }
    }

    const filled = await setComposerText(caption, message.text)
    if (!filled) {
      return {
        ok: false,
        error: 'No se pudo escribir el texto en el comentario de la imagen.',
      }
    }
    return { ok: true, filled: true, imageAttached: true }
  }

  const filled = await setComposerText(footer, message.text)
  if (!filled) {
    return { ok: false, error: 'No se pudo escribir el texto en el chat.' }
  }
  return { ok: true, filled: true, imageAttached: false }
}
