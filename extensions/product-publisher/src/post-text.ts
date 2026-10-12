/**
 * Plain text for WhatsApp: bold name (with UoM) + price (already formatted, e.g. CUP).
 * WhatsApp uses *text* for bold.
 */
export function buildProductPostText(name: string, price: string): string {
  const lines: string[] = []
  const trimmedName = name.trim()
  if (trimmedName) {
    lines.push(`*${trimmedName}*`)
  }
  const trimmedPrice = price.trim()
  if (trimmedPrice) lines.push(trimmedPrice)
  return lines.join('\n')
}
