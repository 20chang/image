import { X } from 'lucide-react'

export default function ImagePreview({ url, onClose }) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        className="absolute top-4 right-4 text-white hover:text-gray-300"
        onClick={onClose}
        aria-label="关闭预览"
      >
        <X className="w-8 h-8" />
      </button>
      <img
        src={url}
        className="max-w-full max-h-full object-contain"
        alt="预览"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  )
}
