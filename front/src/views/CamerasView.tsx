import { FormEvent, useCallback, useState } from 'react'
import * as api from '../api'
import type { Camera, CameraCandidate, Zone } from '../api'
import Empty from '../components/Empty'
import Icon from '../components/Icon'
import RecordingsPanel from '../components/RecordingsPanel'
import Status from '../components/Status'
import { useToast } from '../components/useToast'
import { errorMessage } from '../lib/errors'
import { useEscape } from '../lib/hooks'
import { recordingSupportLabels } from '../lib/labels'

type Props = { cameras: Camera[]; zones: Zone[]; refresh: () => Promise<void>; reloadToken: number }
type Mode = 'network' | 'manual'

const emptyCameraForm = { name: '', ip: '', username: '', password: '', rtsp_url: '' }
const emptyCredentials = { username: '', password: '', rtsp_url: '' }
const emptyConvert = { ip: '', username: '', password: '', rtsp_url: '' }

function candidateDetails(item: CameraCandidate): string {
  const identity = [
    item.manufacturer,
    item.model !== item.name ? item.model : '',
    item.friendly_name !== item.name ? item.friendly_name : '',
    item.hostname !== item.name ? item.hostname : '',
    item.web_title ? `Interface: ${item.web_title}` : '',
  ]
    .filter(Boolean)
    .join(' · ')
  return [identity, item.reason].filter(Boolean).join(' · ') || 'Dispositivo ONVIF'
}

function polygonCenter(polygon: Zone['polygon']) {
  return polygon.reduce(
    (value, point) => ({ x: value.x + point.x / polygon.length, y: value.y + point.y / polygon.length }),
    { x: 0, y: 0 },
  )
}

function CredentialFields({
  value,
  onChange,
  placeholder,
}: {
  value: { username: string; password: string; rtsp_url: string }
  onChange: (next: { username: string; password: string; rtsp_url: string }) => void
  placeholder: string
}) {
  return (
    <>
      <label>
        Usuário
        <input
          value={value.username}
          onChange={event => onChange({ ...value, username: event.target.value })}
          autoComplete="username"
        />
      </label>
      <label>
        Senha
        <input
          type="password"
          value={value.password}
          onChange={event => onChange({ ...value, password: event.target.value })}
          autoComplete="current-password"
        />
      </label>
      <label className="wide">
        URL RTSP opcional
        <input
          value={value.rtsp_url}
          onChange={event => onChange({ ...value, rtsp_url: event.target.value })}
          placeholder={placeholder}
        />
      </label>
    </>
  )
}

export default function CamerasView({ cameras, zones, refresh, reloadToken }: Props) {
  const showToast = useToast()
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<Mode>('network')
  const [discovering, setDiscovering] = useState(false)
  const [candidates, setCandidates] = useState<CameraCandidate[]>([])
  const [form, setForm] = useState(emptyCameraForm)
  const [reconnectCamera, setReconnectCamera] = useState<Camera | null>(null)
  const [convertCamera, setConvertCamera] = useState<Camera | null>(null)
  const [recordingsCamera, setRecordingsCamera] = useState<Camera | null>(null)
  const [credentials, setCredentials] = useState(emptyCredentials)
  const [convert, setConvert] = useState(emptyConvert)
  const [error, setError] = useState('')
  const [zoneOverlays, setZoneOverlays] = useState<string[]>([])
  const [previewFailures, setPreviewFailures] = useState<string[]>([])

  const closeModals = useCallback(() => {
    setOpen(false)
    setReconnectCamera(null)
    setConvertCamera(null)
  }, [])
  useEscape(closeModals, open || reconnectCamera !== null || convertCamera !== null)

  function toggleZoneOverlay(cameraId: string) {
    setZoneOverlays(current =>
      current.includes(cameraId) ? current.filter(id => id !== cameraId) : [...current, cameraId],
    )
  }

  async function discover() {
    setDiscovering(true)
    setError('')
    try {
      let found = await api.discoverCameras()
      if (!found.length) found = await api.discoverCameras(true)
      setCandidates(found)
    } catch (reason) {
      setError(errorMessage(reason, 'Falha na descoberta.'))
    } finally {
      setDiscovering(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      if (mode === 'manual') {
        const camera = await api.createManualCamera(form.name)
        setOpen(false)
        setForm(emptyCameraForm)
        await refresh()
        showToast('Câmera cadastrada. Importe as gravações do cartão.')
        setRecordingsCamera(camera)
        return
      }
      await api.createCamera({ ...form, rtsp_url: form.rtsp_url || null })
      setOpen(false)
      setCandidates([])
      setForm(emptyCameraForm)
      await refresh()
      showToast('Câmera cadastrada.')
    } catch (reason) {
      setError(errorMessage(reason, 'Falha ao cadastrar.'))
    }
  }

  async function reconnect(event: FormEvent) {
    event.preventDefault()
    if (!reconnectCamera) return
    setError('')
    try {
      await api.connectCamera(reconnectCamera.id, { ...credentials, rtsp_url: credentials.rtsp_url || null })
      setReconnectCamera(null)
      setCredentials(emptyCredentials)
      await refresh()
      showToast(`${reconnectCamera.name} conectada.`)
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível conectar a câmera.'))
    }
  }

  async function convertToNetwork(event: FormEvent) {
    event.preventDefault()
    if (!convertCamera) return
    setError('')
    try {
      await api.convertCamera(convertCamera.id, { ...convert, rtsp_url: convert.rtsp_url || null })
      setConvertCamera(null)
      setConvert(emptyConvert)
      await refresh()
      showToast(`${convertCamera.name} agora é uma câmera de rede.`)
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível converter a câmera.'))
    }
  }

  async function syncNow(camera: Camera) {
    try {
      await api.startSyncJob(camera.id)
      showToast(`Buscando gravações novas em ${camera.name}…`)
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível iniciar o download.'), 'error')
    }
  }

  async function remove(camera: Camera) {
    if (!window.confirm(`Remover a câmera ${camera.name}, suas áreas e seus eventos?`)) return
    try {
      await api.deleteCamera(camera.id)
      await refresh()
      showToast(`Câmera ${camera.name} removida.`)
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível remover a câmera.'), 'error')
    }
  }

  function openAdd(initialMode: Mode) {
    setCandidates([])
    setError('')
    setMode(initialMode)
    setOpen(true)
  }

  function cameraPreview(camera: Camera) {
    if (camera.status.connected) {
      return <img src={`/api/cameras/${camera.id}/video`} alt={`Vídeo ao vivo de ${camera.name}`} />
    }
    if (!previewFailures.includes(camera.id)) {
      return (
        <>
          <img
            src={`/api/cameras/${camera.id}/preview?v=${reloadToken}`}
            alt={`Última imagem de ${camera.name}`}
            onError={() => setPreviewFailures(current => [...current, camera.id])}
          />
          <span className="still-caption">Última gravação</span>
        </>
      )
    }
    return (
      <div className="offline-message">
        <Icon name="camera" />
        <strong>{camera.source_kind === 'MANUAL' ? 'Sem gravações importadas' : 'Câmera desconectada'}</strong>
        <p>
          {camera.source_kind === 'MANUAL'
            ? 'Importe os vídeos do cartão para começar a análise.'
            : camera.status.message || 'Reconecte para continuar acompanhando esta área.'}
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">MONITORAMENTO</p>
          <h1>Câmeras</h1>
          <p>Gerencie as fontes de vídeo usadas pelo Monitora Pet.</p>
        </div>
        <button className="primary" onClick={() => openAdd('network')}>
          + Adicionar câmera
        </button>
      </div>
      <section className="camera-grid">
        {cameras.map(camera => {
          const cameraZones = zones.filter(zone => zone.camera_id === camera.id && zone.enabled)
          const showZones = zoneOverlays.includes(camera.id)
          const manual = camera.source_kind === 'MANUAL'
          return (
            <article className="camera-card" key={camera.id}>
              <div className="preview">
                {cameraPreview(camera)}
                {showZones && (
                  <div className="camera-zone-overlay">
                    {cameraZones.map(zone => {
                      const center = polygonCenter(zone.polygon)
                      return (
                        <div className={`camera-zone ${zone.type.toLowerCase()}`} key={zone.id}>
                          <svg viewBox="0 0 100 100" preserveAspectRatio="none">
                            <polygon
                              points={zone.polygon.map(point => `${point.x * 100},${point.y * 100}`).join(' ')}
                            />
                          </svg>
                          <span style={{ left: `${center.x * 100}%`, top: `${center.y * 100}%` }}>{zone.name}</span>
                        </div>
                      )
                    })}
                  </div>
                )}
                {!manual && <Status connected={camera.status.connected} />}
              </div>
              <div className="camera-info">
                <div>
                  <h3>{camera.name}</h3>
                  <p>
                    {manual
                      ? 'Gravações do cartão de memória'
                      : `${camera.model || camera.manufacturer || 'Câmera IP'} · ${camera.ip}`}
                  </p>
                  {!manual && <small className="muted">{recordingSupportLabels[camera.recording_support]}</small>}
                </div>
                <div className="camera-actions">
                  {cameraZones.length > 0 && (
                    <button
                      className={`tertiary zone-toggle ${showZones ? 'active' : ''}`}
                      onClick={() => toggleZoneOverlay(camera.id)}
                    >
                      {showZones ? 'Ocultar zonas' : `Mostrar zonas (${cameraZones.length})`}
                    </button>
                  )}
                  <button className="tertiary" onClick={() => setRecordingsCamera(camera)}>
                    Gravações
                  </button>
                  {camera.recording_support === 'ONVIF_REPLAY' && (
                    <button className="tertiary" onClick={() => void syncNow(camera)}>
                      Baixar da câmera
                    </button>
                  )}
                  {manual && (
                    <button
                      className="tertiary"
                      onClick={() => {
                        setConvertCamera(camera)
                        setError('')
                      }}
                    >
                      Conectar pela rede
                    </button>
                  )}
                  {!manual && !camera.status.connected && (
                    <button
                      className="tertiary"
                      onClick={() => {
                        setReconnectCamera(camera)
                        setError('')
                      }}
                    >
                      Conectar
                    </button>
                  )}
                  <button className="tertiary danger" onClick={() => void remove(camera)}>
                    Remover
                  </button>
                </div>
              </div>
            </article>
          )
        })}
      </section>
      {!cameras.length && (
        <section className="panel">
          <Empty title="Nenhuma câmera cadastrada">
            Conecte uma câmera IP da sua rede ou cadastre uma câmera que grava no cartão de memória para importar os
            vídeos depois.
          </Empty>
        </section>
      )}
      {open && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Configurar câmera">
          <form className="modal" onSubmit={submit}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">NOVA CÂMERA</p>
                <h2>{mode === 'network' ? 'Conectar câmera IP' : 'Câmera com cartão de memória'}</h2>
              </div>
              <button type="button" className="close" aria-label="Fechar" onClick={() => setOpen(false)}>
                ×
              </button>
            </div>
            <div className="camera-mode-toggle" role="tablist">
              <button
                type="button"
                className={mode === 'network' ? 'secondary' : 'tertiary'}
                aria-pressed={mode === 'network'}
                onClick={() => setMode('network')}
              >
                Pela rede
              </button>
              <button
                type="button"
                className={mode === 'manual' ? 'secondary' : 'tertiary'}
                aria-pressed={mode === 'manual'}
                onClick={() => setMode('manual')}
              >
                Pelo cartão de memória
              </button>
            </div>
            {mode === 'network' && (
              <button type="button" className="secondary full" onClick={discover} disabled={discovering}>
                {discovering ? 'Procurando na rede…' : 'Localizar automaticamente'}
              </button>
            )}
            {mode === 'network' && candidates.length > 0 && (
              <div className="candidate-list">
                {candidates.map(item => (
                  <button
                    type="button"
                    key={item.ip}
                    onClick={() => setForm(value => ({ ...value, ip: item.ip, name: item.name }))}
                  >
                    <span>
                      <strong>{item.name}</strong>
                      <small>{candidateDetails(item)}</small>
                    </span>
                    <span>{item.ip}</span>
                  </button>
                ))}
              </div>
            )}
            <div className="form-grid">
              <label className={mode === 'manual' ? 'wide' : ''}>
                Nome
                <input
                  required
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="Ex.: Sala"
                />
              </label>
              {mode === 'network' && (
                <>
                  <label>
                    Endereço IP
                    <input
                      required
                      value={form.ip}
                      onChange={e => setForm({ ...form, ip: e.target.value })}
                      placeholder="192.168.1.100"
                    />
                  </label>
                  <CredentialFields
                    value={form}
                    onChange={next => setForm({ ...form, ...next })}
                    placeholder="rtsp://192.168.1.100:554/stream"
                  />
                </>
              )}
            </div>
            {mode === 'manual' && (
              <p className="muted">
                A câmera grava no cartão. No fim do dia você copia os vídeos para o computador e o Monitora Pet analisa
                tudo em segundo plano.
              </p>
            )}
            {error && <p className="form-error">{error}</p>}
            <button className="primary full" type="submit">
              Cadastrar câmera
            </button>
          </form>
        </div>
      )}
      {reconnectCamera && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Configurar câmera">
          <form className="modal compact-modal" onSubmit={reconnect}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">RECONECTAR</p>
                <h2>{reconnectCamera.name}</h2>
                <p>{reconnectCamera.ip}</p>
              </div>
              <button type="button" className="close" aria-label="Fechar" onClick={() => setReconnectCamera(null)}>
                ×
              </button>
            </div>
            <div className="form-grid">
              <CredentialFields
                value={credentials}
                onChange={setCredentials}
                placeholder="Use somente se a descoberta automática falhar"
              />
            </div>
            {error && <p className="form-error">{error}</p>}
            <button className="primary full">Conectar câmera</button>
          </form>
        </div>
      )}
      {convertCamera && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Conectar pela rede">
          <form className="modal compact-modal" onSubmit={convertToNetwork}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">CONECTAR PELA REDE</p>
                <h2>{convertCamera.name}</h2>
                <p>As zonas e o histórico desta câmera são mantidos.</p>
              </div>
              <button type="button" className="close" aria-label="Fechar" onClick={() => setConvertCamera(null)}>
                ×
              </button>
            </div>
            <div className="form-grid">
              <label className="wide">
                Endereço IP
                <input
                  required
                  value={convert.ip}
                  onChange={event => setConvert({ ...convert, ip: event.target.value })}
                  placeholder="192.168.1.100"
                />
              </label>
              <CredentialFields
                value={convert}
                onChange={next => setConvert({ ...convert, ...next })}
                placeholder="rtsp://192.168.1.100:554/stream"
              />
            </div>
            {error && <p className="form-error">{error}</p>}
            <button className="primary full">Conectar câmera</button>
          </form>
        </div>
      )}
      {recordingsCamera && (
        <RecordingsPanel
          camera={recordingsCamera}
          onClose={() => setRecordingsCamera(null)}
          reloadToken={reloadToken}
        />
      )}
    </>
  )
}
