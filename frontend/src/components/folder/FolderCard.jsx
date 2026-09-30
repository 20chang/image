import { Folder, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'

/*
  Folder card is the navigation primitive — slightly more presence
  than product cards (filled icon tile) so hierarchy reads at a glance.
*/

export default function FolderCard({ folder, onOpen, onRename, onDelete }) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
      className="group relative bg-[var(--bg-surface)] rounded-[var(--radius-md)] border border-[var(--border-whisper)] p-4 hover:border-[var(--border-quiet)] hover:shadow-[var(--shadow-1)] transition-[border-color,box-shadow] duration-150 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]"
      aria-label={`打开文件夹 ${folder.name}`}
    >
      <div className="flex items-start justify-between mb-3.5">
        <div className="w-9 h-9 rounded-[var(--radius-sm)] bg-[var(--accent-soft)] text-[var(--accent-text)] flex items-center justify-center border border-[color-mix(in_srgb,var(--accent)_12%,transparent)]">
          <Folder className="w-[18px] h-[18px]" aria-hidden="true" />
        </div>
        <div className="relative">
          <button
            type="button"
            aria-label="文件夹操作"
            aria-expanded={menuOpen}
            className="p-1.5 rounded-[var(--radius-xs)] text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--bg-hover)] opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation()
              setMenuOpen((v) => !v)
            }}
          >
            <MoreHorizontal className="w-4 h-4" aria-hidden="true" />
          </button>
          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-8 z-20 w-32 bg-[var(--bg-raised)] border border-[var(--border-quiet)] rounded-[var(--radius-sm)] shadow-[var(--shadow-3)] py-1"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                role="menuitem"
                className="w-full flex items-center px-3 py-1.5 text-[13px] text-[var(--text-1)] hover:bg-[var(--bg-hover)]"
                onClick={() => {
                  setMenuOpen(false)
                  onRename()
                }}
              >
                <Pencil className="w-3.5 h-3.5 mr-2" aria-hidden="true" />
                重命名
              </button>
              <button
                type="button"
                role="menuitem"
                className="w-full flex items-center px-3 py-1.5 text-[13px] text-[var(--danger)] hover:bg-[var(--danger-soft)]"
                onClick={() => {
                  setMenuOpen(false)
                  onDelete()
                }}
              >
                <Trash2 className="w-3.5 h-3.5 mr-2" aria-hidden="true" />
                删除
              </button>
            </div>
          )}
        </div>
      </div>

      <h3 className="text-[13.5px] font-medium tracking-[-0.01em] truncate">
        {folder.name}
      </h3>
      <p className="mt-1 text-[11.5px] text-[var(--text-3)] tabular-nums">
        {folder.productCount || 0} 个商品，{folder.refCount || 0} 张参考图
      </p>
    </article>
  )
}
