import {
  PRE_SEND_MS,
  SEND_CONFIRM_TIMEOUT_MS,
  paceMs,
  sleep,
} from './whatsapp-pacing'

export type FillWhatsAppComposerMessage = {
  type: 'FILL_WHATSAPP_COMPOSER'
  text: string
  imageBase64: string | null
  imageMime: string | null
}

export type PublishWhatsAppComposerMessage = {
  type: 'PUBLISH_WHATSAPP_COMPOSER'
  text: string
  imageBase64: string | null
  imageMime: string | null
}

export type FillWhatsAppComposerResult =
  | { ok: true; filled: boolean; imageAttached: boolean }
  | { ok: false; error: string }

export type PublishWhatsAppComposerResult =
  | { ok: true; filled: boolean; imageAttached: boolean; sent: true }
  | { ok: false; error: string }

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

function mediaPreviewOpen(chatComposer: HTMLElement | null): boolean {
  if (!chatComposer) {
    const any = document.querySelector('[contenteditable="true"]')
    if (!(any instanceof HTMLElement)) return false
    return Boolean(findCaptionComposer(any))
  }
  return Boolean(findCaptionComposer(chatComposer))
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

function composerIsEmpty(box: HTMLElement | null): boolean {
  if (!box) return true
  const content = (box.innerText || box.textContent || '').replace(/\u00a0/g, ' ').trim()
  return content.length === 0
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

function controlLabel(el: HTMLElement): string {
  return [
    el.getAttribute('aria-label'),
    el.getAttribute('title'),
    el.getAttribute('data-icon'),
    el.textContent,
  ]
    .filter(Boolean)
    .join(' ')
    .trim()
}

function looksLikeSendControl(el: HTMLElement): boolean {
  const label = controlLabel(el)
  if (/enviar|send/i.test(label)) return true
  const dataIcon = el.getAttribute('data-icon') || ''
  if (/^send$/i.test(dataIcon)) return true
  if (el.querySelector('[data-icon="send"]')) return true
  return false
}

function findSendButton(preferMediaPreview: boolean): HTMLElement | null {
  const selectors = [
    'button[aria-label]',
    '[role="button"][aria-label]',
    'span[data-icon="send"]',
    'button span[data-icon="send"]',
  ]
  const candidates: HTMLElement[] = []
  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((node) => {
      let el: HTMLElement | null = node instanceof HTMLElement ? node : null
      if (!el) return
      if (el.getAttribute('data-icon') === 'send') {
        el = el.closest('button, [role="button"]') as HTMLElement | null
      }
      if (!el || !isVisible(el) || !looksLikeSendControl(el)) return
      if (!candidates.includes(el)) candidates.push(el)
    })
  }

  if (candidates.length === 0) return null

  if (preferMediaPreview) {
    const inPreview = candidates.find((el) => {
      let parent: HTMLElement | null = el
      for (let depth = 0; depth < 12 && parent; depth++) {
        if (parent.querySelector?.('img[src^="blob:"], canvas, video')) return true
        if (looksLikeCaption(parent)) return true
        parent = parent.parentElement
      }
      return false
    })
    if (inPreview) return inPreview
  }

  const main = document.querySelector('#main')
  const footer = main?.querySelector('footer')
  if (footer) {
    const inFooter = candidates.find((el) => footer.contains(el))
    if (inFooter) return inFooter
  }

  return candidates[0] ?? null
}

function detectRateLimitMessage(): string | null {
  const bodyText = document.body?.innerText || ''
  const patterns = [
    /demasiado r[aá]pido/i,
    /too (?:many|fast)/i,
    /espera(?:r)?\s+(?:un\s+)?(?:momento|poco)/i,
    /try again later/i,
    /int[eé]ntalo de nuevo m[aá]s tarde/i,
    /couldn'?t send/i,
    /no se pudo enviar/i,
  ]
  for (const re of patterns) {
    if (re.test(bodyText)) {
      return 'WhatsApp indica que estás enviando demasiado rápido. Espera unos minutos y reanuda con Automático.'
    }
  }
  return null
}

async function waitUntilSent(imageAttached: boolean): Promise<boolean> {
  const started = Date.now()
  while (Date.now() - started < SEND_CONFIRM_TIMEOUT_MS) {
    const rateLimit = detectRateLimitMessage()
    if (rateLimit) return false

    const footer = findFooterComposer()
    const previewOpen = mediaPreviewOpen(footer)
    if (imageAttached) {
      if (!previewOpen && composerIsEmpty(footer)) return true
    } else if (!previewOpen && composerIsEmpty(footer)) {
      return true
    }
    await sleep(250)
  }
  return false
}

type FillPayload = {
  text: string
  imageBase64: string | null
  imageMime: string | null
}

async function fillComposer(
  message: FillPayload,
  options: { requireClearPreview: boolean },
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

  if (options.requireClearPreview && mediaPreviewOpen(footer)) {
    return {
      ok: false,
      error: 'Cierra la vista previa de la foto en WhatsApp y vuelve a intentar.',
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

export async function fillWhatsAppComposer(
  message: FillWhatsAppComposerMessage,
): Promise<FillWhatsAppComposerResult> {
  return fillComposer(message, { requireClearPreview: false })
}

export async function publishWhatsAppComposer(
  message: PublishWhatsAppComposerMessage,
): Promise<PublishWhatsAppComposerResult> {
  const filled = await fillComposer(message, { requireClearPreview: true })
  if (!filled.ok) return filled

  await sleep(paceMs(PRE_SEND_MS))

  const rateBefore = detectRateLimitMessage()
  if (rateBefore) return { ok: false, error: rateBefore }

  const sendBtn = findSendButton(filled.imageAttached)
  if (!sendBtn) {
    return {
      ok: false,
      error: 'No se encontró el botón Enviar. Revisa el chat y reanuda con Automático.',
    }
  }

  sendBtn.click()

  const sent = await waitUntilSent(filled.imageAttached)
  if (!sent) {
    const rateAfter = detectRateLimitMessage()
    if (rateAfter) return { ok: false, error: rateAfter }
    return {
      ok: false,
      error: 'No se confirmó el envío. Revisa WhatsApp y reanuda con Automático.',
    }
  }

  return {
    ok: true,
    filled: true,
    imageAttached: filled.imageAttached,
    sent: true,
  }
}
