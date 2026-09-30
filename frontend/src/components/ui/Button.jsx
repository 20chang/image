import { Loader2 } from 'lucide-react'

const variants = {
  primary:
    'bg-[#1c1917] text-white hover:bg-[#2a2522] active:translate-y-px',
  secondary:
    'bg-white border border-[var(--border-quiet)] text-[#1c1917] hover:bg-[var(--bg-hover)] active:translate-y-px',
  ghost:
    'bg-transparent text-[var(--text-2)] hover:bg-[var(--bg-hover)] hover:text-[#1c1917]',
  danger:
    'bg-transparent border border-[#e8b4b0] text-[#b42318] hover:bg-[#fef3f2]',
  success: 'bg-[#276749] text-white hover:bg-[#1f5539]',
}

const sizes = {
  sm: 'h-8 px-3 text-[13px] rounded-[var(--radius-xs)]',
  md: 'h-9 px-4 text-[13.5px] rounded-[var(--radius-sm)]',
  lg: 'h-10 px-5 text-[14px] rounded-[var(--radius-sm)]',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  loading = false,
  disabled = false,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 font-medium tracking-[-0.01em] transition-[background-color,border-color,color,transform,opacity] duration-150 ease-[var(--ease-out)] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0 ${variants[variant] || variants.primary} ${sizes[size] || sizes.md} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
      )}
      {children}
    </button>
  )
}
