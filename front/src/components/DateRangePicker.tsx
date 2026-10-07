import { useEffect, useMemo, useRef, useState } from 'react'
import Icon from './Icon'

type Props = {
  startDate: string
  endDate: string
  onChange: (startDate: string, endDate: string) => void
}

const weekDays = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']

function isoDate(value: Date): string {
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`
}

function parseDate(value: string): Date {
  return new Date(`${value}T12:00:00`)
}

function monthStart(value?: string): Date {
  const base = value ? parseDate(value) : new Date()
  return new Date(base.getFullYear(), base.getMonth(), 1, 12)
}

function displayDate(value: string): string {
  return parseDate(value).toLocaleDateString('pt-BR')
}

export default function DateRangePicker({ startDate, endDate, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [month, setMonth] = useState(() => monthStart(startDate))
  const [draftStart, setDraftStart] = useState(startDate)
  const [draftEnd, setDraftEnd] = useState(endDate)
  const root = useRef<HTMLDivElement>(null)
  const today = isoDate(new Date())

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', closeOutside)
    return () => window.removeEventListener('mousedown', closeOutside)
  }, [open])

  const days = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1, 12)
    first.setDate(first.getDate() - first.getDay())
    return Array.from({ length: 42 }, (_, index) => {
      const day = new Date(first)
      day.setDate(first.getDate() + index)
      return day
    })
  }, [month])

  const label = startDate && endDate
    ? `${displayDate(startDate)} – ${displayDate(endDate)}`
    : 'Selecionar período'

  function toggle() {
    if (!open) {
      setDraftStart(startDate)
      setDraftEnd(endDate)
      setMonth(monthStart(startDate || endDate))
    }
    setOpen(value => !value)
  }

  function choose(value: string) {
    if (!draftStart || draftEnd) {
      setDraftStart(value)
      setDraftEnd('')
      return
    }
    const nextStart = value < draftStart ? value : draftStart
    const nextEnd = value < draftStart ? draftStart : value
    setDraftStart(nextStart)
    setDraftEnd(nextEnd)
    onChange(nextStart, nextEnd)
    setOpen(false)
  }

  const currentMonth = month.getFullYear() === new Date().getFullYear() && month.getMonth() === new Date().getMonth()

  return (
    <div className="date-range-picker" ref={root}>
      <button type="button" className={`date-range-trigger${startDate ? ' selected' : ''}`} onClick={toggle} aria-expanded={open}>
        <Icon name="calendar" />
        <span>{label}</span>
      </button>
      {open && (
        <div className="date-range-popover">
          <div className="date-range-calendar-head">
            <button
              type="button"
              aria-label="Mês anterior"
              onClick={() => setMonth(value => new Date(value.getFullYear(), value.getMonth() - 1, 1, 12))}
            >
              ‹
            </button>
            <strong>{month.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })}</strong>
            <button
              type="button"
              aria-label="Próximo mês"
              disabled={currentMonth}
              onClick={() => setMonth(value => new Date(value.getFullYear(), value.getMonth() + 1, 1, 12))}
            >
              ›
            </button>
          </div>
          <p className="date-range-hint">
            {draftStart && !draftEnd ? 'Agora selecione a data final' : 'Selecione a data inicial e a final'}
          </p>
          <div className="date-range-weekdays" aria-hidden="true">
            {weekDays.map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}
          </div>
          <div className="date-range-days">
            {days.map(day => {
              const value = isoDate(day)
              const outside = day.getMonth() !== month.getMonth()
              const inRange = Boolean(draftStart && draftEnd && value > draftStart && value < draftEnd)
              const edge = value === draftStart || value === draftEnd
              return (
                <button
                  type="button"
                  key={value}
                  className={`${outside ? 'outside ' : ''}${inRange ? 'in-range ' : ''}${edge ? 'range-edge' : ''}`.trim()}
                  disabled={value > today}
                  aria-pressed={edge || inRange}
                  onClick={() => choose(value)}
                >
                  {day.getDate()}
                </button>
              )
            })}
          </div>
          {(startDate || draftStart) && (
            <button
              type="button"
              className="date-range-clear"
              onClick={() => {
                setDraftStart('')
                setDraftEnd('')
                onChange('', '')
                setOpen(false)
              }}
            >
              Limpar período
            </button>
          )}
        </div>
      )}
    </div>
  )
}
