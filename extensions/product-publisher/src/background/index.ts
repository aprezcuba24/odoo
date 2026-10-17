import type { ExtensionMessage, ExtensionResponse } from '../messaging'
import {
  clearPublishQueue,
  clearReadyIds,
  isQueueItem,
  markItemReady,
  parsePublishQueue,
  readPublishQueue,
  writePublishQueue,
  type QueueItem,
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

function buildComposerPayload(
  item: QueueItem,
  mode: 'fill' | 'publish',
):
  | {
      type: 'FILL_WHATSAPP_COMPOSER'
      text: string
      imageBase64: string | null
      imageMime: string | null
    }
  | {
      type: 'PUBLISH_WHATSAPP_COMPOSER'
      text: string
      imageBase64: string | null
      imageMime: string | null
    } {
  const text =
    item.type === 'product' ? buildProductPostText(item.name, item.price) : item.text
  const imageBase64 = item.type === 'product' ? item.imageBase64 : null
  const imageMime = item.type === 'product' ? item.imageMime : null

  if (mode === 'publish') {
    return {
      type: 'PUBLISH_WHATSAPP_COMPOSER',
      text,
      imageBase64,
      imageMime,
    }
  }
  return {
    type: 'FILL_WHATSAPP_COMPOSER',
    text,
    imageBase64,
    imageMime,
  }
}

async function sendComposerToTab(
  senderTabId: number,
  composerMessage: ReturnType<typeof buildComposerPayload>,
  options: { markReadyOn: 'filled' | 'sent'; failHint: string },
  itemId: string,
): Promise<ExtensionResponse> {
  let lastError: string | null = null

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const result = (await chrome.tabs.sendMessage(
        senderTabId,
        composerMessage,
      )) as ExtensionResponse

      if (result && typeof result === 'object' && 'ok' in result) {
        if (!result.ok) return result
        const filled = 'filled' in result && Boolean(result.filled)
        const sent = 'sent' in result && Boolean(result.sent)
        const success = options.markReadyOn === 'sent' ? sent : filled
        if (success) {
          await markItemReady(itemId)
          return {
            ok: true,
            filled: filled || sent,
            imageAttached:
              'imageAttached' in result ? Boolean(result.imageAttached) : false,
            sent: options.markReadyOn === 'sent' ? true : undefined,
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
    error: lastError ?? options.failHint,
  }
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

  return sendComposerToTab(
    senderTabId,
    buildComposerPayload(item, 'fill'),
    {
      markReadyOn: 'filled',
      failHint: 'No se pudo rellenar el chat de WhatsApp. Vuelve a pulsar Publicar.',
    },
    itemId,
  )
}

async function handlePublishWhatsAppItem(
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

  return sendComposerToTab(
    senderTabId,
    buildComposerPayload(item, 'publish'),
    {
      markReadyOn: 'sent',
      failHint: 'No se pudo enviar el mensaje. Reanuda con Automático.',
    },
    itemId,
  )
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
    case 'PUBLISH_WHATSAPP_ITEM':
      return handlePublishWhatsAppItem(message.itemId, senderTabId)
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
