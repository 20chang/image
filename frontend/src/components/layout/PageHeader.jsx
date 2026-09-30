export default function PageHeader({ title, desc, actions, breadcrumb }) {
  return (
    <>
      {breadcrumb}
      <div className="page-header">
        <div className="min-w-0">
          <h1 className="page-title">{title}</h1>
          {desc && <p className="page-desc">{desc}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </>
  )
}

export function StatStrip({ items }) {
  return (
    <div className="panel flex flex-wrap gap-0 mb-6 overflow-hidden">
      {items.map((item, i) => (
        <div
          key={item.label}
          className={`flex-1 min-w-[120px] px-4 py-3 ${
            i > 0 ? 'border-l border-[var(--border-whisper)]' : ''
          }`}
        >
          <div className="text-[11.5px] text-[var(--text-3)] mb-0.5">
            {item.label}
          </div>
          <div className="text-[16px] font-semibold tracking-[-0.02em] text-[var(--text-1)] tabular-nums">
            {item.value}
          </div>
        </div>
      ))}
    </div>
  )
}

export function Toolbar({ children }) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-6">{children}</div>
  )
}
