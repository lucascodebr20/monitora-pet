type Props = { size?: number; title?: string }

/**
 * Marca do Monitora Pet: a pata do gato enquadrada pelos cantos de foco de uma
 * câmera. A moldura carrega o "monitora" e a pata carrega o "pet".
 */
export default function BrandMark({ size = 38, title }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <defs>
        <linearGradient id="brand-mark-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7d9c63" />
          <stop offset="1" stopColor="#47603b" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9.5" fill="url(#brand-mark-tile)" />
      <g fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.55">
        <path d="M10.5 6.5H6.5V10.5" />
        <path d="M21.5 6.5H25.5V10.5" />
        <path d="M10.5 25.5H6.5V21.5" />
        <path d="M21.5 25.5H25.5V21.5" />
      </g>
      <g fill="#fff" transform="translate(6.63 6.51) scale(0.781)">
        <ellipse cx="4.3" cy="10.6" rx="1.9" ry="2.5" />
        <ellipse cx="9.3" cy="7.3" rx="2.1" ry="2.9" />
        <ellipse cx="14.7" cy="7.3" rx="2.1" ry="2.9" />
        <ellipse cx="19.7" cy="10.6" rx="1.9" ry="2.5" />
        <path d="M12 12.4c-3.1 0-5.6 2.1-5.6 4.6 0 2.1 1.8 3.4 3.7 2.9 1.2-.33 2.6-.33 3.8 0 1.9.5 3.7-.8 3.7-2.9 0-2.5-2.5-4.6-5.6-4.6Z" />
      </g>
    </svg>
  )
}
