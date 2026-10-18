/** Delays between automatic WhatsApp sends to reduce ban / rate-limit risk. */

export const PRE_SEND_MS = { min: 400, max: 700 } as const
export const AFTER_TEXT_MS = { min: 4000, max: 6000 } as const
export const AFTER_IMAGE_MS = { min: 8000, max: 12000 } as const
/** Extra pause every N successful sends. */
export const BATCH_EVERY = 8
export const BATCH_EXTRA_MS = { min: 15000, max: 25000 } as const
/** How long to wait for the composer to clear after clicking Send. */
export const SEND_CONFIRM_TIMEOUT_MS = 25000

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function randomBetween(min: number, max: number): number {
  return Math.floor(min + Math.random() * (max - min + 1))
}

export function paceMs(range: { min: number; max: number }): number {
  return randomBetween(range.min, range.max)
}

/**
 * Interruptible sleep: returns false if `shouldStop` becomes true before the delay ends.
 */
export async function interruptibleSleep(
  ms: number,
  shouldStop: () => boolean,
  tickMs = 200,
): Promise<boolean> {
  const deadline = Date.now() + ms
  while (Date.now() < deadline) {
    if (shouldStop()) return false
    await sleep(Math.min(tickMs, deadline - Date.now()))
  }
  return !shouldStop()
}
