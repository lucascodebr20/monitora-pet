import { FormEvent, useCallback, useEffect, useState } from 'react'
import * as api from '../api'
import type { Camera, Recording, WatchedFolder } from '../api'
import { pickFolder } from '../lib/desktop'
import { errorMessage } from '../lib/errors'
import { useEscape } from '../lib/hooks'
import {
  formatDateTime,
  formatDuration,
  recordingStatusLabels,
  recordingTimeSourceLabels,
  toLocalInputValue,
} from '../lib/labels'
import { useToast } from './useToast'

type Props = { camera: Camera; onClose: () => void; reloadToken: number }

function durationOf(recording: Recording): number {
  return (new Date(recording.ended_at).getTime() - new Date(recording.started_at).getTime()) / 1000
}

export default function RecordingsPanel({ camera, onClose, reloadToken }: Props) {
  const showToast = useToast()
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [folders, setFolders] = useState<WatchedFolder[]>([])
  const [path, setPath] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [editingTime, setEditingTime] = useState<Recording | null>(null)
  const [timeValue, setTimeValue] = useState('')

  useEscape(onClose)

  const load = useCallback(async () => {
    try {
      const [recordingList, folderList] = await Promise.all([
        api.getRecordings(camera.id),
        api.getWatchedFolders(camera.id),
      ])
      setRecordings(recordingList)
      setFolders(folderList)
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível carregar as gravações.'))
    }
  }, [camera.id])

  useEffect(() => {
    void load()
  }, [load, reloadToken])

  async function choose() {
    const selected = await pickFolder()
    if (selected === undefined) {
      setError('A seleção de pastas está disponível no aplicativo desktop do Monitora Pet.')
      return
    }
    if (selected) {
      setPath(selected)
      setError('')
    }
  }

  async function importNow(event: FormEvent) {
    event.preventDefault()
    if (!path.trim()) return
    setBusy(true)
    setError('')
    try {
      const imported = await api.importRecordings(camera.id, path.trim())
      showToast(
        imported.length
          ? `${imported.length} gravação(ões) adicionada(s) à fila.`
          : 'Nenhum vídeo novo encontrado nesse caminho.',
      )
      await load()
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível importar.'))
    } finally {
      setBusy(false)
    }
  }

  async function watch() {
    if (!path.trim()) return
    setBusy(true)
    setError('')
    try {
      const folder = await api.createWatchedFolder(camera.id, path.trim())
      const imported = await api.scanWatchedFolder(folder.id)
      showToast(`Pasta vigiada. ${imported.length} gravação(ões) encontrada(s).`)
      setPath('')
      await load()
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível vigiar a pasta.'))
    } finally {
      setBusy(false)
    }
  }

  async function analyzeNow() {
    try {
      await api.startImportJob(camera.id)
      showToast('Análise iniciada em segundo plano.')
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível iniciar a análise.'), 'error')
    }
  }

  async function scan(folder: WatchedFolder) {
    setBusy(true)
    try {
      const imported = await api.scanWatchedFolder(folder.id)
      showToast(imported.length ? `${imported.length} gravação(ões) nova(s).` : 'Nada novo na pasta.')
      await load()
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível varrer a pasta.'), 'error')
    } finally {
      setBusy(false)
    }
  }

  async function unwatch(folder: WatchedFolder) {
    if (!window.confirm(`Deixar de vigiar ${folder.path}?`)) return
    try {
      await api.deleteWatchedFolder(folder.id)
      await load()
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível remover a pasta.'), 'error')
    }
  }

  async function reprocess(recording: Recording) {
    if (!window.confirm('Reprocessar apaga os eventos e as revisões desta gravação. Continuar?')) return
    try {
      await api.reprocessRecording(recording.id)
      showToast('Gravação devolvida à fila.')
      await load()
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível reprocessar.'), 'error')
    }
  }

  function startTimeEdit(recording: Recording) {
    setEditingTime(recording)
    setTimeValue(toLocalInputValue(recording.started_at))
  }

  async function saveTime(event: FormEvent) {
    event.preventDefault()
    if (!editingTime || !timeValue) return
    try {
      await api.adjustRecordingTime(editingTime.id, new Date(timeValue).toISOString())
      showToast('Horário ajustado. A gravação voltou para a fila.')
      setEditingTime(null)
      await load()
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível ajustar o horário.'))
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Gravações da câmera">
      <div className="modal recordings-modal">
        <div className="panel-head">
          <div>
            <p className="eyebrow">GRAVAÇÕES DO CARTÃO</p>
            <h2>{camera.name}</h2>
          </div>
          <button type="button" className="close" aria-label="Fechar" onClick={onClose}>
            ×
          </button>
        </div>
        <form className="recording-import" onSubmit={importNow}>
          <div className="wide recording-folder-field">
            <span className="recording-folder-label">Pasta com as gravações</span>
            <div className="recording-folder-picker">
              <input value={path} readOnly placeholder="Nenhuma pasta selecionada" title={path || undefined} />
              <button type="button" className="secondary" disabled={busy} onClick={() => void choose()}>
                Selecionar pasta
              </button>
            </div>
          </div>
          <div className="recording-import-actions">
            <button className="primary" type="submit" disabled={busy || !path.trim()}>
              {busy ? 'Importando…' : 'Importar agora'}
            </button>
            <button className="secondary" type="button" disabled={busy || !path.trim()} onClick={() => void watch()}>
              Vigiar esta pasta
            </button>
          </div>
          <small className="muted">
            Pastas vigiadas são varridas automaticamente sempre que o aplicativo abre e a cada nova importação.
          </small>
        </form>
        {folders.length > 0 && (
          <section className="watched-folders">
            <h3>Pastas vigiadas</h3>
            <ul>
              {folders.map(folder => (
                <li key={folder.id}>
                  <span>
                    <strong>{folder.path}</strong>
                    <small>
                      {folder.last_scanned_at
                        ? `Última varredura ${formatDateTime(folder.last_scanned_at)}`
                        : 'Ainda não varrida'}
                    </small>
                  </span>
                  <span className="camera-actions">
                    <button className="tertiary" type="button" disabled={busy} onClick={() => void scan(folder)}>
                      Varrer
                    </button>
                    <button className="tertiary danger" type="button" onClick={() => void unwatch(folder)}>
                      Remover
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
        {error && <p className="form-error">{error}</p>}
        <section className="recording-list">
          <div className="panel-head">
            <h3>Gravações ({recordings.length})</h3>
            {recordings.some(item => item.status === 'PENDING') && (
              <button className="secondary" type="button" onClick={() => void analyzeNow()}>
                Analisar agora
              </button>
            )}
          </div>
          {!recordings.length && <p className="muted">Nenhuma gravação importada para esta câmera.</p>}
          <ul>
            {recordings.map(recording => (
              <li key={recording.id} className={`recording-row ${recording.status.toLowerCase()}`}>
                <div>
                  <strong>{formatDateTime(recording.started_at)}</strong>
                  <small>
                    {formatDuration(durationOf(recording))} · {recordingTimeSourceLabels[recording.time_source]}
                  </small>
                  <small className="recording-path-label" title={recording.path}>
                    {recording.path}
                  </small>
                  {recording.error && <small className="form-error">{recording.error}</small>}
                </div>
                <div className="recording-row-actions">
                  <span className={`badge ${recording.status.toLowerCase()}`}>
                    {recordingStatusLabels[recording.status]}
                    {recording.status === 'PROCESSING' && durationOf(recording) > 0 && (
                      <> {Math.min(100, Math.round((recording.processed_seconds / durationOf(recording)) * 100))}%</>
                    )}
                  </span>
                  {recording.status !== 'PROCESSING' && (
                    <>
                      <button className="tertiary" type="button" onClick={() => startTimeEdit(recording)}>
                        Ajustar horário
                      </button>
                      {recording.status !== 'PENDING' && (
                        <button className="tertiary" type="button" onClick={() => void reprocess(recording)}>
                          Reprocessar
                        </button>
                      )}
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
        {editingTime && (
          <form className="recording-time-form" onSubmit={saveTime}>
            <label>
              Início real da gravação
              <input
                type="datetime-local"
                step="1"
                value={timeValue}
                onChange={event => setTimeValue(event.target.value)}
                required
              />
              <small>Use o relógio exibido no próprio vídeo, se a câmera grava a hora na imagem.</small>
            </label>
            <div className="recording-import-actions">
              <button className="tertiary" type="button" onClick={() => setEditingTime(null)}>
                Cancelar
              </button>
              <button className="primary" type="submit">
                Salvar horário
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
