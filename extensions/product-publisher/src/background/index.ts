import type { ExtensionMessage, ExtensionResponse } from '../messaging'
import {
  clearPublishQueue,
  clearReadyIds,
  isQueueItem,
  markItemReady,
  parsePublishQueue,
  readPublishQueue,
  writePublishQueue,
} from '../publish-queue'
import { buildProductPostText } from '../post-text'

async function handleStartPublish(message: {
  items: unknown
}): Promise<ExtensionResponse> {
  if (!Array.isArray(message.items) || !message.items.every(isQueueItem)) {
    return { ok: false, error: 'Items inválidos' }
  }
  if (message.items.length === 0) {
    return { ok: false, error: 'Selecciona al menos un item' }
  }

  const queue = parsePublishQueue({
    items: message.items,
    startedAt: Date.now(),
    readyIds: [],
  })
  if (!queue) {
    return { ok: false, error: 'Cola de publicación inválida' }
  }

  await writePublishQueue(queue)
  return { ok: true }
}

async function handleClearReadyIds(): Promise<ExtensionResponse> {
  await clearReadyIds()
  return { ok: true }
}

async function handleClearPublishQueue(): Promise<ExtensionResponse> {
  await clearPublishQueue()
  return { ok: true }
}

async function handleFillWhatsAppItem(
  itemId: string,
  senderTabId: number | undefined,
): Promise<ExtensionResponse> {
  if (senderTabId == null) {
    return { ok: false, error: 'No hay pestaña activa' }
  }

  const queue = await readPublishQueue()
  if (!queue || queue.items.length === 0) {
    return { ok: false, error: 'No hay cola de publicación' }
  }
  const item = queue.items.find((row) => row.id === itemId)
  if (!item) {
    return { ok: false, error: 'Item no encontrado en la cola' }
  }

  let composerMessage: {
    type: 'FILL_WHATSAPP_COMPOSER'
    text: string
    imageBase64: string | null
    imageMime: string | null
  }

  if (item.type === 'product') {
    composerMessage = {
      type: 'FILL_WHATSAPP_COMPOSER',
      text: buildProductPostText(item.name, item.price),
      imageBase64: item.imageBase64,
      imageMime: item.imageMime,
    }
  } else if (item.kind === 'text') {
    // Block with plain text (e.g. a category header, an emoji)
    composerMessage = {
      type: 'FILL_WHATSAPP_COMPOSER',
      text: item.text,
      imageBase64: null,
      imageMime: null,
    }
  } else {
    // Block with sticker image only
    composerMessage = {
      type: 'FILL_WHATSAPP_COMPOSER',
      text: '',
      imageBase64: item.imageBase64,
      imageMime: item.imageMime,
    }
  }

  let lastError: string | null = null

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const result = (await chrome.tabs.sendMessage(senderTabId, composerMessage)) as ExtensionResponse

      if (result && typeof result === 'object' && 'ok' in result) {
        if (!result.ok) return result
        if ('filled' in result && result.filled) {
          await markItemReady(itemId)
          return {
            ok: true,
            filled: result.filled,
            imageAttached:
              'imageAttached' in result ? Boolean(result.imageAttached) : false,
          }
        }
      }
      break
    } catch (err) {
      lastError = err instanceof Error ? err.message : 'No se pudo contactar la pestaña'
      await new Promise((resolve) => setTimeout(resolve, 800))
    }
  }

  return {
    ok: false,
    error: lastError ?? 'No se pudo rellenar el chat de WhatsApp. Vuelve a pulsar Publicar.',
  }
}

async function dispatch(
  message: ExtensionMessage,
  senderTabId?: number,
): Promise<ExtensionResponse> {
  switch (message.type) {
    case 'START_PUBLISH':
      return handleStartPublish(message)
    case 'CLEAR_PUBLISH_QUEUE':
      return handleClearPublishQueue()
    case 'CLEAR_READY_IDS':
      return handleClearReadyIds()
    case 'FILL_WHATSAPP_ITEM':
      return handleFillWhatsAppItem(message.itemId, senderTabId)
    default:
      return { ok: false, error: 'Mensaje desconocido' }
  }
}

chrome.runtime.onMessage.addListener((message: ExtensionMessage, sender, sendResponse) => {
  void (async () => {
    sendResponse(await dispatch(message, sender.tab?.id))
  })()
  return true
})
