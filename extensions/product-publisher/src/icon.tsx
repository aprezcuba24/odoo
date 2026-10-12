type Props = {
  size?: number
  alt?: string
  className?: string
}

/** Simple generic mark (no Facebook / WhatsApp branding). */
export default function AppIcon({ size = 32, alt = '', className }: Props) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-label={alt || undefined}
      role={alt ? 'img' : 'presentation'}
    >
      <rect width="32" height="32" rx="8" fill="currentColor" opacity="0.15" />
      <path
        d="M8 12h16v2H8v-2Zm0 5h12v2H8v-2Zm0 5h14v2H8v-2Z"
        fill="currentColor"
      />
    </svg>
  )
}
