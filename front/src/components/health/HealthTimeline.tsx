import { useCallback, useState } from 'react'
import * as api from '../../api'
import type { TimelineItem } from '../../api'
import { useHousehold } from '../../lib/useHousehold'
import { SectionState, formatDay, shiftDays, todayIso, useLoader } from './shared'

type Props = { petId: string; petName: string }
type Filter = 'ALL' | 'FOOD' | 'EXAM' | 'WEIGHT' | 'DOSE' | 'TREATMENT' | 'CAMERA'

const RANGES: [string, number][] = [
  ['7 dias', 7],
  ['30 dias', 30],
  ['90 dias', 90],
  ['1 ano', 365],
]
const FILTERS: [Filter, string][] = [
  ['ALL', 'Tudo'],
  ['CAMERA', 'Câmeras'],
  ['FOOD', 'Alimentação'],
  ['EXAM', 'Exames'],
  ['WEIGHT', 'Peso'],
  ['DOSE', 'Vacinas e remédios'],
  ['TREATMENT', 'Tratamentos'],
]
const GROUP: Record<string, Filter> = {
  CAMERA_DAY: 'CAMERA',
  FOOD_START: 'FOOD',
  FOOD_END: 'FOOD',
  EXAM: 'EXAM',
  WEIGHT: 'WEIGHT',
  VACCINE: 'DOSE',
  MEDICATION: 'DOSE',
  ANTIPARASITIC: 'DOSE',
  TREATMENT_START: 'TREATMENT',
  TREATMENT_END: 'TREATMENT',
  TREATMENT_ENTRY: 'TREATMENT',
}
const ZONE_ORDER = ['FOOD', 'WATER', 'LITTER', 'CUSTOM']

export default function HealthTimeline({ petId, petName }: Props) {
  const { zoneLabels } = useHousehold()
  const [days, setDays] = useState(30)
  const [filter, setFilter] = useState<Filter>('ALL')
  const end = todayIso()
  const start = shiftDays(end, -(days - 1))
  const load = useCallback(() => api.getHealthTimeline(petId, start, end), [petId, start, end])
  const { data, loading, error } = useLoader(load, { start, end, items: [] as TimelineItem[] }, 'Não foi possível carregar a linha do tempo.')

  const visible = data.items.filter(item => filter === 'ALL' || GROUP[item.kind] === filter)
  const byDay = new Map<string, TimelineItem[]>()
  for (const item of visible) byDay.set(item.date, [...(byDay.get(item.date) ?? []), item])

  function cameraDetail(item: TimelineItem) {
    const counts = item.counts ?? {}
    return ZONE_ORDER.filter(zone => counts[zone]).map(zone => {
      const { detected, confirmed } = counts[zone]
      const label = zone === 'CUSTOM' ? 'Outras áreas' : (zoneLabels as Record<string, string>)[zone] ?? zone
      return (
        <span key={zone} className={`timeline-zone ${zone.toLowerCase()}`}>
          {label}: <strong>{detected}</strong> {detected === 1 ? 'visita' : 'visitas'}
          {confirmed > 0 && <small> ({confirmed} confirmada{confirmed === 1 ? '' : 's'})</small>}
        </span>
      )
    })
  }

  return (
    <section className="panel health-section" aria-labelledby="timeline-title">
      <div className="panel-head">
        <div>
          <h2 id="timeline-title">Linha do tempo</h2>
          <p>Tudo de {petName} em ordem: registros de saúde e a rotina vista pelas câmeras.</p>
        </div>
      </div>
      <div className="health-filters">
        <div role="group" aria-label="Período">
          {RANGES.map(([label, value]) => (
            <button key={value} className={days === value ? 'selected' : ''} onClick={() => setDays(value)}>
              {label}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Tipo de registro">
          {FILTERS.map(([value, label]) => (
            <button key={value} className={filter === value ? 'selected' : ''} onClick={() => setFilter(value)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="health-hint">
        As visitas vêm das câmeras e contam presenças na área. As confirmadas são as que você conferiu nas revisões.
      </p>
      <SectionState
        loading={loading}
        error={error}
        empty={!visible.length}
        emptyTitle="Nada neste período"
        emptyText="Escolha um período maior ou adicione registros nas outras abas."
      />
      {!loading && (
        <ol className="health-timeline">
          {[...byDay.entries()].map(([day, entries]) => (
            <li key={day}>
              <h3>{formatDay(day)}</h3>
              <ul>
                {entries.map((item, index) => (
                  <li key={`${item.kind}-${item.record_id ?? 'camera'}-${index}`} className={`timeline-${GROUP[item.kind]?.toLowerCase()}`}>
                    <strong>{item.title}</strong>
                    {item.kind === 'CAMERA_DAY' ? (
                      <div className="timeline-zones">{cameraDetail(item)}</div>
                    ) : (
                      item.detail && <p>{item.detail}</p>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
