import { InputHTMLAttributes, ReactNode } from 'react'

type FloatingInputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  helperText?: ReactNode
  containerClassName?: string
  rightElement?: ReactNode
}

export default function FloatingInput({
  label,
  helperText,
  containerClassName = '',
  rightElement,
  className = '',
  ...props
}: FloatingInputProps) {
  return (
    <div className={containerClassName}>
      <div className="relative">
        <input
          {...props}
          placeholder=" "
          className={`peer w-full rounded-2xl border border-gray-200 bg-white px-4 py-4 text-gray-900 placeholder-transparent transition-all focus:border-primary-500 focus:ring-0 ${rightElement ? 'pr-12' : ''} ${className}`}
        />
        <label
          htmlFor={props.id}
          className="pointer-events-none absolute left-4 top-2 text-xs text-gray-500 transition-colors duration-200 peer-focus:text-primary-600"
        >
          {label}
        </label>
        {rightElement && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            {rightElement}
          </div>
        )}
      </div>
      {helperText && <p className="mt-2 text-xs text-gray-500">{helperText}</p>}
    </div>
  )
}

