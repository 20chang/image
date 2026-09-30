import { ChevronRight, Home } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Breadcrumbs({ items }) {
  return (
    <nav aria-label="面包屑" className="mb-3">
      <ol className="flex flex-wrap items-center gap-x-0.5 gap-y-1 m-0 p-0 list-none text-[12.5px] text-[var(--text-3)]">
        <li className="flex items-center min-w-0">
          <Link
            to="/folders"
            className="inline-flex items-center gap-1 px-1 py-0.5 rounded text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--bg-hover)] transition-colors no-underline hover:underline"
          >
            <Home className="w-3.5 h-3.5" aria-hidden="true" />
            商品库
          </Link>
        </li>
        {items.map((item, i) => {
          const last = i === items.length - 1
          return (
            <li key={item.key || item.label} className="flex items-center min-w-0">
              <ChevronRight
                className="w-3.5 h-3.5 mx-0.5 text-[var(--text-3)] opacity-60"
                aria-hidden="true"
              />
              {item.to && !last ? (
                <Link
                  to={item.to}
                  className="px-1 py-0.5 rounded text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--bg-hover)] transition-colors no-underline hover:underline truncate max-w-[12rem] sm:max-w-[20rem]"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  className="px-1 py-0.5 font-medium text-[var(--text-1)] truncate max-w-[12rem] sm:max-w-[24rem]"
                  aria-current="page"
                >
                  {item.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
