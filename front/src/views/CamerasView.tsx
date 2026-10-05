import { FormEvent, useCallback, useState } from 'react'
import * as api from '../api'
import type { Camera, CameraCandidate, Zone } from '../api'
import Empty from '../components/Empty'
import Icon from '../components/Icon'
import Status from '../components/Status'
import { useToast } from '../components/useToast'
import { errorMessage } from '../lib/errors'
import { useEscape } from '../lib/hooks'

type Props = { cameras: Camera[]; zones: Zone[]; refresh: () => Promise<void> }

const emptyCameraForm = { name: '', ip: '', username: '', password: '', rtsp_url: '' }
const emptyCredentials = { username: '', password: '', rtsp_url: '' }

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

export default function CamerasView({ cameras, zones, refresh }: Props) {
  const showToast = useToast()
  const [open, setOpen] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [candidates, setCandidates] = useState<CameraCandidate[]>([])
  const [form, setForm] = useState(emptyCameraForm)
  const [reconnectCamera, setReconnectCamera] = useState<Camera | null>(null)
  const [credentials, setCredentials] = useState(emptyCredentials)
  const [error, setError] = useState('')
  const [zoneOverlays, setZoneOverlays] = useState<string[]>([])

  const closeModals = useCallback(() => {
    setOpen(false)
    setReconnectCamera(null)
  }, [])
  useEscape(closeModals, open || reconnectCamera !== null)

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

  async function remove(camera: Camera) {
    if (!window.confirm(`Remover a câmera ${camera.name} e suas áreas?`)) return
    try {
      await api.deleteCamera(camera.id)
      await refresh()
      showToast(`Câmera ${camera.name} removida.`)
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível remover a câmera.'), 'error')
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">MONITORAMENTO</p>
          <h1>Câmeras</h1>
          <p>Gerencie as fontes de vídeo usadas pelo VigiaPet.</p>
        </div>
        <button
          className="primary"
          onClick={() => {
            setCandidates([])
            setError('')
            setOpen(true)
          }}
        >
          + Adicionar câmera
        </button>
      </div>
      <section className="camera-grid">
        {cameras.map(camera => {
          const cameraZones = zones.filter(zone => zone.camera_id === camera.id && zone.enabled)
          const showZones = zoneOverlays.includes(camera.id)
          return (
            <article className="camera-card" key={camera.id}>
              <div className="preview">
                {camera.status.connected ? (
                  <img src={`/api/cameras/${camera.id}/video`} alt={`Vídeo ao vivo de ${camera.name}`} />
                ) : (
                  <div className="offline-message">
                    <Icon name="camera" />
                    <strong>Câmera desconectada</strong>
                    <p>{camera.status.message || 'Reconecte para continuar acompanhando esta área.'}</p>
                  </div>
                )}
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
                <Status connected={camera.status.connected} />
              </div>
              <div className="camera-info">
                <div>
                  <h3>{camera.name}</h3>
                  <p>
                    {camera.model || camera.manufacturer || 'Câmera IP'} · {camera.ip}
                  </p>
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
                  {!camera.status.connected && (
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
            Adicione até duas câmeras IP para começar o monitoramento local.
          </Empty>
        </section>
      )}
      {open && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Configurar câmera">
          <form className="modal" onSubmit={submit}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">NOVA CÂMERA</p>
                <h2>Conectar câmera IP</h2>
              </div>
              <button type="button" className="close" aria-label="Fechar" onClick={() => setOpen(false)}>
                ×
              </button>
            </div>
            <button type="button" className="secondary full" onClick={discover} disabled={discovering}>
              {discovering ? 'Procurando na rede…' : 'Localizar automaticamente'}
            </button>
            {candidates.length > 0 && (
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
              <label>
                Nome
                <input
                  required
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="Ex.: Sala"
                />
              </label>
              <label>
                Endereço IP
                <input
                  required
                  value={form.ip}
                  onChange={e => setForm({ ...form, ip: e.target.value })}
                  placeholder="192.168.1.100"
                />
              </label>
              <label>
                Usuário
                <input
                  value={form.username}
                  onChange={e => setForm({ ...form, username: e.target.value })}
                  autoComplete="username"
                />
              </label>
              <label>
                Senha
                <input
                  type="password"
                  value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  autoComplete="current-password"
                />
              </label>
              <label className="wide">
                URL RTSP opcional
                <input
                  value={form.rtsp_url}
                  onChange={e => setForm({ ...form, rtsp_url: e.target.value })}
                  placeholder="rtsp://192.168.1.100:554/stream"
                />
              </label>
            </div>
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
              <label>
                Usuário
                <input
                  value={credentials.username}
                  onChange={event => setCredentials({ ...credentials, username: event.target.value })}
                  autoComplete="username"
                />
              </label>
              <label>
                Senha
                <input
                  type="password"
                  value={credentials.password}
                  onChange={event => setCredentials({ ...credentials, password: event.target.value })}
                  autoComplete="current-password"
                />
              </label>
              <label className="wide">
                URL RTSP opcional
                <input
                  value={credentials.rtsp_url}
                  onChange={event => setCredentials({ ...credentials, rtsp_url: event.target.value })}
                  placeholder="Use somente se a descoberta automática falhar"
                />
              </label>
            </div>
            {error && <p className="form-error">{error}</p>}
            <button className="primary full">Conectar câmera</button>
          </form>
        </div>
      )}
    </>
  )
}
