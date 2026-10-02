import { FormEvent, ReactNode, useEffect, useState } from 'react'
import * as api from './api'
import type { Camera, CameraCandidate, Dashboard, Event, Zone } from './api'

type View = 'dashboard' | 'cameras' | 'zones' | 'history' | 'reviews' | 'settings'

const labels: Record<View, string> = {
  dashboard: 'Visão geral', cameras: 'Câmeras', zones: 'Zonas', history: 'Histórico',
  reviews: 'Revisões', settings: 'Configurações',
}

const zoneLabels: Record<string, string> = {
  FOOD: 'Comida', WATER: 'Água', LITTER: 'Caixa de areia', CUSTOM: 'Personalizada',
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty"><span className="empty-icon">◇</span><h3>{title}</h3><p>{children}</p></div>
}

function Status({ connected }: { connected: boolean }) {
  return <span className={`status ${connected ? 'online' : ''}`}><i />{connected ? 'Online' : 'Offline'}</span>
}

function EventList({ events }: { events: Event[] }) {
  if (!events.length) return <Empty title="Nenhuma visita registrada">Os eventos aparecerão quando o monitoramento detectar um gato em uma zona.</Empty>
  return <div className="event-list">{events.map(event => <article className="event-row" key={event.id}>
    <div className={`event-kind ${event.zone_type.toLowerCase()}`}>{event.zone_type === 'WATER' ? '◉' : event.zone_type === 'FOOD' ? '●' : '◆'}</div>
    <div><strong>{zoneLabels[event.zone_type] ?? event.zone_name}</strong><span>{event.camera_name} · {new Date(event.started_at).toLocaleString('pt-BR')}</span></div>
    <div className="event-meta"><strong>{Math.round(event.duration_seconds)}s</strong><span>{event.review_decision ? 'Revisado' : 'Pendente'}</span></div>
  </article>)}</div>
}

function DashboardView({ data }: { data: Dashboard | null }) {
  if (!data) return <div className="loading">Carregando resumo…</div>
  const totalCameras = data.health.cameras.registered
  return <>
    <div className="page-heading"><div><p className="eyebrow">HOJE</p><h1>Olá! Como estão seus gatos?</h1><p>Acompanhe as visitas detectadas nas áreas importantes da casa.</p></div><span className="date-pill">{new Date(`${data.date}T12:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'long' })}</span></div>
    <section className="metrics">
      <article><span>Visitas hoje</span><strong>{data.events_today}</strong><small>eventos confirmados</small></article>
      <article><span>Água</span><strong>{data.by_zone_type.WATER ?? 0}</strong><small>visitas à zona</small></article>
      <article><span>Comida</span><strong>{data.by_zone_type.FOOD ?? 0}</strong><small>visitas à zona</small></article>
      <article><span>Câmeras</span><strong>{data.health.cameras.connected}/{totalCameras}</strong><small>conectadas agora</small></article>
    </section>
    {totalCameras === 0 && <section className="welcome-banner"><div><span className="eyebrow">PRIMEIROS PASSOS</span><h2>Configure sua primeira câmera</h2><p>Cadastre uma câmera IP e depois marque as zonas que deseja acompanhar.</p></div><span className="step-count">1 de 2</span></section>}
    <section className="panel"><div className="panel-head"><div><h2>Atividade recente</h2><p>Últimas visitas detectadas nas zonas configuradas.</p></div>{data.pending_reviews > 0 && <span className="review-count">{data.pending_reviews} para revisar</span>}</div><EventList events={data.recent_events} /></section>
  </>
}

function CamerasView({ cameras, refresh }: { cameras: Camera[]; refresh: () => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [candidates, setCandidates] = useState<CameraCandidate[]>([])
  const [form, setForm] = useState({ name: '', ip: '', username: '', password: '', rtsp_url: '' })
  const [error, setError] = useState('')

  async function discover() {
    setDiscovering(true); setError('')
    try {
      let found = await api.discoverCameras()
      if (!found.length) found = await api.discoverCameras(true)
      setCandidates(found)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Falha na descoberta.') }
    finally { setDiscovering(false) }
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setError('')
    try {
      await api.createCamera({ ...form, rtsp_url: form.rtsp_url || null })
      setOpen(false); setForm({ name: '', ip: '', username: '', password: '', rtsp_url: '' }); await refresh()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Falha ao cadastrar.') }
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">MONITORAMENTO</p><h1>Câmeras</h1><p>Gerencie as fontes de vídeo usadas pelo MonitoraPet.</p></div><button className="primary" onClick={() => setOpen(true)}>+ Adicionar câmera</button></div>
    <section className="camera-grid">{cameras.map(camera => <article className="camera-card" key={camera.id}>
      <div className="preview">{camera.status.connected ? <img src={`/api/cameras/${camera.id}/video`} alt={`Vídeo de ${camera.name}`} /> : <span>Sem sinal</span>}<Status connected={camera.status.connected} /></div>
      <div className="camera-info"><div><h3>{camera.name}</h3><p>{camera.model || camera.manufacturer || 'Câmera IP'} · {camera.ip}</p></div><button className="ghost danger" onClick={async () => { await api.deleteCamera(camera.id); await refresh() }}>Remover</button></div>
    </article>)}</section>
    {!cameras.length && <section className="panel"><Empty title="Nenhuma câmera cadastrada">Adicione até duas câmeras IP para começar o monitoramento local.</Empty></section>}
    {open && <div className="modal-backdrop"><form className="modal" onSubmit={submit}><div className="panel-head"><div><p className="eyebrow">NOVA CÂMERA</p><h2>Conectar câmera IP</h2></div><button type="button" className="close" onClick={() => setOpen(false)}>×</button></div>
      <button type="button" className="secondary full" onClick={discover} disabled={discovering}>{discovering ? 'Procurando na rede…' : 'Localizar automaticamente'}</button>
      {candidates.length > 0 && <div className="candidate-list">{candidates.map(item => <button type="button" key={item.ip} onClick={() => setForm(value => ({ ...value, ip: item.ip, name: item.name }))}><strong>{item.name}</strong><span>{item.ip}</span></button>)}</div>}
      <div className="form-grid"><label>Nome<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Ex.: Sala" /></label><label>Endereço IP<input required value={form.ip} onChange={e => setForm({ ...form, ip: e.target.value })} placeholder="192.168.1.100" /></label><label>Usuário<input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} autoComplete="username" /></label><label>Senha<input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} autoComplete="current-password" /></label><label className="wide">URL RTSP opcional<input value={form.rtsp_url} onChange={e => setForm({ ...form, rtsp_url: e.target.value })} placeholder="rtsp://192.168.1.100:554/stream" /></label></div>
      {error && <p className="form-error">{error}</p>}<button className="primary full" type="submit">Cadastrar câmera</button>
    </form></div>}
  </>
}

function ZonesView({ cameras, zones, refresh }: { cameras: Camera[]; zones: Zone[]; refresh: () => Promise<void> }) {
  const [form, setForm] = useState({ camera_id: '', name: '', type: 'FOOD' as Zone['type'], minimum_presence_seconds: 3 })
  async function submit(event: FormEvent) {
    event.preventDefault()
    await api.createZone({ ...form, polygon: [{ x: .2, y: .2 }, { x: .8, y: .2 }, { x: .8, y: .8 }, { x: .2, y: .8 }] })
    setForm({ camera_id: '', name: '', type: 'FOOD', minimum_presence_seconds: 3 }); await refresh()
  }
  return <><div className="page-heading"><div><p className="eyebrow">DETECÇÃO</p><h1>Zonas monitoradas</h1><p>Defina as áreas de comida, água e caixa de areia.</p></div></div>
    <div className="split"><section className="panel"><h2>Nova zona</h2><p className="muted">O editor visual será habilitado quando a câmera estiver online. Por enquanto, a área central é usada como base.</p><form onSubmit={submit} className="stack-form"><label>Câmera<select required value={form.camera_id} onChange={e => setForm({ ...form, camera_id: e.target.value })}><option value="">Selecione</option>{cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label><label>Nome<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Ex.: Pote de água" /></label><label>Tipo<select value={form.type} onChange={e => setForm({ ...form, type: e.target.value as Zone['type'] })}>{Object.entries(zoneLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>Permanência mínima<input type="number" min="0.5" step="0.5" value={form.minimum_presence_seconds} onChange={e => setForm({ ...form, minimum_presence_seconds: Number(e.target.value) })} /></label><button className="primary" disabled={!cameras.length}>Criar zona</button></form></section>
      <section className="panel"><div className="panel-head"><div><h2>Zonas configuradas</h2><p>{zones.length} no total</p></div></div>{zones.length ? <div className="zone-list">{zones.map(zone => <div key={zone.id}><span className={`zone-dot ${zone.type.toLowerCase()}`} /><div><strong>{zone.name}</strong><small>{zoneLabels[zone.type]} · {zone.minimum_presence_seconds}s</small></div><button className="ghost danger" onClick={async () => { await api.deleteZone(zone.id); await refresh() }}>Remover</button></div>)}</div> : <Empty title="Nenhuma zona">Cadastre uma câmera e crie a primeira área de monitoramento.</Empty>}</section></div>
  </>
}

function ReviewsView({ events, refresh }: { events: Event[]; refresh: () => Promise<void> }) {
  const current = events[0]
  if (!current) return <><div className="page-heading"><div><p className="eyebrow">AUDITORIA</p><h1>Revisões</h1><p>Confirme ou corrija as classificações automáticas.</p></div></div><section className="panel"><Empty title="Tudo revisado">Não há eventos pendentes na fila.</Empty></section></>
  const review = async (decision: string) => { await api.reviewEvent(current.id, decision); await refresh() }
  return <><div className="page-heading"><div><p className="eyebrow">AUDITORIA</p><h1>Revisões</h1><p>{events.length} eventos aguardando sua análise.</p></div></div><section className="review-card"><div className="review-media">Clipe indisponível</div><div className="review-detail"><span className="eyebrow">EVENTO DETECTADO</span><h2>{zoneLabels[current.zone_type]}</h2><p>{current.camera_name} · {new Date(current.started_at).toLocaleString('pt-BR')}</p><div className="review-actions"><button onClick={() => review('CONFIRMED')} className="primary">Confirmar</button><button onClick={() => review('CORRECTED')} className="secondary">Corrigir</button><button onClick={() => review('INCONCLUSIVE')} className="secondary">Inconclusivo</button><button onClick={() => review('FALSE_POSITIVE')} className="ghost danger">Falso positivo</button></div></div></section></>
}

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [pending, setPending] = useState<Event[]>([])
  const [error, setError] = useState('')

  async function refresh() {
    try {
      const [summary, cameraList, zoneList, eventList, pendingList] = await Promise.all([api.getDashboard(), api.getCameras(), api.getZones(), api.getEvents(), api.getEvents(true)])
      setDashboard(summary); setCameras(cameraList); setZones(zoneList); setEvents(eventList); setPending(pendingList); setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Não foi possível carregar o MonitoraPet.') }
  }
  useEffect(() => { void refresh() }, [])

  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">M</span><div><strong>MonitoraPet</strong><small>Monitoramento local</small></div></div><nav>{(Object.keys(labels) as View[]).map(item => <button key={item} className={view === item ? 'active' : ''} onClick={() => setView(item)}><span>{item === 'dashboard' ? '⌂' : item === 'cameras' ? '◉' : item === 'zones' ? '◇' : item === 'history' ? '≡' : item === 'reviews' ? '✓' : '⚙'}</span>{labels[item]}{item === 'reviews' && pending.length > 0 && <b>{pending.length}</b>}</button>)}</nav><div className="local-note"><i>●</i><div><strong>100% local</strong><small>Seus dados ficam neste computador.</small></div></div></aside>
    <main className="content">{error && <div className="global-error">{error}<button onClick={refresh}>Tentar novamente</button></div>}{view === 'dashboard' && <DashboardView data={dashboard} />}{view === 'cameras' && <CamerasView cameras={cameras} refresh={refresh} />}{view === 'zones' && <ZonesView cameras={cameras} zones={zones} refresh={refresh} />}{view === 'history' && <><div className="page-heading"><div><p className="eyebrow">REGISTROS</p><h1>Histórico</h1><p>Consulte as visitas detectadas pelo sistema.</p></div></div><section className="panel"><EventList events={events} /></section></>}{view === 'reviews' && <ReviewsView events={pending} refresh={refresh} />}{view === 'settings' && <><div className="page-heading"><div><p className="eyebrow">SISTEMA</p><h1>Configurações</h1><p>Preferências do monitoramento local.</p></div></div><section className="panel settings"><h2>Privacidade</h2><p>O processamento acontece localmente. Nenhuma imagem ou credencial é enviada para serviços externos.</p><h2>Versão</h2><p>MonitoraPet {dashboard?.health.version ?? '0.1.0'}</p></section></>}</main>
  </div>
}
