import Button from './Button.jsx'

export default function ConfirmDialog({
  title,
  message,
  confirmText = '确定',
  cancelText = '取消',
  discardText = '放弃修改',
  onConfirm,
  onDiscard,
  onCancel,
  showDiscard = true,
}) {
  return (
    <div
      className="fixed inset-0 bg-black/25 backdrop-blur-[1px] z-[60] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-white rounded-[var(--radius-lg)] shadow-[var(--shadow-3)] w-full max-w-sm p-5 border border-[var(--border-whisper)]">
        <h3 className="text-[15px] font-semibold text-[var(--text-1)] mb-1.5">
          {title}
        </h3>
        <p className="text-[13px] text-[var(--text-2)] mb-5 leading-relaxed">
          {message}
        </p>
        <div className="flex flex-col gap-2">
          {onConfirm && (
            <Button onClick={onConfirm} className="w-full" size="sm">
              {confirmText}
            </Button>
          )}
          {showDiscard && onDiscard && (
            <Button
              variant="danger"
              onClick={onDiscard}
              className="w-full"
              size="sm"
            >
              {discardText}
            </Button>
          )}
          <Button variant="ghost" onClick={onCancel} className="w-full" size="sm">
            {cancelText}
          </Button>
        </div>
      </div>
    </div>
  )
}
