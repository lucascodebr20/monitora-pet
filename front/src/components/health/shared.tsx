import { useCallback, useEffect, useState } from 'react'
import type { HealthAttachment } from '../../api'
import { errorMessage } from '../../lib/errors'

export function todayIso(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

export function nowLocalInput(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export function shiftDays(day: string, days: number): string {
  const [year, month, date] = day.split('-').map(Number)
  const shifted = new Date(Date.UTC(year, month - 1, date + days))
  return shifted.toISOString().slice(0, 10)
}

export function formatDay(day: string | null | undefined, fallback = 'Data não informada'): string {
  if (!day) return fallback
  const [year, month, date] = day.split('-').map(Number)
  return new Date(year, month - 1, date).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatInstant(instant: string): string {
  return new Date(instant).toLocaleString('pt-BR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatWeight(kg: number): string {
  return `${kg.toLocaleString('pt-BR', { maximumFractionDigits: 3 })} kg`
}

export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`
}

export function dueLabel(days: number): string {
  if (days < -1) return `atrasada há ${-days} dias`
  if (days === -1) return 'atrasada desde ontem'
  if (days === 0) return 'vence hoje'
  if (days === 1) return 'vence amanhã'
  return `vence em ${days} dias`
}

export function useLoader<T>(load: () => Promise<T>, initial: T, failure: string) {
  const [data, setData] = useState<T>(initial)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion(current => current + 1), [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    load()
      .then(result => {
        if (active) setData(result)
      })
      .catch(reason => {
        if (active) setError(errorMessage(reason, failure))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [version, load, failure])

  return { data, setData, loading, error, reload }
}

type AttachmentProps = {
  attachments: HealthAttachment[]
  onOpenImage: (attachment: HealthAttachment) => void
  onDelete?: (attachment: HealthAttachment) => void
  deleting?: string | null
}

export function AttachmentList({ attachments, onOpenImage, onDelete, deleting }: AttachmentProps) {
  if (!attachments.length) return null
  return (
    <ul className="health-attachments">
      {attachments.map((attachment, index) => (
        <li key={attachment.id}>
          {attachment.thumbnail_url ? (
            <button type="button" className="image-button" onClick={() => onOpenImage(attachment)}>
              <img src={attachment.thumbnail_url} alt={`Página ${index + 1}: ${attachment.original_name}`} />
            </button>
          ) : (
            <a className="health-file" href={attachment.url} target="_blank" rel="noreferrer">
              <span>PDF</span>
            </a>
          )}
          <div>
            <a href={attachment.url} target="_blank" rel="noreferrer" title="Abrir o original">
              {attachment.original_name}
            </a>
            <small>{formatSize(attachment.size_bytes)}</small>
          </div>
          {onDelete && (
            <button
              type="button"
              className="tertiary danger"
              disabled={deleting === attachment.id}
              onClick={() => onDelete(attachment)}
            >
              {deleting === attachment.id ? 'Removendo…' : 'Remover'}
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

export function SectionState({ loading, error, empty, emptyTitle, emptyText }: {
  loading: boolean
  error: string
  empty: boolean
  emptyTitle: string
  emptyText: string
}) {
  if (error) return <p className="form-error">{error}</p>
  if (loading) return <p className="loading">Carregando…</p>
  if (empty)
    return (
      <div className="empty">
        <h3>{emptyTitle}</h3>
        <p>{emptyText}</p>
      </div>
    )
  return null
}
