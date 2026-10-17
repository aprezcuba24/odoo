import { PUBLISH_QUEUE_STORAGE_KEY } from './constants'

export type ProductItem = {
  type: 'product'
  id: string
  name: string
  price: string
  imageBase64: string | null
  imageMime: string | null
}

export type BlockItem =
  | { type: 'block'; id: string; kind: 'text'; text: string }
  | { type: 'block'; id: string; kind: 'sticker'; imageBase64: string; imageMime: string }

export type QueueItem = ProductItem | BlockItem

export type PublishQueue = {
  items: QueueItem[]
  startedAt: number
  /** Item ids marked as published ("Listo"). Survives sidebar close/reopen. */
  readyIds: string[]
}

function isProductItem(value: unknown): value is ProductItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    item.type === 'product' &&
    typeof item.id === 'string' &&
    typeof item.name === 'string' &&
    typeof item.price === 'string' &&
    (item.imageBase64 === null || typeof item.imageBase64 === 'string') &&
    (item.imageMime === null || typeof item.imageMime === 'string')
  )
}

function isBlockItem(value: unknown): value is BlockItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  if (item.type !== 'block' || typeof item.id !== 'string') return false
  if (item.kind === 'text') return typeof item.text === 'string'
  if (item.kind === 'sticker')
    return typeof item.imageBase64 === 'string' && typeof item.imageMime === 'string'
  return false
}

export function isQueueItem(value: unknown): value is QueueItem {
  return isProductItem(value) || isBlockItem(value)
}

function parseReadyIds(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((id): id is string => typeof id === 'string')
}

export function parsePublishQueue(value: unknown): PublishQueue | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  if (!Array.isArray(raw.items) || typeof raw.startedAt !== 'number') return null
  if (!raw.items.every(isQueueItem)) return null
  return {
    items: raw.items,
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

export async function markItemReady(itemId: string): Promise<void> {
  const queue = await readPublishQueue()
  if (!queue) return
  if (queue.readyIds.includes(itemId)) return
  await writePublishQueue({
    ...queue,
    readyIds: [...queue.readyIds, itemId],
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
