const types = {
  default: 'bg-[var(--bg-hover)] text-[var(--text-2)]',
  warning: 'bg-[var(--warning-soft)] text-[var(--warning)]',
  success: 'bg-[var(--success-soft)] text-[var(--success)]',
  error: 'bg-[var(--danger-soft)] text-[var(--danger)]',
  info: 'bg-[var(--accent-soft)] text-[var(--accent-text)]',
}

export default function Badge({ children, type = 'default', className = '' }) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium tracking-[0.01em] ${types[type] || types.default} ${className}`}
    >
      {children}
    </span>
  )
}
