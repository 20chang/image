export default function Input({
  label,
  error,
  hint,
  className = '',
  id,
  ...props
}) {
  const inputId = id || props.name || label
  return (
    <div className={`mb-4 ${className}`}>
      {label && (
        <label className="field-label" htmlFor={inputId}>
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`field-input ${error ? 'aria-invalid' : ''}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${inputId}-error` : undefined}
        {...props}
      />
      {hint && !error && <p className="field-hint">{hint}</p>}
      {error && (
        <p className="field-error" id={`${inputId}-error`}>
          {error}
        </p>
      )}
    </div>
  )
}
