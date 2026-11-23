/**
 * Plain text for WhatsApp product posts: bold name (with UoM), price, optional store link.
 * Caption is only those three lines (plus the product photo when attached) — nothing else.
 * The store URL must stay a clean https://… string so Android App Links open the APK.
 * WhatsApp uses *text* for bold.
 */
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
  if (trimmedUrl) lines.push(`🔗 ${trimmedUrl}`)
  return lines.join('\n')
}
