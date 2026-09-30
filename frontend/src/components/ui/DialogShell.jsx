import { X } from 'lucide-react'

export default function DialogShell({
  title,
  subtitle,
  onClose,
  children,
  footer,
  width = 'max-w-md',
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[rgba(28,25,22,0.28)] backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={`w-full ${width} bg-[var(--bg-raised)] rounded-[var(--radius-lg)] border border-[var(--border-whisper)] shadow-[var(--shadow-3)] flex flex-col max-h-[min(88vh,720px)]`}
      >
        <header className="flex items-start justify-between gap-3 px-5 pt-5 pb-3">
          <div>
            <h2 className="m-0 text-[16px] font-semibold tracking-[-0.02em] text-[var(--text-1)]">
              {title}
            </h2>
            {subtitle && (
              <p className="mt-1.5 mb-0 text-[12.5px] text-[var(--text-2)] leading-relaxed">
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="shrink-0 p-1.5 -mt-1 rounded-[var(--radius-xs)] text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--bg-hover)] transition-colors"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </header>

        <div className="px-5 pb-5 overflow-y-auto flex-1">{children}</div>

        {footer && (
          <footer className="flex justify-end gap-2 px-5 py-4 border-t border-[var(--border-whisper)] bg-[var(--bg-surface)] rounded-b-[var(--radius-lg)]">
            {footer}
          </footer>
        )}
      </div>
    </div>
  )
}
