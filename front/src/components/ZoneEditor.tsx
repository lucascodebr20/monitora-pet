import { FormEvent, MouseEvent, PointerEvent, memo, useEffect, useMemo, useRef, useState } from 'react'
import * as api from '../api'
import type { Camera, MonitoringFeedback, Zone } from '../api'
import { errorMessage } from '../lib/errors'
import { zoneIcon, zoneLabels } from '../lib/labels'
import Icon from './Icon'
import { useToast } from './useToast'

type Point = { x: number; y: number }
type Props = { cameras: Camera[]; zones: Zone[]; refresh: () => Promise<void> }
type ZoneForm = Omit<Zone, 'id' | 'enabled' | 'camera_id' | 'polygon'>

const FEEDBACK_INTERVAL_MS = 750
const MIN_POINTS = 3
const HANDLE_RADIUS = 1.25

const emptyForm: ZoneForm = {
  name: '',
  type: 'FOOD',
  minimum_presence_seconds: 3,
  absence_tolerance_seconds: 1,
  cooldown_seconds: 10,
}

const clamp = (value: number) => Math.max(0, Math.min(1, value))
const toSvgPoints = (points: Point[]) => points.map(point => `${point.x * 100},${point.y * 100}`).join(' ')

function normalizedPoint(clientX: number, clientY: number, bounds: DOMRect): Point {
  return { x: clamp((clientX - bounds.left) / bounds.width), y: clamp((clientY - bounds.top) / bounds.height) }
}

function aiStatusLabel(status: MonitoringFeedback['status'] | undefined): string {
  if (status === 'running') return 'IA ativa'
  if (status === 'error') return 'Falha na IA'
  if (status === 'model_missing') return 'Modelo de IA ausente'
  return 'Iniciando IA'
}

const CameraVideo = memo(function CameraVideo({ cameraId, cameraName }: { cameraId: string; cameraName: string }) {
  return <img src={`/api/cameras/${cameraId}/video`} alt={`Vídeo ao vivo de ${cameraName}`} />
})

export default function ZoneEditor({ cameras, zones, refresh }: Props) {
  const showToast = useToast()
  const [cameraId, setCameraId] = useState('')
  const [saving, setSaving] = useState(false)
  const [points, setPoints] = useState<Point[]>([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null)
  const [selectedPointIndex, setSelectedPointIndex] = useState<number | null>(null)
  const [draggingZone, setDraggingZone] = useState<{ start: Point; original: Point[] } | null>(null)
  const [feedback, setFeedback] = useState<MonitoringFeedback | null>(null)
  const [previewFailed, setPreviewFailed] = useState(false)
  const [error, setError] = useState('')
  const suppressCanvasClick = useRef(false)

  const camera = cameras.find(item => item.id === cameraId)
  const connected = camera?.status.connected ?? false
  const canDraw = connected || (camera !== undefined && !previewFailed)
  const cameraZones = useMemo(() => zones.filter(zone => zone.camera_id === cameraId), [zones, cameraId])
  const feedbackByZone = useMemo(() => new Map((feedback?.zones ?? []).map(item => [item.zone_id, item])), [feedback])

  useEffect(() => {
    if (!cameraId && cameras.length) {
      setCameraId((cameras.find(item => item.status.connected) ?? cameras[0]).id)
    }
  }, [cameraId, cameras])

  useEffect(() => {
    setFeedback(null)
    setPreviewFailed(false)
    if (!cameraId) return
    let active = true
    const load = async () => {
      try {
        const result = await api.getMonitoringFeedback(cameraId)
        if (active) setFeedback(result)
      } catch {
        if (active) setFeedback(null)
      }
    }
    void load()
    const timer = window.setInterval(load, FEEDBACK_INTERVAL_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [cameraId])

  useEffect(() => {
    const removeSelectedPoint = (event: KeyboardEvent) => {
      if (selectedPointIndex === null || (event.key !== 'Delete' && event.key !== 'Backspace')) return
      const target = event.target as HTMLElement | null
      if (target?.matches('input, textarea, select, [contenteditable="true"]')) return
      event.preventDefault()
      setPoints(current => current.filter((_, index) => index !== selectedPointIndex))
      setSelectedPointIndex(null)
    }
    window.addEventListener('keydown', removeSelectedPoint)
    return () => window.removeEventListener('keydown', removeSelectedPoint)
  }, [selectedPointIndex])

  function resetEditor() {
    setPoints([])
    setSelectedPointIndex(null)
    setForm(emptyForm)
    setEditingId(null)
    setError('')
  }

  function closeEditor() {
    if (!saving) resetEditor()
  }

  function startCreate() {
    resetEditor()
    setCameraId((cameras.find(c => c.status.connected) ?? cameras[0])?.id ?? '')
  }

  function selectCamera(id: string) {
    setCameraId(id)
    setPoints([])
    setSelectedPointIndex(null)
    setError('')
  }

  function clearPoints() {
    setPoints([])
    setSelectedPointIndex(null)
  }

  function editZone(zone: Zone) {
    setCameraId(zone.camera_id)
    setPoints(zone.polygon)
    setForm({
      name: zone.name,
      type: zone.type,
      minimum_presence_seconds: zone.minimum_presence_seconds,
      absence_tolerance_seconds: zone.absence_tolerance_seconds,
      cooldown_seconds: zone.cooldown_seconds,
    })
    setEditingId(zone.id)
  }

  function addPoint(event: MouseEvent<SVGSVGElement>) {
    if (suppressCanvasClick.current) {
      suppressCanvasClick.current = false
      return
    }
    if (!canDraw) return
    const point = normalizedPoint(event.clientX, event.clientY, event.currentTarget.getBoundingClientRect())
    setPoints(current => [...current, point])
    setSelectedPointIndex(null)
  }

  function movePoint(event: PointerEvent<SVGSVGElement>) {
    const next = normalizedPoint(event.clientX, event.clientY, event.currentTarget.getBoundingClientRect())
    if (draggingIndex !== null) {
      setPoints(current => current.map((point, index) => (index === draggingIndex ? next : point)))
      return
    }
    if (!draggingZone) return
    const xs = draggingZone.original.map(point => point.x)
    const ys = draggingZone.original.map(point => point.y)
    const deltaX = Math.max(-Math.min(...xs), Math.min(1 - Math.max(...xs), next.x - draggingZone.start.x))
    const deltaY = Math.max(-Math.min(...ys), Math.min(1 - Math.max(...ys), next.y - draggingZone.start.y))
    setPoints(draggingZone.original.map(point => ({ x: point.x + deltaX, y: point.y + deltaY })))
  }

  function startZoneDrag(event: PointerEvent<SVGPolygonElement>, original: Point[], zone?: Zone) {
    event.preventDefault()
    event.stopPropagation()
    if (zone) editZone(zone)
    const svg = event.currentTarget.ownerSVGElement
    if (!svg) return
    setDraggingIndex(null)
    setDraggingZone({ start: normalizedPoint(event.clientX, event.clientY, svg.getBoundingClientRect()), original })
    suppressCanvasClick.current = true
    svg.setPointerCapture(event.pointerId)
  }

  function startPointDrag(event: PointerEvent<SVGCircleElement>, index: number) {
    event.stopPropagation()
    suppressCanvasClick.current = true
    setSelectedPointIndex(index)
    setDraggingZone(null)
    setDraggingIndex(index)
    event.currentTarget.ownerSVGElement?.setPointerCapture(event.pointerId)
  }

  function finishDragging(event: PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    setDraggingIndex(null)
    setDraggingZone(null)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!cameraId || points.length < MIN_POINTS || saving) return
    setError('')
    const payload = { camera_id: cameraId, ...form, polygon: points }
    setSaving(true)
    try {
      if (editingId) await api.updateZone(editingId, payload)
      else await api.createZone(payload)
      await refresh()
      showToast(editingId ? 'Zona atualizada.' : 'Zona criada e monitoramento iniciado.')
      resetEditor()
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível salvar a zona.'))
    } finally {
      setSaving(false)
    }
  }

  async function removeZone() {
    const zone = zones.find(item => item.id === editingId)
    if (!zone || !window.confirm(`Remover a zona ${zone.name}?`)) return
    try {
      await api.deleteZone(zone.id)
      resetEditor()
      await refresh()
      showToast(`Zona ${zone.name} removida.`)
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível remover a zona.'))
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">DEFINA O QUE ACOMPANHAR</p>
          <h1>Zonas monitoradas</h1>
        </div>
        <button className="primary" onClick={startCreate}>
          + Cadastrar zona
        </button>
      </div>
      <section className="zone-filter-panel" aria-label="Selecionar zona">
        <span>Zonas</span>
        <div>
          {zones.map(zone => (
            <button
              type="button"
              className={editingId === zone.id ? 'selected' : ''}
              aria-pressed={editingId === zone.id}
              key={zone.id}
              onClick={() => editZone(zone)}
            >
              <Icon name={zoneIcon(zone.type)} />
              {zone.name}
            </button>
          ))}
          {!zones.length && <p>Nenhuma zona cadastrada.</p>}
        </div>
      </section>
      <section className="zone-workspace">
        <div className="zone-editor-panel">
          <div className="zone-toolbar">
            <fieldset className="zone-camera-picker">
              <legend>Câmera</legend>
              <div>
                {cameras.map(item => (
                  <button
                    type="button"
                    aria-pressed={cameraId === item.id}
                    className={cameraId === item.id ? 'selected' : ''}
                    key={item.id}
                    onClick={() => selectCamera(item.id)}
                  >
                    {item.name}
                    <small>{item.status.connected ? 'Online' : 'Offline'}</small>
                  </button>
                ))}
              </div>
              {!cameras.length && <p className="muted">Cadastre uma câmera antes de criar a zona.</p>}
            </fieldset>
            <div>
              <button className="tertiary" type="button" disabled={!points.length} onClick={clearPoints}>
                Limpar
              </button>
            </div>
          </div>
          <div className={`zone-canvas ${canDraw ? '' : 'disabled'}`}>
            {camera && connected ? (
              <CameraVideo cameraId={camera.id} cameraName={camera.name} />
            ) : camera && !previewFailed ? (
              <>
                <img
                  src={`/api/cameras/${camera.id}/preview?v=${camera.id}`}
                  alt={`Última imagem de ${camera.name}`}
                  onError={() => setPreviewFailed(true)}
                />
                <span className="still-caption">Imagem da última gravação</span>
              </>
            ) : (
              <div className="zone-video-empty">
                <strong>{camera ? 'Sem imagem disponível' : 'Selecione uma câmera'}</strong>
                <span>Conecte a câmera ou importe uma gravação para desenhar a zona.</span>
              </div>
            )}
            {canDraw && (
              <svg
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                onClick={addPoint}
                onPointerMove={movePoint}
                onPointerUp={finishDragging}
              >
                {cameraZones
                  .filter(zone => zone.id !== editingId)
                  .map(zone => (
                    <polygon
                      key={zone.id}
                      className={`saved-zone ${zone.type.toLowerCase()} ${feedbackByZone.get(zone.id)?.inside ? 'detected' : ''}`}
                      points={toSvgPoints(zone.polygon)}
                      onPointerDown={event => startZoneDrag(event, zone.polygon, zone)}
                    />
                  ))}
                {points.length >= 2 && <polyline className="draft-zone" points={toSvgPoints(points)} />}
                {points.length >= MIN_POINTS && (
                  <polygon
                    className="draft-fill"
                    points={toSvgPoints(points)}
                    onPointerDown={event => startZoneDrag(event, points)}
                  />
                )}
                {points.map((point, index) => (
                  <circle
                    key={index}
                    className={`zone-handle ${selectedPointIndex === index ? 'selected' : ''}`}
                    cx={point.x * 100}
                    cy={point.y * 100}
                    r={HANDLE_RADIUS}
                    onPointerDown={event => startPointDrag(event, index)}
                    onClick={event => {
                      event.stopPropagation()
                      suppressCanvasClick.current = false
                      setSelectedPointIndex(index)
                    }}
                  />
                ))}
                {(feedback?.detections ?? []).map((detection, index) => (
                  <g key={index} className="ai-detection">
                    <rect
                      x={detection.x1 * 100}
                      y={detection.y1 * 100}
                      width={(detection.x2 - detection.x1) * 100}
                      height={(detection.y2 - detection.y1) * 100}
                    />
                    <text x={detection.x1 * 100} y={Math.max(3, detection.y1 * 100 - 1)}>
                      {detection.species === 'CAT' ? 'Gato' : 'Cão'} {Math.round(detection.confidence * 100)}%
                    </text>
                  </g>
                ))}
              </svg>
            )}
            {connected && (
              <div className={`ai-status ${feedback?.status === 'running' ? 'ready' : ''}`}>
                <i />
                {aiStatusLabel(feedback?.status)}
              </div>
            )}
          </div>
          <p className="drawing-hint">
            Clique na imagem para adicionar os limites. Para remover um ponto, selecione-o e pressione Delete.
          </p>
        </div>
        <aside className="zone-settings">
          <form className="panel stack-form" onSubmit={submit}>
            <div>
              <p className="eyebrow">{editingId ? 'EDITAR ÁREA' : 'NOVA ÁREA'}</p>
              <h2>{editingId ? 'Configurações da zona' : 'Cadastrar zona'}</h2>
            </div>
            <label>
              Nome
              <input
                required
                value={form.name}
                onChange={event => setForm({ ...form, name: event.target.value })}
                placeholder="Ex.: Pote de água"
              />
            </label>
            <fieldset className="zone-type-picker">
              <legend>Tipo</legend>
              <div>
                {(Object.entries(zoneLabels) as [Zone['type'], string][]).map(([value, label]) => (
                  <label className={form.type === value ? 'selected' : ''} key={value}>
                    <input
                      type="radio"
                      name="zone-type"
                      checked={form.type === value}
                      onChange={() => setForm({ ...form, type: value })}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
            <label>
              Permanência para confirmar
              <input
                type="number"
                min="0.5"
                max="300"
                step="0.5"
                value={form.minimum_presence_seconds}
                onChange={event => setForm({ ...form, minimum_presence_seconds: Number(event.target.value) })}
              />
              <small>Segundos que o pet precisa permanecer na área.</small>
            </label>
            <div className="two-inputs">
              <label>
                Tolerância
                <input
                  type="number"
                  min="0"
                  max="30"
                  step="0.5"
                  value={form.absence_tolerance_seconds}
                  onChange={event => setForm({ ...form, absence_tolerance_seconds: Number(event.target.value) })}
                />
              </label>
              <label>
                Intervalo entre visitas
                <input
                  type="number"
                  min="0"
                  max="3600"
                  step="1"
                  value={form.cooldown_seconds}
                  onChange={event => setForm({ ...form, cooldown_seconds: Number(event.target.value) })}
                />
              </label>
            </div>
            {error && <p className="form-error">{error}</p>}
            <div className="zone-form-actions">
              <button className="tertiary" type="button" disabled={saving} onClick={closeEditor}>
                {editingId ? 'Cancelar' : 'Limpar campos'}
              </button>
              {editingId && (
                <button className="tertiary danger" type="button" disabled={saving} onClick={() => void removeZone()}>
                  Remover
                </button>
              )}
              <button className="primary" disabled={saving || !canDraw || points.length < MIN_POINTS}>
                {saving ? 'Salvando…' : editingId ? 'Salvar' : 'Cadastrar zona'}
              </button>
            </div>
          </form>
        </aside>
      </section>
    </>
  )
}
