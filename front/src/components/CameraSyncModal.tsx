import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Camera, JobState } from '../api'
import { useEscape } from '../lib/hooks'

type Props = {
  camera: Camera
  requestedAt: number
  startError?: string
  onClose: () => void
  refresh: () => Promise<void>
}

type StepState = 'waiting' | 'active' | 'done' | 'error'

const POLL_MS = 800

function finishedAfterRequest(state: JobState, requestedAt: number): boolean {
  if (!state.finished_at || state.camera_id === null) return false
  return Date.parse(state.finished_at) >= requestedAt - 1000
}

function stepClass(state: StepState): string {
  return `camera-sync-step ${state}`
}

export default function CameraSyncModal({ camera, requestedAt, startError, onClose, refresh }: Props) {
  const [job, setJob] = useState<JobState | null>(null)
  const [pollError, setPollError] = useState('')
  const observedRunning = useRef(false)
  const refreshed = useRef(false)
  useEscape(onClose)

  useEffect(() => {
    if (startError) return
    let active = true
    let timer = 0

    const tick = async () => {
      try {
        const next = await api.getJobState()
        if (!active) return
        setJob(next)
        setPollError('')

        const belongsToCamera = next.camera_id === camera.id
        if (next.status === 'running' && belongsToCamera) observedRunning.current = true
        const finished =
          next.status === 'idle' &&
          belongsToCamera &&
          (observedRunning.current || finishedAfterRequest(next, requestedAt))

        if (finished) {
          if (!refreshed.current) {
            refreshed.current = true
            void refresh()
          }
          return
        }
        timer = window.setTimeout(() => void tick(), POLL_MS)
      } catch {
        if (!active) return
        setPollError('Não foi possível acompanhar o andamento. O trabalho continua em segundo plano.')
        timer = window.setTimeout(() => void tick(), 2500)
      }
    }

    void tick()
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [camera.id, refresh, requestedAt, startError])

  const belongsToCamera = job?.camera_id === camera.id
  const running = Boolean(job?.status === 'running' && belongsToCamera)
  const finished = Boolean(
    job?.status === 'idle' &&
      belongsToCamera &&
      (observedRunning.current || (job && finishedAfterRequest(job, requestedAt))),
  )
  const error = startError || (finished ? job?.error : null) || pollError
  const stage = running ? job?.stage : null
  const processing = stage === 'scanning' || stage === 'analyzing'
  const downloadState: StepState = error
    ? 'error'
    : processing || finished
      ? 'done'
      : running && stage === 'downloading'
        ? 'active'
        : 'waiting'
  const processingState: StepState = error
    ? processing
      ? 'error'
      : 'waiting'
    : finished
      ? 'done'
      : processing
        ? 'active'
        : 'waiting'
  const percent =
    processing && job && job.total_seconds > 0
      ? Math.min(100, Math.round((job.progress_seconds / job.total_seconds) * 100))
      : null
  const downloaded = job?.last_result?.kind === 'sync' ? job.last_result.downloaded : null

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Andamento do download da câmera">
      <section className="modal compact-modal camera-sync-modal">
        <div className="panel-head">
          <div>
            <p className="eyebrow">BAIXAR DA CÂMERA</p>
            <h2>{camera.name}</h2>
            <p>Acompanhe o download e a análise das gravações.</p>
          </div>
          <button type="button" className="close" aria-label="Fechar" onClick={onClose}>
            ×
          </button>
        </div>

        <ol className="camera-sync-steps">
          <li className={stepClass(downloadState)}>
            <span className="camera-sync-step-icon" aria-hidden="true">
              {downloadState === 'done' ? '✓' : downloadState === 'error' ? '!' : '1'}
            </span>
            <span>
              <strong>Download das gravações</strong>
              <small>
                {downloadState === 'active'
                  ? 'Buscando e baixando os vídeos da câmera…'
                  : downloadState === 'done'
                    ? `${downloaded ?? 0} trecho(s) novo(s) baixado(s).`
                    : downloadState === 'error'
                      ? 'Não foi possível concluir o download.'
                      : 'Aguardando o trabalho iniciar…'}
              </small>
            </span>
            {downloadState === 'active' && <i className="button-spinner" aria-hidden="true" />}
          </li>
          <li className={stepClass(processingState)}>
            <span className="camera-sync-step-icon" aria-hidden="true">
              {processingState === 'done' ? '✓' : processingState === 'error' ? '!' : '2'}
            </span>
            <span>
              <strong>Análise da rotina dos gatos</strong>
              <small>
                {processingState === 'active'
                  ? stage === 'scanning'
                    ? 'Preparando as gravações baixadas…'
                    : `Analisando os vídeos${percent === null ? '…' : ` · ${percent}%`}`
                  : processingState === 'done'
                    ? 'Processamento concluído.'
                    : 'Começa automaticamente após o download.'}
              </small>
              {processingState === 'active' && percent !== null && (
                <span className="camera-sync-progress" aria-label={`${percent}% concluído`}>
                  <i style={{ width: `${percent}%` }} />
                </span>
              )}
            </span>
            {processingState === 'active' && percent === null && <i className="button-spinner" aria-hidden="true" />}
          </li>
        </ol>

        {error && <p className="camera-sync-message error" role="alert">{error}</p>}
        {!error && finished && Boolean(downloaded) && (
          <p className="camera-sync-message success" role="status">
            Download e análise concluídos.
          </p>
        )}

        <div className="camera-sync-actions">
          {running && (
            <button className="secondary" type="button" onClick={() => void api.cancelJobs()}>
              Parar
            </button>
          )}
          <button className={finished || error ? 'primary' : 'tertiary'} type="button" onClick={onClose}>
            {finished || error ? 'Fechar' : 'Continuar em segundo plano'}
          </button>
        </div>
      </section>
    </div>
  )
}
