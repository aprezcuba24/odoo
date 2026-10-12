import type { ExtensionMessage, ExtensionResponse } from '../messaging'
import {
  clearPublishQueue,
  clearReadyIds,
  markProductReady,
  parsePublishQueue,
  readPublishQueue,
  writePublishQueue,
} from '../publish-queue'
import { buildProductPostText } from '../post-text'

function isProductRow(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    typeof item.id === 'string' &&
    typeof item.name === 'string' &&
    typeof item.price === 'string' &&
    (item.imageBase64 === null || typeof item.imageBase64 === 'string') &&
    (item.imageMime === null || typeof item.imageMime === 'string')
  )
}

async function handleStartPublish(message: {
  products: unknown
}): Promise<ExtensionResponse> {
  if (!Array.isArray(message.products) || !message.products.every(isProductRow)) {
    return { ok: false, error: 'Productos inválidos' }
  }
  if (message.products.length === 0) {
    return { ok: false, error: 'Selecciona al menos un producto' }
  }

  const queue = parsePublishQueue({
    products: message.products,
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

async function handleFillWhatsAppProduct(
  productId: string,
  senderTabId: number | undefined,
): Promise<ExtensionResponse> {
  if (senderTabId == null) {
    return { ok: false, error: 'No hay pestaña activa' }
  }

  const queue = await readPublishQueue()
  if (!queue || queue.products.length === 0) {
    return { ok: false, error: 'No hay cola de publicación' }
  }
  const product = queue.products.find((row) => row.id === productId)
  if (!product) {
    return { ok: false, error: 'Producto no encontrado en la cola' }
  }

  const text = buildProductPostText(product.name, product.price)
  let lastError: string | null = null

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const result = (await chrome.tabs.sendMessage(senderTabId, {
        type: 'FILL_WHATSAPP_COMPOSER',
        text,
        imageBase64: product.imageBase64,
        imageMime: product.imageMime,
      })) as ExtensionResponse

      if (result && typeof result === 'object' && 'ok' in result) {
        if (!result.ok) return result
        if ('filled' in result && result.filled) {
          await markProductReady(productId)
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
    case 'FILL_WHATSAPP_PRODUCT':
      return handleFillWhatsAppProduct(message.productId, senderTabId)
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
