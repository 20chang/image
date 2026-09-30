import { Image as ImageIcon } from 'lucide-react'
import Badge from '../ui/Badge.jsx'

/*
  Product card — content-first, quiet chrome.
  Shows a short facts line so list pages don't feel empty.
*/

export default function ProductCard({ product, onClick }) {
  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      className="group flex h-full flex-col overflow-hidden rounded-[var(--radius-md)] border border-[var(--border-whisper)] bg-[var(--bg-raised)] cursor-pointer transition-shadow duration-200 hover:shadow-[var(--shadow-2)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]"
      aria-label={`打开商品 ${product.name}`}
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-[var(--bg-subtle)]">
        {product.coverUrl ? (
          <img
            src={product.coverUrl}
            alt=""
            className="h-full w-full object-cover"
            draggable={false}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[var(--text-3)]">
            <ImageIcon className="w-7 h-7" aria-hidden="true" />
            <span className="sr-only">暂无封面</span>
          </div>
        )}
        {product.market && (
          <div className="absolute left-2.5 top-2.5">
            <Badge>{product.market}</Badge>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col p-3.5">
        <h3
          className="text-[13.5px] font-medium leading-snug tracking-[-0.01em] line-clamp-2 text-[var(--text-1)]"
          title={product.name}
        >
          {product.name}
        </h3>

        {product.facts ? (
          <p className="mt-1.5 text-[11.5px] leading-[1.5] text-[var(--text-3)] line-clamp-2">
            {product.facts}
          </p>
        ) : (
          <p className="mt-1.5 text-[11.5px] text-[var(--text-3)]">
            未填写已知事实
          </p>
        )}

        <div className="mt-auto flex items-baseline justify-between gap-2 border-t border-[var(--border-whisper)] pt-2.5 text-[11.5px] text-[var(--text-3)]">
          <span className="tabular-nums">
            {product.refCount || 0} 张参考图
          </span>
          <time className="tabular-nums" dateTime={product.updatedAt}>
            {product.updatedAt}
          </time>
        </div>
      </div>
    </article>
  )
}
