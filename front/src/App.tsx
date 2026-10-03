import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react'
import * as api from './api'
import type { Camera, CameraCandidate, Dashboard, Event, EventPage, Pet, Zone } from './api'
import ZoneEditor from './components/ZoneEditor'
import PetManager from './components/PetManager'
import Icon from './components/Icon'
import { useToast } from './components/Toast'

type View = 'dashboard' | 'cameras' | 'zones' | 'pets' | 'history' | 'reviews' | 'settings'

const labels: Record<View, string> = {
  dashboard: 'Hoje', cameras: 'Câmeras', zones: 'Áreas monitoradas', pets: 'Pets', history: 'Histórico',
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

function HistoryView({
  pets, result, page, petId, zoneType, loading, onPage, onPet, onZone,
}: {
  pets: Pet[]; result: EventPage | null; page: number; petId: string; zoneType: Zone['type'] | '';
  loading: boolean; onPage: (page: number) => void; onPet: (id: string) => void; onZone: (type: Zone['type'] | '') => void
}) {
  const total = result?.total ?? 0
  const pageSize = result?.page_size ?? 10
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const start = total ? (page - 1) * pageSize + 1 : 0
  const end = Math.min(page * pageSize, total)
  const pages = Array.from({ length: pageCount }, (_, index) => index + 1)
    .filter(value => value === 1 || value === pageCount || Math.abs(value - page) <= 1)

  return <>
    <div className="page-heading"><div><p className="eyebrow">REGISTROS</p><h1>Histórico</h1><p>Consulte as visitas detectadas pelo sistema.</p></div></div>
    <section className="history-filter-panel" aria-label="Filtros do histórico">
      <div className="filter-chip-row"><span className="filter-chip-label">Pet</span><div className="filter-chip-options" role="group" aria-label="Filtrar por pet">
        {[{ id: '', name: 'Todos os pets' }, ...pets].map(pet => <button key={pet.id || 'all'} className={petId === pet.id ? 'selected' : ''} aria-pressed={petId === pet.id} onClick={() => onPet(pet.id)}>{pet.name}</button>)}
      </div></div>
      <div className="filter-chip-row"><span className="filter-chip-label">Área</span><div className="filter-chip-options" role="group" aria-label="Filtrar por área">
        {([['', 'Todas as áreas'], ...Object.entries(zoneLabels)] as [string, string][]).map(([value, label]) => <button key={value || 'all'} className={zoneType === value ? 'selected' : ''} aria-pressed={zoneType === value} onClick={() => onZone(value as Zone['type'] | '')}>{value && <Icon name={value === 'WATER' ? 'water' : value === 'FOOD' ? 'food' : value === 'LITTER' ? 'litter' : 'zones'} />} {label}</button>)}
      </div></div>
    </section>
    <section className="panel"><div className="panel-head"><h2>{total} registros</h2><span className="muted">Todos os períodos</span></div>
      {loading && !result ? <p className="loading">Carregando histórico…</p> : <EventList events={result?.events ?? []} />}
      {total > 0 && <div className="history-pagination"><p className="pagination-summary" aria-live="polite">Mostrando <strong>{start}–{end}</strong> de <strong>{total}</strong> registros</p><nav className="pagination-controls" aria-label="Páginas do histórico">
        <button className="secondary" disabled={page <= 1 || loading} onClick={() => onPage(page - 1)}>Anterior</button>
        {pages.map((value, index) => <span className="pagination-item" key={value}>{index > 0 && value - pages[index - 1] > 1 && <span className="pagination-ellipsis" aria-hidden="true">…</span>}<button className="pagination-number" aria-label={`Página ${value}`} aria-current={value === page ? 'page' : undefined} disabled={loading} onClick={() => onPage(value)}>{value}</button></span>)}
        <button className="secondary" disabled={page >= pageCount || loading} onClick={() => onPage(page + 1)}>Próxima</button>
      </nav></div>}
    </section>
  </>
}

function EventList({ events }: { events: Event[] }) {
  const [detail,setDetail]=useState<Event|null>(null)
  useEffect(()=>{const close=(e:KeyboardEvent)=>{if(e.key==='Escape')setDetail(null)};window.addEventListener('keydown',close);return ()=>window.removeEventListener('keydown',close)},[])
  if (!events.length) return <Empty title="Nenhuma visita registrada">Os eventos aparecerão quando o monitoramento detectar um pet em uma zona.</Empty>
  return <><div className="event-list">{events.map(event => <button className="event-row" key={event.id} onClick={()=>setDetail(event)}>
    <div className={`event-kind ${event.zone_type.toLowerCase()}`}><Icon name={event.zone_type==='WATER'?'water':event.zone_type==='FOOD'?'food':'litter'}/></div>
    <div><strong>{event.pet_name ? `${event.pet_name} · ` : 'Pet não identificado · '}{zoneLabels[event.zone_type] ?? event.zone_name}</strong><span>{event.camera_name} · {new Date(event.started_at).toLocaleString('pt-BR')}</span></div>
    <div className="event-meta"><strong>{Math.round(event.duration_seconds)}s</strong><span className={!event.review_decision?'pending':''}>{event.review_decision==='FALSE_POSITIVE'?'Descartado':event.review_decision==='INCONCLUSIVE'?'Inconclusivo':event.review_decision ? 'Revisado' : 'A revisar'}</span></div>
  </button>)}</div>{detail&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Detalhes do registro"><section className="modal event-detail-modal"><div className="panel-head"><h2>Detalhes da visita</h2><button className="close" aria-label="Fechar detalhes" onClick={()=>setDetail(null)}>×</button></div>{detail.clip_path ? <video className="event-detail-photo" controls preload="metadata" poster={detail.snapshot_path ? `/api/events/${detail.id}/snapshot` : undefined}><source src={`/api/events/${detail.id}/clip`} type="video/webm" /></video> : detail.snapshot_path ? <img className="event-detail-photo" src={`/api/events/${detail.id}/snapshot`} alt={`Evidência de ${detail.zone_name}`} /> : <p className="muted">Não há imagem disponível para este registro.</p>}<h3>{detail.pet_name??'Pet não identificado'} · {zoneLabels[detail.zone_type]}</h3><p>{detail.camera_name} · {new Date(detail.started_at).toLocaleString('pt-BR')}</p><div className="detail-metrics"><div><span>Permanência</span><strong>{Math.round(detail.duration_seconds)}s</strong></div><div><span>Detecção</span><strong>{Math.round((detail.confidence??0)*100)}%</strong></div><div><span>Revisão</span><strong>{detail.review_decision==='FALSE_POSITIVE'?'Recusada':detail.review_decision?'Concluída':'Pendente'}</strong></div></div><button className="secondary full" onClick={()=>setDetail(null)}>Fechar registro</button></section></div>}</>
}

function DashboardView({ data, pets, cameras, events, onNavigate }: { data: Dashboard | null; pets: Pet[]; cameras: Camera[]; events: Event[]; onNavigate: (view: View) => void }) {
  const [petId, setPetId] = useState('')
  if (!data) return <div className="loading">Carregando a rotina dos pets…</div>
  const filtered = events.filter(e => e.review_decision !== 'FALSE_POSITIVE' && (!petId || e.pet_id === petId))
  const selected = pets.find(p => p.id === petId)
  const byType = selected ? Object.fromEntries(['FOOD','WATER','LITTER'].map(t => [t,filtered.filter(e=>e.zone_type===t).length])) : data.by_zone_type
  return <>
    <div className="page-heading"><div><div className="eyebrow">UM OLHAR SOBRE A ROTINA</div><h1>O dia dos seus pets<span className="heading-dot">.</span></h1><p>Pequenas visitas. Um acompanhamento mais próximo.</p></div><span className="date-pill"><Icon name="calendar" />{new Date().toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}</span></div>
    <div className="pet-selector" role="group" aria-label="Filtrar por pet"><button className={!petId?'selected':''} onClick={()=>setPetId('')}><span className="all-pets"><Icon name="pets" /></span>Todos os pets</button>{pets.map(p=><button className={petId===p.id?'selected':''} key={p.id} onClick={()=>setPetId(p.id)}>{p.photo_path?<img src={`/api/pets/${p.id}/photo`} alt=""/>:<span className="pet-initial">{p.name[0]}</span>}{p.name}</button>)}<button className="manage-pets" onClick={()=>onNavigate('pets')}>Gerenciar pets</button></div>
    {petId && <p className="filter-note">Resumo das visitas identificadas de {selected?.name}. Registros sem identificação ficam em Todos os pets.</p>}
    <section className="metrics">{[{type:'WATER',title:'Água',icon:'water',class:'water',sub:'visitas ao bebedouro'},{type:'FOOD',title:'Comida',icon:'food',class:'food',sub:'visitas ao comedouro'},{type:'LITTER',title:'Caixa de areia',icon:'litter',class:'litter',sub:'visitas à caixa'}].map(m=><article key={m.type} className={m.class}><div className="metric-label"><span>{m.title}</span><span className="metric-icon"><Icon name={m.icon}/></span></div><div className="metric-number">{byType[m.type]??0}<span>visitas</span></div><small>{m.sub}</small></article>)}<article className="total"><div className="metric-label"><span>Atividade do dia</span><span className="metric-icon"><Icon name="activity"/></span></div><div className="metric-number">{petId?filtered.length:data.events_today}<span>registros</span></div><small>{petId?'registros identificados hoje':'em todas as áreas'}</small></article></section>
    <p className="observation-note"><Icon name="info"/>Uma visita à área não confirma ingestão de água, alimentação ou uso da caixa.</p>
    <div className="dashboard-layout"><div className="dashboard-main">
      <section className="panel activity-panel"><div className="panel-head"><div><h2>Últimas visitas</h2><p>O que aconteceu nas áreas monitoradas.</p></div><button className="text-button" onClick={()=>onNavigate('history')}>Ver histórico</button></div><EventList events={filtered.slice(0,5)}/><div className="panel-foot"><Icon name="clock"/>Horários apresentados no seu fuso local</div></section>
      <section className="review-banner"><div className="review-banner-icon"><Icon name="reviews"/></div><div><h3>{data.pending_reviews?'Um olhar seu faz a diferença':'Tudo revisado por aqui'}</h3><p>{data.pending_reviews?`${data.pending_reviews} registros precisam de confirmação ou identificação do pet.`:'As próximas detecções aparecerão aqui para você conferir.'}</p></div><button className="secondary" onClick={()=>onNavigate('reviews')}>{data.pending_reviews?'Revisar registros':'Ver revisões'}{data.pending_reviews>0&&<b>{data.pending_reviews}</b>}</button></section>
    </div><aside className="dashboard-aside"><section className="panel camera-summary"><div className="panel-head"><h2>Suas câmeras</h2><button className="icon-button" title="Gerenciar câmeras" onClick={()=>onNavigate('cameras')}><Icon name="settings"/></button></div>{cameras.find(camera=>camera.status.connected) ? <div className="camera-still"><img src={`/api/cameras/${cameras.find(camera=>camera.status.connected)!.id}/video`} alt={`Vídeo ao vivo de ${cameras.find(camera=>camera.status.connected)!.name}`}/><span>AO VIVO</span><div className="still-caption"><Icon name="camera"/>{cameras.find(camera=>camera.status.connected)!.name}</div></div> : <div className="camera-still camera-still-empty">{cameras.length ? 'Nenhuma câmera conectada' : 'Nenhuma câmera cadastrada'}</div>}<div className="camera-summary-list">{cameras.map(c=><button key={c.id} onClick={()=>onNavigate('cameras')}><div><Icon name="camera"/><span><strong>{c.name}</strong><small>{c.status.connected?'Conectada':'Conexão interrompida'}</small></span></div><span className={c.status.connected?'camera-state online':'camera-state offline'}>{c.status.connected?'Online':'Offline'}</span></button>)}</div><button className="secondary full" onClick={()=>onNavigate('cameras')}>Abrir câmeras</button></section><div className="privacy-card"><Icon name="shield"/><div><strong>Dentro de casa. Dentro da sua rede.</strong><p>Todos os dados são armazenados localmente.</p></div></div></aside></div>
  </>
}

function CamerasView({ cameras, zones, refresh }: { cameras: Camera[]; zones: Zone[]; refresh: () => Promise<void> }) {
  const showToast = useToast()
  const [open, setOpen] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [candidates, setCandidates] = useState<CameraCandidate[]>([])
  const [form, setForm] = useState({ name: '', ip: '', username: '', password: '', rtsp_url: '' })
  const [reconnectCamera, setReconnectCamera] = useState<Camera | null>(null)
  const [credentials, setCredentials] = useState({ username: '', password: '', rtsp_url: '' })
  const [error, setError] = useState('')
  const [zoneOverlays, setZoneOverlays] = useState<string[]>([])
  useEffect(()=>{const close=(e:KeyboardEvent)=>{if(e.key==='Escape'){setOpen(false);setReconnectCamera(null)}};window.addEventListener('keydown',close);return ()=>window.removeEventListener('keydown',close)},[])

  function toggleZoneOverlay(cameraId: string) {
    setZoneOverlays(current => current.includes(cameraId) ? current.filter(id => id !== cameraId) : [...current, cameraId])
  }

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
      setOpen(false); setForm({ name: '', ip: '', username: '', password: '', rtsp_url: '' }); await refresh(); showToast('Câmera cadastrada.')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Falha ao cadastrar.') }
  }

  async function reconnect(event: FormEvent) {
    event.preventDefault()
    if (!reconnectCamera) return
    setError('')
    try {
      await api.connectCamera(reconnectCamera.id, { ...credentials, rtsp_url: credentials.rtsp_url || null })
      setReconnectCamera(null)
      setCredentials({ username: '', password: '', rtsp_url: '' })
      await refresh()
      showToast(`${reconnectCamera.name} conectada.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível conectar a câmera.')
    }
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">MONITORAMENTO</p><h1>Câmeras</h1><p>Gerencie as fontes de vídeo usadas pelo MonitoraPet.</p></div><button className="primary" onClick={() => setOpen(true)}>+ Adicionar câmera</button></div>
    <section className="camera-grid">{cameras.map(camera => {
      const cameraZones = zones.filter(zone => zone.camera_id === camera.id && zone.enabled)
      const showZones = zoneOverlays.includes(camera.id)
      return <article className="camera-card" key={camera.id}>
        <div className="preview">
          {camera.status.connected ? <img src={`/api/cameras/${camera.id}/video`} alt={`Vídeo ao vivo de ${camera.name}`} /> : <div className="offline-message"><Icon name="camera"/><strong>Câmera desconectada</strong><p>Reconecte para continuar acompanhando esta área.</p></div>}
          {showZones && <div className="camera-zone-overlay">{cameraZones.map(zone => {
            const center = zone.polygon.reduce((value, point) => ({ x: value.x + point.x / zone.polygon.length, y: value.y + point.y / zone.polygon.length }), { x: 0, y: 0 })
            return <div className={`camera-zone ${zone.type.toLowerCase()}`} key={zone.id}>
              <svg viewBox="0 0 100 100" preserveAspectRatio="none"><polygon points={zone.polygon.map(point => `${point.x * 100},${point.y * 100}`).join(' ')} /></svg>
              <span style={{ left: `${center.x * 100}%`, top: `${center.y * 100}%` }}>{zone.name}</span>
            </div>
          })}</div>}
          <Status connected={camera.status.connected} />
        </div>
        <div className="camera-info"><div><h3>{camera.name}</h3><p>{camera.model || camera.manufacturer || 'Câmera IP'} · {camera.ip}</p></div><div className="camera-actions">{cameraZones.length > 0 && <button className={`tertiary zone-toggle ${showZones ? 'active' : ''}`} onClick={() => toggleZoneOverlay(camera.id)}>{showZones ? 'Ocultar zonas' : `Mostrar zonas (${cameraZones.length})`}</button>}{!camera.status.connected && <button className="tertiary" onClick={() => { setReconnectCamera(camera); setError('') }}>Conectar</button>}<button className="tertiary danger" onClick={async () => { if(window.confirm(`Remover a câmera ${camera.name} e suas áreas?`)){await api.deleteCamera(camera.id); await refresh(); showToast(`Câmera ${camera.name} removida.`)} }}>Remover</button></div></div>
      </article>
    })}</section>
    {!cameras.length && <section className="panel"><Empty title="Nenhuma câmera cadastrada">Adicione até duas câmeras IP para começar o monitoramento local.</Empty></section>}
    {open && <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Configurar câmera"><form className="modal" onSubmit={submit}><div className="panel-head"><div><p className="eyebrow">NOVA CÂMERA</p><h2>Conectar câmera IP</h2></div><button type="button" className="close" aria-label="Fechar" onClick={() => setOpen(false)}>×</button></div>
      <button type="button" className="secondary full" onClick={discover} disabled={discovering}>{discovering ? 'Procurando na rede…' : 'Localizar automaticamente'}</button>
      {candidates.length > 0 && <div className="candidate-list">{candidates.map(item => <button type="button" key={item.ip} onClick={() => setForm(value => ({ ...value, ip: item.ip, name: item.name }))}><span><strong>{item.name}</strong><small>{[item.manufacturer, item.model].filter(Boolean).join(' · ') || item.reason || 'Dispositivo ONVIF'}</small></span><span>{item.ip}</span></button>)}</div>}
      <div className="form-grid"><label>Nome<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Ex.: Sala" /></label><label>Endereço IP<input required value={form.ip} onChange={e => setForm({ ...form, ip: e.target.value })} placeholder="192.168.1.100" /></label><label>Usuário<input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} autoComplete="username" /></label><label>Senha<input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} autoComplete="current-password" /></label><label className="wide">URL RTSP opcional<input value={form.rtsp_url} onChange={e => setForm({ ...form, rtsp_url: e.target.value })} placeholder="rtsp://192.168.1.100:554/stream" /></label></div>
      {error && <p className="form-error">{error}</p>}<button className="primary full" type="submit">Cadastrar câmera</button>
    </form></div>}
    {reconnectCamera && <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Configurar câmera"><form className="modal compact-modal" onSubmit={reconnect}><div className="panel-head"><div><p className="eyebrow">RECONECTAR</p><h2>{reconnectCamera.name}</h2><p>{reconnectCamera.ip}</p></div><button type="button" className="close" aria-label="Fechar" onClick={() => setReconnectCamera(null)}>×</button></div><div className="form-grid"><label>Usuário<input value={credentials.username} onChange={event => setCredentials({ ...credentials, username: event.target.value })} autoComplete="username" /></label><label>Senha<input type="password" value={credentials.password} onChange={event => setCredentials({ ...credentials, password: event.target.value })} autoComplete="current-password" /></label><label className="wide">URL RTSP opcional<input value={credentials.rtsp_url} onChange={event => setCredentials({ ...credentials, rtsp_url: event.target.value })} placeholder="Use somente se a descoberta automática falhar" /></label></div>{error && <p className="form-error">{error}</p>}<button className="primary full">Conectar câmera</button></form></div>}
  </>
}

function ReviewsView({ events, pets, refresh }: { events: Event[]; pets: Pet[]; refresh: () => Promise<void> }) {
  const showToast = useToast()
  const current = events[0]
  const [decision, setDecision] = useState<'accept' | 'reject' | 'correct' | ''>('')
  const [stage,setStage] = useState<'validate'|'type'|'pet'>('validate')
  const stageHeading = useRef<HTMLHeadingElement>(null)
  const [correctedType, setCorrectedType] = useState<Zone['type'] | ''>('')
  const [petId, setPetId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { setDecision('');setStage('validate');setCorrectedType('');setPetId(current?.pet_id ?? '');setError('') }, [current?.id])
  const compatiblePets = pets.filter(pet => pet.species === current?.detected_species)
  useEffect(()=>{stageHeading.current?.focus()},[stage])
  const validPet = petId==='unknown'||compatiblePets.some(p=>p.id===petId)
  const canSave = decision==='reject' || (stage==='pet'&&validPet&&(decision!=='correct'||(!!correctedType&&correctedType!==current?.zone_type)))
  async function saveReview() {
    if (!current || !canSave || saving) return
    setSaving(true);setError('')
    try {
      const apiDecision = decision === 'reject' ? 'FALSE_POSITIVE' : decision === 'correct' ? 'CORRECTED' : 'CONFIRMED'
      await api.reviewEvent(current.id, apiDecision, decision === 'reject' || petId==='unknown' ? null : petId || null, decision === 'correct' && correctedType ? correctedType : undefined)
      await refresh()
      showToast(decision === 'reject' ? 'Evidência recusada.' : decision === 'correct' ? `Tipo corrigido para ${zoneLabels[correctedType].toLowerCase()}.` : 'Evidência aceita.')
    } catch(reason) { setError(reason instanceof Error ? reason.message : 'Não foi possível salvar. Tente novamente.') }
    finally { setSaving(false) }
  }
  function chooseDecision(value: 'accept' | 'reject' | 'correct') { setDecision(value);setError('');setStage(value==='accept'?'pet':value==='correct'?'type':'validate') }
  return <>
    <div className="page-heading"><div><p className="eyebrow">REGISTROS PARA CONFERIR</p><h1>Revisões</h1><p>{events.length ? `${events.length} ${events.length === 1 ? 'registro aguardando' : 'registros aguardando'} revisão.` : 'Nenhum registro pendente.'}</p></div></div>
    {!current ? <section className="panel"><Empty title="Tudo revisado">Novos registros aparecerão aqui quando uma visita for detectada.</Empty></section> : <section className="review-card review-flow">
      <div className="review-evidence"><div className="review-step-heading"><span>1</span><h2>Confira a evidência</h2></div><div className="review-media">{current.clip_path ? <video key={current.id} controls preload="metadata" poster={current.snapshot_path ? `/api/events/${current.id}/snapshot` : undefined}><source src={`/api/events/${current.id}/clip`} type="video/webm"/>Seu navegador não conseguiu reproduzir este vídeo.</video> : current.snapshot_path ? <div className="review-snapshot"><img src={`/api/events/${current.id}/snapshot`} alt={`Evidência de uma visita à área ${current.zone_name}`}/></div> : <p>Mídia indisponível para este registro.</p>}</div><div className="review-record-details"><div><strong>{zoneLabels[current.zone_type]}</strong><p>{current.camera_name} · {new Date(current.started_at).toLocaleString('pt-BR')}</p></div><span>{current.duration_seconds ? `${Math.round(current.duration_seconds)}s na área` : 'Em andamento'}</span></div></div>
      <div className="review-detail review-wizard"><div className="review-step-heading"><span>{stage==='validate'?2:stage==='type'||decision==='accept'?3:4}</span><h2 ref={stageHeading} tabIndex={-1}>{stage==='validate'?'A evidência está correta?':stage==='type'?'Qual é o tipo correto?':'Qual animal aparece?'}</h2></div>
        {stage==='validate' && <><div className="evidence-actions">{([{value:'accept',icon:'accept',title:'Aceitar',description:`É uma visita à área de ${zoneLabels[current.zone_type].toLowerCase()}.`},{value:'correct',icon:'correct',title:'Corrigir tipo',description:'A visita é válida, mas o tipo está errado.'},{value:'reject',icon:'reject',title:'Recusar',description:'A imagem não comprova uma visita à área.'}] as const).map(option=><button type="button" className={`evidence-action evidence-action-${option.value} ${decision===option.value?'chosen':''}`} key={option.value} disabled={saving} onClick={()=>chooseDecision(option.value)}><span className="evidence-action-icon"><Icon name={option.icon}/></span><span className="evidence-action-copy"><strong>{option.title}</strong><span>{option.description}</span></span></button>)}</div>{decision==='reject'&&<div className="review-save"><p className="review-save-hint">A evidência ficará no histórico como recusada e não entrará no resumo de visitas.</p>{error&&<p className="form-error" role="alert">{error}</p>}<button className="primary full" disabled={saving} onClick={()=>void saveReview()}>{saving?'Salvando…':'Confirmar recusa'}</button></div>}</>}
        {stage==='type' && <><p className="wizard-context">Tipo detectado: <strong>{zoneLabels[current.zone_type]}</strong></p><fieldset className="review-type-options" disabled={saving}><legend className="sr-only">Novo tipo da evidência</legend><div>{(['WATER','FOOD','LITTER'] as const).map(type=><label key={type} className={`${correctedType===type?'chosen':''} ${current.zone_type===type?'current-type':''}`}><input type="radio" name="corrected-evidence-type" value={type} disabled={current.zone_type===type} checked={correctedType===type} onChange={()=>setCorrectedType(type)}/><Icon name={type==='WATER'?'water':type==='FOOD'?'food':'litter'}/><span>{zoneLabels[type]}{current.zone_type===type&&<small>Tipo atual</small>}</span></label>)}</div></fieldset><div className="review-save"><button className="primary full" disabled={!correctedType||correctedType===current.zone_type} onClick={()=>setStage('pet')}>Continuar</button><button className="tertiary full" onClick={()=>{setStage('validate');setDecision('')}}>Voltar</button></div></>}
        {stage==='pet' && <><p className="wizard-context">Visita à área de <strong>{zoneLabels[decision==='correct'&&correctedType?correctedType:current.zone_type].toLowerCase()}</strong>{decision==='correct'&&' · tipo corrigido'}</p><fieldset className="review-pet-options" disabled={saving}><legend className="sr-only">Selecionar animal</legend>{compatiblePets.map(pet=><label key={pet.id} className={`review-choice ${petId===pet.id?'chosen':''}`}><input type="radio" name="evidence-pet" checked={petId===pet.id} onChange={()=>setPetId(pet.id)}/>{pet.photo_path?<img src={`/api/pets/${pet.id}/photo`} alt=""/>:<span className="review-pet-letter">{pet.name[0]}</span>}<span className="review-choice-copy"><strong>{pet.name}</strong><small>{pet.description}</small></span></label>)}<label className={`review-choice ${petId==='unknown'?'chosen':''}`}><input type="radio" name="evidence-pet" checked={petId==='unknown'} onChange={()=>setPetId('unknown')}/><span className="review-choice-copy"><strong>Não consigo identificar</strong><small>Salvar a visita sem atribuir a um animal.</small></span></label></fieldset><div className="review-save"><p className="review-save-hint">{petId==='unknown'?'A visita será salva sem identificar o animal.':compatiblePets.find(p=>p.id===petId)?`A visita será atribuída a ${compatiblePets.find(p=>p.id===petId)?.name}.`:'Selecione o animal para concluir a revisão.'}</p>{error&&<p className="form-error" role="alert">{error}</p>}<button className="primary full" disabled={!canSave||saving} onClick={()=>void saveReview()}>{saving?'Salvando…':'Concluir revisão'}</button><button className="tertiary full" disabled={saving} onClick={()=>{setStage(decision==='correct'?'type':'validate');if(decision!=='correct')setDecision('')}}>Voltar</button></div></>}

      </div></section>}
  </>
}

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [pets, setPets] = useState<Pet[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [pending, setPending] = useState<Event[]>([])
  const [error, setError] = useState('')
  const [historyPetId, setHistoryPetId] = useState('')
  const [historyZone, setHistoryZone] = useState<Zone['type'] | ''>('')
  const [historyPage, setHistoryPage] = useState(1)
  const [historyResult, setHistoryResult] = useState<EventPage | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyReload, setHistoryReload] = useState(0)

  async function refresh() {
    try {
      const summary = await api.getDashboard()
      const [cameraList, zoneList, petList, eventList, pendingList] = await Promise.all([api.getCameras(), api.getZones(), api.getPets(), api.getEvents(false, 500, summary.date), api.getEvents(true, 500)])
      setDashboard(summary); setCameras(cameraList); setZones(zoneList); setPets(petList); setEvents(eventList); setPending(pendingList); setError('')
      setHistoryReload(value => value + 1)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Não foi possível carregar o MonitoraPet.') }
  }
  useEffect(() => { void refresh() }, [])
  useEffect(() => {
    const timer = window.setInterval(refresh, 10000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (view !== 'history') return
    let active = true
    setHistoryLoading(true)
    void api.getEventPage(historyPage, historyPetId, historyZone, 10)
      .then(result => { if (active) setHistoryResult(result) })
      .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Não foi possível carregar o histórico.') })
      .finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [view, historyPage, historyPetId, historyZone, historyReload])

  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#" onClick={e=>{e.preventDefault();setView('dashboard')}}><span className="brand-mark"><Icon name="pets"/></span><strong>monitora<span>pet</span></strong></a><p className="nav-caption">ACOMPANHAMENTO</p><nav>{(['dashboard','history','reviews','pets'] as View[]).map(item=><button key={item} className={view===item?'active':''} onClick={()=>setView(item)}><Icon name={item}/>{labels[item]}{item==='reviews'&&pending.length>0&&<b>{pending.length}</b>}</button>)}</nav><p className="nav-caption second">MONITORAMENTO</p><nav>{(['cameras','zones','settings'] as View[]).map(item=><button key={item} className={view===item?'active':''} onClick={()=>setView(item)}><Icon name={item}/>{labels[item]}</button>)}</nav><div className="sidebar-bottom"><div className="local-note"><Icon name="shield"/><div><strong>Todos os dados são armazenados localmente</strong></div></div><div className="workspace-avatar"><span>MP</span><div><strong>Minha casa</strong><small>Monitoramento local</small></div></div></div></aside><div className="main-shell"><header className="topbar"><div><span>Minha casa</span><span className="breadcrumb">/</span><strong>{labels[view]}</strong></div></header>
    <main className="content">{error && <div className="global-error">{error}<button onClick={refresh}>Tentar novamente</button></div>}{view === 'dashboard' && <DashboardView data={dashboard} pets={pets} cameras={cameras} events={events} onNavigate={setView} />}{view === 'cameras' && <CamerasView cameras={cameras} zones={zones} refresh={refresh} />}{view === 'zones' && <ZoneEditor cameras={cameras} zones={zones} refresh={refresh} />}{view === 'pets' && <PetManager pets={pets} refresh={refresh} />}{view === 'history' && <HistoryView pets={pets} result={historyResult} page={historyPage} petId={historyPetId} zoneType={historyZone} loading={historyLoading} onPage={setHistoryPage} onPet={id => { setHistoryPetId(id); setHistoryPage(1) }} onZone={type => { setHistoryZone(type); setHistoryPage(1) }} />}{view === 'reviews' && <ReviewsView events={pending} pets={pets} refresh={refresh} />}{view === 'settings' && <><div className="page-heading"><div><p className="eyebrow">SISTEMA</p><h1>Configurações</h1><p>Preferências do monitoramento local.</p></div></div><section className="panel settings"><h2>Privacidade</h2><p>Todos os dados são armazenados localmente.</p><h2>Versão</h2><p>MonitoraPet {dashboard?.health.version ?? '0.1.0'}</p></section></>}</main><footer className="app-footer">MonitoraPet <span>Um pouco mais perto da rotina deles.</span></footer></div>
  </div>
}
