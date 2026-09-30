import { AlertCircle, Image as ImageIcon, Bookmark } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-transparent flex flex-col text-[var(--text-1)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:bg-white focus:px-3 focus:py-2 focus:rounded-[var(--radius-sm)] focus:border focus:border-[var(--border-quiet)]"
      >
        跳到主内容
      </a>

      <div className="bg-[var(--warning-soft)] text-[var(--warning)] px-4 py-2 text-[12px] flex justify-center items-center gap-1.5 border-b border-[var(--border-whisper)]">
        <AlertCircle className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
        <span>原型环境 · 数据已落库，当前为单人示例范围</span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-[52px] lg:w-[212px] bg-[var(--bg-surface)] border-r border-[var(--border-whisper)] flex flex-col shrink-0">
          <div className="h-14 px-3 flex items-center gap-2.5 border-b border-[var(--border-whisper)]">
            <div className="w-7 h-7 rounded-[var(--radius-xs)] bg-[var(--text-1)] text-[var(--text-inverse)] flex items-center justify-center text-[10px] font-semibold shrink-0 tracking-wide">
              IMG
            </div>
            <div className="hidden lg:block min-w-0">
              <p className="text-[13px] font-semibold tracking-[-0.02em] truncate">
                图片工作台
              </p>
            </div>
          </div>

          <nav className="flex-1 p-2 space-y-0.5" aria-label="主导航">
            <NavLink
              to="/folders"
              className={({ isActive }) =>
                `w-full flex items-center h-9 px-2.5 rounded-[var(--radius-xs)] text-[13px] transition-colors ${
                  isActive
                    ? 'bg-[var(--bg-hover)] text-[var(--text-1)] font-medium'
                    : 'text-[var(--text-2)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-1)]'
                }`
              }
            >
              <ImageIcon className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span className="ml-2.5 hidden lg:block">商品库</span>
            </NavLink>

            <button
              type="button"
              disabled
              className="w-full flex items-center h-9 px-2.5 rounded-[var(--radius-xs)] text-[13px] text-[var(--text-3)] cursor-not-allowed"
            >
              <Bookmark className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span className="ml-2.5 hidden lg:block">收藏</span>
              <span className="ml-auto hidden lg:block text-[11px]">
                未开放
              </span>
            </button>
          </nav>

          <div className="px-3 py-3 border-t border-[var(--border-whisper)]">
            <p className="hidden lg:block text-[11px] text-[var(--text-3)] leading-relaxed">
              文件夹归类商品，商品下管理参考图
            </p>
          </div>
        </aside>

        <main id="main" className="flex-1 overflow-auto relative">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
