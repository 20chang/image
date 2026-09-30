import {
  ArrowDown,
  ArrowUp,
  Loader2,
  Maximize2,
  AlertCircle,
} from 'lucide-react'
import Badge from '../ui/Badge.jsx'
import { SOURCE_LABELS, PURPOSE_LABELS } from '../../data/constants.js'

export default function ReferenceCard({
  item,
  index,
  selected,
  onSelect,
  onPreview,
  onMove,
  canMoveUp,
  canMoveDown,
  onRetry,
  onRemove,
}) {
  const isUnclassified =
    item.status === 'success' && (!item.source || item.purposes?.length === 0)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(item.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(item.id)
        }
      }}
      className={`relative overflow-hidden rounded-[var(--radius-md)] bg-[var(--bg-raised)] cursor-pointer transition-[border-color,box-shadow] duration-150 border ${
        selected
          ? 'border-[var(--accent)] shadow-[var(--shadow-1)] ring-1 ring-[var(--accent)]'
          : 'border-[var(--border-whisper)] hover:border-[var(--border-quiet)]'
      } focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]`}
    >
      <div className="relative aspect-square bg-[var(--bg-subtle)] group">
        <img
          src={item.url}
          alt=""
          className={`h-full w-full object-contain ${
            item.status === 'uploading' ? 'opacity-50 blur-sm' : ''
          }`}
          draggable={false}
        />

        {item.status === 'uploading' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/50">
            <Loader2
              className="w-5 h-5 animate-spin text-[var(--accent)] mb-1.5"
              aria-hidden="true"
            />
            <span className="text-[11px] font-medium text-[var(--accent-text)]">
              上传中
            </span>
          </div>
        )}

        {item.status === 'failed' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/85 p-2">
            <AlertCircle
              className="w-5 h-5 text-[var(--danger)] mb-1.5"
              aria-hidden="true"
            />
            <span className="text-[11px] font-medium text-[var(--danger)] mb-2">
              上传失败
            </span>
            <div className="flex gap-1">
              <button
                type="button"
                className="px-2 py-1 text-[11px] rounded-[var(--radius-xs)] bg-[var(--text-1)] text-white"
                onClick={(e) => {
                  e.stopPropagation()
                  onRetry?.(item.id)
                }}
              >
                重试
              </button>
              <button
                type="button"
                className="px-2 py-1 text-[11px] rounded-[var(--radius-xs)] bg-white border border-[var(--border-quiet)] text-[var(--text-2)]"
                onClick={(e) => {
                  e.stopPropagation()
                  onRemove?.(item.id)
                }}
              >
                移除
              </button>
            </div>
          </div>
        )}

        {item.status === 'success' && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onPreview(item.url)
            }}
            className="absolute right-2 top-2 rounded-[var(--radius-xs)] bg-[rgba(28,25,22,0.55)] p-1.5 text-white opacity-0 transition-opacity hover:bg-[rgba(28,25,22,0.75)] group-hover:opacity-100"
            title="放大预览"
            aria-label="放大预览"
          >
            <Maximize2 className="w-3.5 h-3.5" aria-hidden="true" />
          </button>
        )}

        {isUnclassified && !selected && (
          <div className="absolute left-2 top-2 pointer-events-none">
            <Badge type="warning">待分类</Badge>
          </div>
        )}
      </div>

      {item.status === 'success' && (
        <div className="border-t border-[var(--border-whisper)] p-2.5">
          <div className="mb-1 flex items-start justify-between gap-1">
            <span className="text-[11px] font-semibold text-[var(--text-3)] tabular-nums">
              #{index + 1}
            </span>
            <span
              className={`rounded-[var(--radius-xs)] px-1.5 py-0.5 text-[10.5px] ${
                item.source
                  ? 'bg-[var(--bg-hover)] text-[var(--text-2)]'
                  : 'bg-[var(--danger-soft)] text-[var(--danger)]'
              }`}
            >
              {item.source ? SOURCE_LABELS[item.source] : '缺来源'}
            </span>
          </div>
          <p
            className="truncate text-[11px] text-[var(--text-3)]"
            title={(item.purposes || [])
              .map((p) => PURPOSE_LABELS[p])
              .filter(Boolean)
              .join('、')}
          >
            {item.purposes?.length > 0
              ? item.purposes
                  .map((p) => PURPOSE_LABELS[p])
                  .filter(Boolean)
                  .join('、')
              : '未选用途'}
          </p>
        </div>
      )}

      {selected && item.status === 'success' && (
        <div className="absolute left-2 top-2 z-10 flex gap-1">
          <button
            type="button"
            aria-label="上移"
            onClick={(e) => {
              e.stopPropagation()
              onMove(item.id, 'up')
            }}
            className="rounded-[var(--radius-xs)] bg-white/95 p-1 text-[var(--text-2)] shadow-[var(--shadow-1)] disabled:opacity-30 hover:bg-white"
            disabled={!canMoveUp}
          >
            <ArrowUp className="w-3 h-3" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="下移"
            onClick={(e) => {
              e.stopPropagation()
              onMove(item.id, 'down')
            }}
            className="rounded-[var(--radius-xs)] bg-white/95 p-1 text-[var(--text-2)] shadow-[var(--shadow-1)] disabled:opacity-30 hover:bg-white"
            disabled={!canMoveDown}
          >
            <ArrowDown className="w-3 h-3" aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  )
}
