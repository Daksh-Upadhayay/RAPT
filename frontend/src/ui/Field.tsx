import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { controlClasses } from './styles'

/** Label + control + hint/error, wired together for screen readers. */
export function Field({ id, label, optional, hint, error, children }: {
  id: string
  label: ReactNode
  optional?: boolean
  hint?: ReactNode
  error?: string | null
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-small font-semibold">
        {label}
        {optional && <span className="ml-1 font-normal text-ink-3">(optional)</span>}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-tiny font-medium text-danger-ink">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1.5 text-tiny text-ink-3">{hint}</p>
      )}
    </div>
  )
}

type Invalid = { invalid?: boolean }

export function Input({ invalid, className = '', ...rest }: InputHTMLAttributes<HTMLInputElement> & Invalid) {
  return <input aria-invalid={invalid || undefined} className={controlClasses(invalid, `h-10 ${className}`)} {...rest} />
}

export function Select({ invalid, className = '', ...rest }: SelectHTMLAttributes<HTMLSelectElement> & Invalid) {
  return <select aria-invalid={invalid || undefined} className={controlClasses(invalid, `h-10 ${className}`)} {...rest} />
}

export function Textarea({ invalid, className = '', ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & Invalid) {
  return <textarea aria-invalid={invalid || undefined} className={controlClasses(invalid, `resize-y py-2.5 ${className}`)} {...rest} />
}
