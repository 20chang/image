import Button from './Button.jsx'

/*
  Empty states are invitations (frontend-design):
  say what to do next, not how lonely the screen is.
*/

export default function EmptyState({ icon, title, desc, action }) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 py-16 text-center">
      <div
        className="w-14 h-14 rounded-[var(--radius-md)] bg-[var(--bg-subtle)] border border-[var(--border-whisper)] flex items-center justify-center mb-5 text-[var(--text-2)]"
        aria-hidden="true"
      >
        {icon}
      </div>
      <h3 className="text-[var(--text-lg)] font-semibold tracking-[-0.02em] text-[var(--text-1)] mb-2">
        {title}
      </h3>
      <p className="text-[var(--text-sm)] text-[var(--text-2)] max-w-[28rem] leading-[1.65] mb-7">
        {desc}
      </p>
      {action && (
        <Button variant="secondary" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  )
}
