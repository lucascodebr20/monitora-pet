import { useEffect, useId, useRef, useState } from 'react'
import Icon from './Icon'

type Props = {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}

export default function FilterDropdown({ label, value, options, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const id = useId()
  const selected = options.find(option => option.value === value)

  useEffect(() => {
    if (!open) return
    root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus()
    const closeOutside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnBlur = (event: FocusEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('focusin', closeOnBlur)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('focusin', closeOnBlur)
    }
  }, [open])

  return (
    <div className="history-select-filter filter-dropdown" ref={root}>
      <span id={`${id}-label`}>{label}</span>
      <button
        ref={trigger}
        type="button"
        className="filter-dropdown-trigger"
        aria-labelledby={`${id}-label ${id}-value`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? `${id}-menu` : undefined}
        onClick={() => setOpen(current => !current)}
        onKeyDown={event => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            setOpen(true)
          }
        }}
      >
        <span id={`${id}-value`}>{selected?.label}</span>
        <svg className="filter-dropdown-chevron" viewBox="0 0 24 24" aria-hidden="true">
          <path d="m7 10 5 5 5-5" />
        </svg>
      </button>
      {open && (
        <div
          id={`${id}-menu`}
          className="filter-dropdown-menu"
          role="menu"
          aria-labelledby={`${id}-label`}
          onKeyDown={event => {
            if (event.key === 'Escape') {
              event.preventDefault()
              setOpen(false)
              trigger.current?.focus()
            }
            const buttons = Array.from(
              event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'),
            )
            const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
            let next: number | undefined
            if (event.key === 'ArrowDown') next = (index + 1) % buttons.length
            if (event.key === 'ArrowUp') next = (index - 1 + buttons.length) % buttons.length
            if (event.key === 'Home') next = 0
            if (event.key === 'End') next = buttons.length - 1
            if (next !== undefined) {
              event.preventDefault()
              buttons[next]?.focus()
            }
          }}
        >
          {options.map(option => (
            <button
              key={option.value}
              type="button"
              role="menuitemradio"
              aria-checked={option.value === value}
              tabIndex={-1}
              onClick={() => {
                onChange(option.value)
                setOpen(false)
                trigger.current?.focus()
              }}
            >
              <span>{option.label}</span>
              {option.value === value && <Icon name="accept" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
