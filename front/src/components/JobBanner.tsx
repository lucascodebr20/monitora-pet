import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { JobState } from '../api'
import { useToast } from './useToast'

type Props = { refresh: () => Promise<void> }

const ACTIVE_POLL_MS = 2000
const IDLE_POLL_MS = 15000

function stageLabel(state: JobState): string {
  const camera = state.camera_name ? ` · ${state.camera_name}` : ''
  if (state.stage === 'downloading') return `Baixando gravações da câmera${camera}`
  if (state.stage === 'scanning') return `Procurando gravações novas${camera}`
  if (state.stage === 'analyzing') return `Analisando gravações${camera}`
  return 'Preparando…'
}

function resultMessage(state: JobState): string | null {
  const result = state.last_result
  if (!result) return null
  if (result.kind === 'sync') {
    return result.downloaded
      ? `${result.downloaded} trecho(s) baixado(s) da câmera.`
      : 'Nenhuma gravação nova na câmera.'
  }
  if (result.kind === 'import') {
    if (!result.processed && !result.failed) return null
    return `Análise concluída: ${result.processed} gravação(ões) analisada(s)${
      result.failed ? `, ${result.failed} com falha` : ''
    }.`
  }
  return null
}

export default function JobBanner({ refresh }: Props) {
  const showToast = useToast()
  const [state, setState] = useState<JobState | null>(null)
  const [showOutcome, setShowOutcome] = useState(false)
  const previous = useRef<JobState | null>(null)
  const requested = useRef(false)

  useEffect(() => {
    let active = true
    let timer = 0
    const tick = async () => {
      try {
        const next = await api.getJobState()
        if (!active) return
        const before = previous.current
        previous.current = next
        setState(next)
        if (next.status === 'running') setShowOutcome(false)
        const completed =
          next.status === 'idle' &&
          Boolean(next.finished_at) &&
          (before?.status === 'running' || requested.current) &&
          next.finished_at !== before?.finished_at
        if (completed) {
          const message = resultMessage(next)
          setShowOutcome(Boolean(next.error || message))
          requested.current = false
          if (next.error) showToast(next.error, 'error')
          else if (message) showToast(message)
          void refresh()
        }
        timer = window.setTimeout(() => void tick(), next.status === 'running' ? ACTIVE_POLL_MS : IDLE_POLL_MS)
      } catch {
        if (active) timer = window.setTimeout(() => void tick(), IDLE_POLL_MS)
      }
    }
    void tick()
    const wake = () => {
      requested.current = true
      window.clearTimeout(timer)
      void tick()
    }
    window.addEventListener('monitorapet:job-started', wake)
    return () => {
      active = false
      window.clearTimeout(timer)
      window.removeEventListener('monitorapet:job-started', wake)
    }
  }, [refresh, showToast])

  if (!state) return null
  const running = state.status === 'running'
  const message = resultMessage(state)
  if (!running && (!showOutcome || (!state.error && !message))) return null
  const percent =
    state.total_seconds > 0 ? Math.min(100, Math.round((state.progress_seconds / state.total_seconds) * 100)) : null

  return (
    <div
      className={`job-banner${running ? '' : state.error ? ' job-error' : ' job-success'}`}
      role={state.error ? 'alert' : 'status'}
      aria-live="polite"
    >
      {running ? (
        <span className="job-spinner" aria-hidden="true" />
      ) : (
        <span className="job-result-icon" aria-hidden="true">
          {state.error ? '!' : '✓'}
        </span>
      )}
      <span className="job-text">
        {running ? stageLabel(state) : state.error ? `Falha no download: ${state.error}` : message}
        {running && percent !== null && <small> {percent}%</small>}
        {running && state.pending_recordings > 0 && <small> · {state.pending_recordings} na fila</small>}
      </span>
      {running && percent !== null && (
        <span className="job-progress">
          <i style={{ width: `${percent}%` }} />
        </span>
      )}
      <button
        className="tertiary"
        type="button"
        onClick={() => (running ? void api.cancelJobs() : setShowOutcome(false))}
      >
        {running ? 'Parar' : 'Fechar'}
      </button>
    </div>
  )
}
