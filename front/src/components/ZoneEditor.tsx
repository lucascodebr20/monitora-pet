import { FormEvent, MouseEvent, memo, useEffect, useMemo, useRef, useState } from 'react'
import * as api from '../api'
import type { Camera, MonitoringFeedback, Zone } from '../api'


const zoneLabels: Record<Zone['type'], string> = {
  FOOD: 'Comida',
  WATER: 'Água',
  LITTER: 'Caixa de areia',
  CUSTOM: 'Personalizada',
}

const stateLabels: Record<string, string> = {
  OUTSIDE: 'Sem presença',
  CANDIDATE: 'Verificando permanência',
  ACTIVE: 'Visita confirmada',
  COOLDOWN: 'Aguardando possível retorno',
}

type Point = { x: number; y: number }

type Props = {
  cameras: Camera[]
  zones: Zone[]
  refresh: () => Promise<void>
}

const emptyForm = {
  name: '',
  type: 'FOOD' as Zone['type'],
  minimum_presence_seconds: 3,
  absence_tolerance_seconds: 1,
  cooldown_seconds: 10,
}

const CameraVideo = memo(function CameraVideo({ cameraId, cameraName }: { cameraId: string; cameraName: string }) {
  return <img src={`/api/cameras/${cameraId}/video`} alt={`Vídeo de ${cameraName}`} />
})

export default function ZoneEditor({ cameras, zones, refresh }: Props) {
  const [cameraId, setCameraId] = useState('')
  const [points, setPoints] = useState<Point[]>([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null)
  const [draggingZone, setDraggingZone] = useState<{ start: Point; original: Point[] } | null>(null)
  const [feedback, setFeedback] = useState<MonitoringFeedback | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const suppressCanvasClick = useRef(false)

  const camera = cameras.find(item => item.id === cameraId)
  const cameraZones = useMemo(() => zones.filter(zone => zone.camera_id === cameraId), [zones, cameraId])
  const feedbackByZone = useMemo(
    () => new Map((feedback?.zones ?? []).map(item => [item.zone_id, item])),
    [feedback],
  )

  useEffect(() => {
    if (!cameraId && cameras.length) {
      setCameraId((cameras.find(item => item.status.connected) ?? cameras[0]).id)
    }
  }, [cameraId, cameras])

  useEffect(() => {
    setFeedback(null)
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
    const timer = window.setInterval(load, 750)
    return () => { active = false; window.clearInterval(timer) }
  }, [cameraId])

  function addPoint(event: MouseEvent<SVGSVGElement>) {
    if (suppressCanvasClick.current) {
      suppressCanvasClick.current = false
      return
    }
    if (!camera?.status.connected) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const point = {
      x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
      y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
    }
    setPoints(current => [...current, point])
    setMessage('')
  }

  function movePoint(event: React.PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const next = {
      x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
      y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
    }
    if (draggingIndex !== null) {
      setPoints(current => current.map((point, index) => index === draggingIndex ? next : point))
      return
    }
    if (!draggingZone) return
    const minX = Math.min(...draggingZone.original.map(point => point.x))
    const maxX = Math.max(...draggingZone.original.map(point => point.x))
    const minY = Math.min(...draggingZone.original.map(point => point.y))
    const maxY = Math.max(...draggingZone.original.map(point => point.y))
    const deltaX = Math.max(-minX, Math.min(1 - maxX, next.x - draggingZone.start.x))
    const deltaY = Math.max(-minY, Math.min(1 - maxY, next.y - draggingZone.start.y))
    setPoints(draggingZone.original.map(point => ({ x: point.x + deltaX, y: point.y + deltaY })))
  }

  function startZoneDrag(event: React.PointerEvent<SVGPolygonElement>, original: Point[], zone?: Zone) {
    event.preventDefault()
    event.stopPropagation()
    if (zone) editZone(zone)
    const svg = event.currentTarget.ownerSVGElement
    if (!svg) return
    const bounds = svg.getBoundingClientRect()
    setDraggingIndex(null)
    setDraggingZone({
      start: {
        x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
        y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
      },
      original,
    })
    suppressCanvasClick.current = true
    svg.setPointerCapture(event.pointerId)
  }

  function finishDragging(event: React.PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    setDraggingIndex(null)
    setDraggingZone(null)
  }

  function resetEditor() {
    setPoints([])
    setForm(emptyForm)
    setEditingId(null)
    setError('')
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
    setMessage(`Editando ${zone.name}. Ajuste os pontos e salve.`)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!cameraId || points.length < 3) return
    setError('')
    const payload = { camera_id: cameraId, ...form, polygon: points }
    try {
      if (editingId) await api.updateZone(editingId, payload)
      else await api.createZone(payload)
      await refresh()
      setMessage(editingId ? 'Zona atualizada.' : 'Zona criada e monitoramento iniciado.')
      resetEditor()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível salvar a zona.')
    }
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">DETECÇÃO POR IA</p><h1>Zonas monitoradas</h1><p>Desenhe no vídeo a área que a IA deve acompanhar.</p></div></div>
    <section className="zone-workspace">
      <div className="zone-editor-panel">
        <div className="zone-toolbar">
          <label>Câmera<select value={cameraId} onChange={event => { setCameraId(event.target.value); resetEditor() }}><option value="">Selecione</option>{cameras.map(item => <option key={item.id} value={item.id}>{item.name} · {item.status.connected ? 'online' : 'offline'}</option>)}</select></label>
          <div><button className="secondary" type="button" disabled={!points.length} onClick={() => setPoints(current => current.slice(0, -1))}>Desfazer ponto</button><button className="ghost" type="button" disabled={!points.length} onClick={() => setPoints([])}>Limpar</button></div>
        </div>
        <div className={`zone-canvas ${camera?.status.connected ? '' : 'disabled'}`}>
          {camera?.status.connected
            ? <CameraVideo cameraId={camera.id} cameraName={camera.name} />
            : <div className="zone-video-empty"><strong>{camera ? 'Câmera offline' : 'Selecione uma câmera'}</strong><span>A câmera precisa estar conectada para desenhar a zona.</span></div>}
          {camera?.status.connected && <svg viewBox="0 0 100 100" preserveAspectRatio="none" onClick={addPoint} onPointerMove={movePoint} onPointerUp={finishDragging}>
            {cameraZones.filter(zone => zone.id !== editingId).map(zone => <polygon key={zone.id} className={`saved-zone ${zone.type.toLowerCase()} ${feedbackByZone.get(zone.id)?.inside ? 'detected' : ''}`} points={zone.polygon.map(point => `${point.x * 100},${point.y * 100}`).join(' ')} onPointerDown={event => startZoneDrag(event, zone.polygon, zone)} />)}
            {points.length >= 2 && <polyline className="draft-zone" points={points.map(point => `${point.x * 100},${point.y * 100}`).join(' ')} />}
            {points.length >= 3 && <polygon className="draft-fill" points={points.map(point => `${point.x * 100},${point.y * 100}`).join(' ')} onPointerDown={event => startZoneDrag(event, points)} />}
            {points.map((point, index) => <circle key={index} className="zone-handle" cx={point.x * 100} cy={point.y * 100} r="1.25" onPointerDown={event => { event.stopPropagation(); suppressCanvasClick.current = true; setDraggingZone(null); setDraggingIndex(index); event.currentTarget.ownerSVGElement?.setPointerCapture(event.pointerId) }} onClick={event => { event.stopPropagation(); suppressCanvasClick.current = false }} />)}
            {(feedback?.detections ?? []).map((detection, index) => <g key={index} className="ai-detection"><rect x={detection.x1 * 100} y={detection.y1 * 100} width={(detection.x2 - detection.x1) * 100} height={(detection.y2 - detection.y1) * 100} /><text x={detection.x1 * 100} y={Math.max(3, detection.y1 * 100 - 1)}>{detection.species === 'CAT' ? 'Gato' : 'Cão'} {Math.round(detection.confidence * 100)}%</text></g>)}
          </svg>}
          {camera?.status.connected && <div className={`ai-status ${feedback?.status === 'running' ? 'ready' : ''}`}><i />{feedback?.status === 'running' ? `IA ativa · ${feedback.detections.length} pet(s)` : feedback?.status === 'error' ? 'Falha na IA' : 'Iniciando IA'}</div>}
        </div>
        <p className="drawing-hint">Clique na imagem para adicionar os limites da zona. Use pelo menos três pontos.</p>
      </div>

      <aside className="zone-settings">
        <form className="panel stack-form" onSubmit={submit}>
          <div><p className="eyebrow">{editingId ? 'EDITAR ZONA' : 'NOVA ZONA'}</p><h2>{points.length < 3 ? 'Marque a área no vídeo' : 'Configure o monitoramento'}</h2></div>
          <label>Nome<input required value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Pote de água" /></label>
          <label>Tipo<select value={form.type} onChange={event => setForm({ ...form, type: event.target.value as Zone['type'] })}>{Object.entries(zoneLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <label>Permanência para confirmar<input type="number" min="0.5" max="300" step="0.5" value={form.minimum_presence_seconds} onChange={event => setForm({ ...form, minimum_presence_seconds: Number(event.target.value) })} /><small>Segundos que o pet precisa permanecer na área.</small></label>
          <div className="two-inputs"><label>Tolerância<input type="number" min="0" max="30" step="0.5" value={form.absence_tolerance_seconds} onChange={event => setForm({ ...form, absence_tolerance_seconds: Number(event.target.value) })} /></label><label>Cooldown<input type="number" min="0" max="3600" step="1" value={form.cooldown_seconds} onChange={event => setForm({ ...form, cooldown_seconds: Number(event.target.value) })} /></label></div>
          {error && <p className="form-error">{error}</p>}
          {message && <p className="form-success">{message}</p>}
          <button className="primary full" disabled={!camera?.status.connected || points.length < 3}>{editingId ? 'Salvar alterações' : 'Criar e monitorar zona'}</button>
          {editingId && <button className="ghost full" type="button" onClick={resetEditor}>Cancelar edição</button>}
        </form>
        <section className="panel zone-feedback"><div className="panel-head"><div><h2>Feedback ao vivo</h2><p>{cameraZones.length} zona(s) nesta câmera</p></div></div>{cameraZones.length ? <div className="zone-list">{cameraZones.map(zone => { const state = feedbackByZone.get(zone.id); return <div key={zone.id}><span className={`zone-dot ${zone.type.toLowerCase()} ${state?.inside ? 'pulse' : ''}`} /><div><strong>{zone.name}</strong><small>{state ? stateLabels[state.state] : 'Aguardando IA'}{state?.state === 'CANDIDATE' ? ` · ${Math.round(state.progress * 100)}%` : ''}</small></div><div className="zone-actions"><button className="ghost" onClick={() => editZone(zone)}>Editar</button><button className="ghost danger" onClick={async () => { await api.deleteZone(zone.id); await refresh() }}>Remover</button></div></div>})}</div> : <p className="muted">Desenhe a primeira zona nesta câmera.</p>}</section>
      </aside>
    </section>
  </>
}
