/**
 * Plain text for WhatsApp product posts: bold name (with UoM), price, optional store link.
 * Caption is only those three lines (plus the product photo when attached) — nothing else.
 * WhatsApp uses *text* for bold.
 */

/** Invisible break after `://` so WhatsApp does not fetch a link-preview card. */
export function withoutLinkPreview(url: string): string {
  const trimmed = url.trim()
  if (!trimmed) return trimmed
  // Zero-width space: URL stays visually identical and copyable; WA skips OG scrape.
  return trimmed.replace(/:\/\//, '://\u200B')
}

export function buildProductPostText(
  name: string,
  price: string,
  storeUrl?: string | null,
): string {
  const lines: string[] = []
  const trimmedName = name.trim()
  if (trimmedName) {
    lines.push(`👉 *${trimmedName}*`)
  }
  const trimmedPrice = price.trim()
  if (trimmedPrice) lines.push(`💰 ${trimmedPrice}`)
  const trimmedUrl = (storeUrl || '').trim()
  if (trimmedUrl) lines.push(`🔗 ${withoutLinkPreview(trimmedUrl)}`)
  return lines.join('\n')
}
