import { useEffect, useState } from 'react'
import * as api from '../api'
import type { Camera, Dashboard, Event, Pet } from '../api'
import EventList from '../components/EventList'
import Icon, { IconName } from '../components/Icon'
import PetAvatar from '../components/PetAvatar'
import type { View } from '../lib/views'
import { useHousehold } from '../lib/useHousehold'

type Props = {
  data: Dashboard | null
  pets: Pet[]
  cameras: Camera[]
  reloadToken: number
  onNavigate: (view: View) => void
}

type Metric = { type: string; title: string; icon: IconName; className: string; sub: string }

const RECENT_LIMIT = 5
const DAY_LIMIT = 500

export default function DashboardView({ data, pets, cameras, reloadToken, onNavigate }: Props) {
  const { zoneLabels, zoneIcon, hygieneSummary } = useHousehold()
  const [petId, setPetId] = useState('')
  const metrics: Metric[] = [
    { type: 'WATER', title: zoneLabels.WATER, icon: 'water', className: 'water', sub: 'visitas ao bebedouro' },
    { type: 'FOOD', title: zoneLabels.FOOD, icon: 'food', className: 'food', sub: 'visitas ao comedouro' },
    { type: 'LITTER', title: zoneLabels.LITTER, icon: zoneIcon('LITTER'), className: 'litter', sub: hygieneSummary },
  ]
  const [events, setEvents] = useState<Event[]>([])
  const date = data?.date
  const eventsToday = data?.events_today

  useEffect(() => {
    if (!date) return
    let active = true
    void api
      .getEvents(false, DAY_LIMIT, date)
      .then(list => {
        if (active) setEvents(list)
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [date, eventsToday, reloadToken])

  if (!data) return <div className="loading">Carregando a rotina dos pets…</div>

  const filtered = events.filter(e => e.review_decision !== 'FALSE_POSITIVE' && (!petId || e.pet_id === petId))
  const selected = pets.find(p => p.id === petId)
  const byType: Record<string, number> = selected
    ? Object.fromEntries(metrics.map(m => [m.type, filtered.filter(e => e.zone_type === m.type).length]))
    : data.by_zone_type
  const liveCamera = cameras.find(camera => camera.status.connected)

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">UM OLHAR SOBRE A ROTINA</div>
          <h1>
            O dia dos seus pets<span className="heading-dot">.</span>
          </h1>
          <p>Pequenas visitas. Um acompanhamento mais próximo.</p>
        </div>
        <span className="date-pill">
          <Icon name="calendar" />
          {new Date().toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}
        </span>
      </div>
      <div className="pet-selector" role="group" aria-label="Filtrar por pet">
        <button className={!petId ? 'selected' : ''} onClick={() => setPetId('')}>
          <span className="all-pets">
            <Icon name="pets" />
          </span>
          Todos os pets
        </button>
        {pets.map(p => (
          <button className={petId === p.id ? 'selected' : ''} key={p.id} onClick={() => setPetId(p.id)}>
            <PetAvatar pet={p} />
            {p.name}
          </button>
        ))}
      </div>
      {petId && (
        <p className="filter-note">
          Resumo das visitas identificadas de {selected?.name}. Registros sem identificação ficam em Todos os pets.
        </p>
      )}
      <section className="metrics">
        {metrics.map(m => (
          <article key={m.type} className={m.className}>
            <div className="metric-label">
              <span>{m.title}</span>
              <span className="metric-icon">
                <Icon name={m.icon} />
              </span>
            </div>
            <div className="metric-number">
              {byType[m.type] ?? 0}
              <span>visitas</span>
            </div>
            <small>{m.sub}</small>
          </article>
        ))}
        <article className="total">
          <div className="metric-label">
            <span>Atividade do dia</span>
            <span className="metric-icon">
              <Icon name="activity" />
            </span>
          </div>
          <div className="metric-number">
            {petId ? filtered.length : data.events_today}
            <span>registros</span>
          </div>
          <small>{petId ? 'registros identificados hoje' : 'em todas as áreas'}</small>
        </article>
      </section>
      <p className="observation-note">
        <Icon name="info" />
        Uma visita à área não confirma ingestão de água, alimentação ou uso do banheiro.
      </p>
      <div className="dashboard-layout">
        <div className="dashboard-main">
          <section className="panel activity-panel">
            <div className="panel-head">
              <div>
                <h2>Últimas visitas</h2>
                <p>O que aconteceu nas áreas monitoradas.</p>
              </div>
              <button className="text-button" onClick={() => onNavigate('history')}>
                Ver histórico
              </button>
            </div>
            <EventList
              events={filtered.slice(0, RECENT_LIMIT)}
              onChange={updated => setEvents(current => current.map(e => (e.id === updated.id ? updated : e)))}
            />
            <div className="panel-foot">
              <Icon name="clock" />
              Horários apresentados no seu fuso local
            </div>
          </section>
          {data.pending_reviews > 0 && (
            <section className="review-banner">
              <div className="review-banner-icon">
                <Icon name="reviews" />
              </div>
              <div>
                <h3>Um olhar seu faz a diferença</h3>
                <p>{data.pending_reviews} registros precisam de confirmação ou identificação do pet.</p>
              </div>
              <button className="secondary" onClick={() => onNavigate('reviews')}>
                Revisar registros
                <b>{data.pending_reviews}</b>
              </button>
            </section>
          )}
        </div>
        <aside className="dashboard-aside">
          <section className="panel camera-summary">
            <div className="panel-head">
              <h2>Suas câmeras</h2>
              <button className="icon-button" title="Gerenciar câmeras" onClick={() => onNavigate('cameras')}>
                <Icon name="settings" />
              </button>
            </div>
            {liveCamera ? (
              <div className="camera-still">
                <img src={`/api/cameras/${liveCamera.id}/video`} alt={`Vídeo ao vivo de ${liveCamera.name}`} />
                <span>AO VIVO</span>
                <div className="still-caption">
                  <Icon name="camera" />
                  {liveCamera.name}
                </div>
              </div>
            ) : (
              <div className="camera-still camera-still-empty">
                {cameras.length ? 'Nenhuma câmera conectada' : 'Nenhuma câmera cadastrada'}
              </div>
            )}
            <div className="camera-summary-list">
              {cameras.map(c => (
                <button key={c.id} onClick={() => onNavigate('cameras')}>
                  <div>
                    <Icon name="camera" />
                    <span>
                      <strong>{c.name}</strong>
                      <small>{c.status.connected ? 'Conectada' : 'Conexão interrompida'}</small>
                    </span>
                  </div>
                  <span className={c.status.connected ? 'camera-state online' : 'camera-state offline'}>
                    {c.status.connected ? 'Online' : 'Offline'}
                  </span>
                </button>
              ))}
            </div>
            <button className="secondary full" onClick={() => onNavigate('cameras')}>
              Abrir câmeras
            </button>
          </section>
        </aside>
      </div>
    </>
  )
}
