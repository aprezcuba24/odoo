import { PUBLISH_QUEUE_STORAGE_KEY } from './constants'

export type PublishQueueProduct = {
  id: string
  name: string
  price: string
  imageBase64: string | null
  imageMime: string | null
}

export type PublishQueue = {
  products: PublishQueueProduct[]
  startedAt: number
  /** Product ids marked as published ("Listo"). Survives sidebar close/reopen. */
  readyIds: string[]
}

function isProduct(value: unknown): value is PublishQueueProduct {
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

function parseReadyIds(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((id): id is string => typeof id === 'string')
}

export function parsePublishQueue(value: unknown): PublishQueue | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  if (!Array.isArray(raw.products) || typeof raw.startedAt !== 'number') return null
  if (!raw.products.every(isProduct)) return null
  return {
    products: raw.products,
    startedAt: raw.startedAt,
    readyIds: parseReadyIds(raw.readyIds),
  }
}

export async function readPublishQueue(): Promise<PublishQueue | null> {
  const stored = await chrome.storage.local.get(PUBLISH_QUEUE_STORAGE_KEY)
  return parsePublishQueue(stored[PUBLISH_QUEUE_STORAGE_KEY])
}

export async function writePublishQueue(queue: PublishQueue): Promise<void> {
  await chrome.storage.local.set({ [PUBLISH_QUEUE_STORAGE_KEY]: queue })
}

export async function markProductReady(productId: string): Promise<void> {
  const queue = await readPublishQueue()
  if (!queue) return
  if (queue.readyIds.includes(productId)) return
  await writePublishQueue({
    ...queue,
    readyIds: [...queue.readyIds, productId],
  })
}

export async function clearReadyIds(): Promise<void> {
  const queue = await readPublishQueue()
  if (!queue) return
  await writePublishQueue({ ...queue, readyIds: [] })
}

export async function clearPublishQueue(): Promise<void> {
  await chrome.storage.local.remove(PUBLISH_QUEUE_STORAGE_KEY)
}
