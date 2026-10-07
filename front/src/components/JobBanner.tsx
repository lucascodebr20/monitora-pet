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
  const previous = useRef<JobState | null>(null)

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
        if (before?.status === 'running' && next.status === 'idle') {
          const message = resultMessage(next)
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
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [refresh, showToast])

  if (!state || state.status !== 'running') return null
  const percent =
    state.total_seconds > 0 ? Math.min(100, Math.round((state.progress_seconds / state.total_seconds) * 100)) : null

  return (
    <div className="job-banner" role="status" aria-live="polite">
      <span className="job-spinner" aria-hidden="true" />
      <span className="job-text">
        {stageLabel(state)}
        {percent !== null && <small> {percent}%</small>}
        {state.pending_recordings > 0 && <small> · {state.pending_recordings} na fila</small>}
      </span>
      {percent !== null && (
        <span className="job-progress">
          <i style={{ width: `${percent}%` }} />
        </span>
      )}
      <button className="tertiary" type="button" onClick={() => void api.cancelJobs()}>
        Parar
      </button>
    </div>
  )
}
