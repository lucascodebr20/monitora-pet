import { useCallback, useState } from 'react'
import * as api from '../../api'
import EventList from '../EventList'
import Icon from '../Icon'
import { activityEvents } from '../../lib/eventActivity'
import { useHousehold } from '../../lib/useHousehold'
import { SectionState, formatDay, shiftDays, todayIso, useLoader } from './shared'

type Props = { petId: string; petName: string; onOpenTimeline: () => void }
const RANGES = [
  ['Hoje', 1],
  ['7 dias', 7],
  ['30 dias', 30],
  ['90 dias', 90],
] as const

export default function PetActivity({ petId, petName, onOpenTimeline }: Props) {
  const [days, setDays] = useState(30)
  const { zoneLabels, zoneIcon } = useHousehold()
  const end = todayIso()
  const start = shiftDays(end, -(days - 1))
  const load = useCallback(async () => {
    const [timeline, page] = await Promise.all([
      api.getHealthTimeline(petId, start, end),
      api.getEventPage(1, petId, '', 20, start, end),
    ])
    return { items: timeline.items, events: activityEvents(page.events, petId) }
  }, [petId, start, end])
  const { data, setData, loading, error } = useLoader<{ items: api.TimelineItem[]; events: api.Event[] }>(
    load,
    { items: [], events: [] },
    'Não foi possível carregar as atividades deste pet.',
  )
  const counts: Record<string, { detected: number; confirmed: number }> = {}
  const cameraDays = data.items.filter(item => item.kind === 'CAMERA_DAY')
  for (const item of cameraDays) {
    for (const [zone, value] of Object.entries(item.counts ?? {})) {
      const total = counts[zone] ?? { detected: 0, confirmed: 0 }
      counts[zone] = { detected: total.detected + value.detected, confirmed: total.confirmed + value.confirmed }
    }
  }
  const total = Object.values(counts).reduce((sum, count) => sum + count.detected, 0)

  return (
    <section className="panel health-section pet-activity" aria-labelledby="pet-activity-title">
      <div className="panel-head">
        <div>
          <h2 id="pet-activity-title">A rotina de {petName}</h2>
          <p>Atividades registradas pelas câmeras, junto da ficha de saúde.</p>
        </div>
        <button type="button" className="text-button" onClick={onOpenTimeline}>
          Ver linha do tempo
        </button>
      </div>
      <div className="health-filters">
        <div role="group" aria-label="Período das atividades">
          {RANGES.map(([label, value]) => (
            <button
              type="button"
              key={value}
              aria-pressed={days === value}
              className={days === value ? 'selected' : ''}
              onClick={() => setDays(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="health-hint">
        {formatDay(start)}
        {start !== end && ` a ${formatDay(end)}`} · Somente registros identificados de {petName}.
      </p>
      <SectionState
        loading={loading}
        error={error}
        empty={!total}
        emptyTitle="Nenhuma atividade identificada neste período"
        emptyText="Escolha um período maior. Se as visitas estão sem identificação, associe este pet aos registros na tela de Revisões."
      />
      {!loading && !error && total > 0 && (
        <>
          <div className="pet-activity-metrics">
            {(['FOOD', 'WATER', 'LITTER', 'CUSTOM'] as const)
              .filter(zone => zone !== 'CUSTOM' || counts.CUSTOM)
              .map(zone => (
                <article key={zone}>
                  <div>
                    <Icon name={zoneIcon(zone)} />
                    <span>{zoneLabels[zone]}</span>
                  </div>
                  <strong>
                    {counts[zone]?.detected ?? 0}
                    <small> visitas</small>
                  </strong>
                  <p>{counts[zone]?.confirmed ?? 0} confirmadas na revisão</p>
                </article>
              ))}
          </div>
          <p className="health-hint">
            {total} visitas em {cameraDays.length} dia(s) com atividade. Uma visita à área não confirma alimentação,
            ingestão de água ou uso do banheiro.
          </p>
          {data.events.length > 0 && (
            <div className="pet-activity-recent">
              <h3>Registros recentes</h3>
              <EventList
                events={data.events.slice(0, 5)}
                onChange={updated =>
                  setData(current => ({
                    ...current,
                    events: current.events.map(event => (event.id === updated.id ? updated : event)),
                  }))
                }
              />
            </div>
          )}
        </>
      )}
    </section>
  )
}
