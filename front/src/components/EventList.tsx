import { useCallback, useState } from 'react'
import type { Event } from '../api'
import { formatDateTime } from '../lib/labels'
import { useHousehold } from '../lib/useHousehold'
import { useEscape } from '../lib/hooks'
import Empty from './Empty'
import Icon from './Icon'
import StarButton from './StarButton'

function reviewLabel(decision: string | null): string {
  if (decision === 'FALSE_POSITIVE') return 'Descartado'
  if (decision === 'INCONCLUSIVE') return 'Inconclusivo'
  return decision ? 'Revisado' : 'A revisar'
}

type DetailProps = { event: Event; onClose: () => void; onChange: (event: Event) => void }

function EventDetail({ event, onClose, onChange }: DetailProps) {
  const { zoneLabels } = useHousehold()
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Detalhes do registro">
      <section className="modal event-detail-modal">
        <div className="panel-head">
          <h2>Detalhes da visita</h2>
          <button className="close" aria-label="Fechar detalhes" onClick={onClose}>
            ×
          </button>
        </div>
        {event.clip_path ? (
          <video
            className="event-detail-photo"
            controls
            preload="metadata"
            poster={event.snapshot_path ? `/api/events/${event.id}/snapshot` : undefined}
          >
            <source src={`/api/events/${event.id}/clip`} type="video/webm" />
          </video>
        ) : event.snapshot_path ? (
          <img
            className="event-detail-photo"
            src={`/api/events/${event.id}/snapshot`}
            alt={`Evidência de ${event.zone_name}`}
          />
        ) : (
          <p className="muted">Não há imagem disponível para este registro.</p>
        )}
        <h3>
          {event.pet_name ?? 'Pet não identificado'} · {zoneLabels[event.zone_type]}
        </h3>
        <p>
          {event.camera_name} · {formatDateTime(event.started_at)}
        </p>
        <div className="highlight-box">
          <StarButton event={event} onChange={onChange} withLabel />
          <small className="muted">
            {event.highlighted_at
              ? `Favoritado em ${formatDateTime(event.highlighted_at)}. A mídia deste registro não é apagada pela retenção.`
              : 'Guarde este registro nos favoritos. A mídia dele deixa de ser apagada pela retenção.'}
          </small>
        </div>
        <div className="detail-metrics">
          <div>
            <span>Permanência</span>
            <strong>{Math.round(event.duration_seconds)}s</strong>
          </div>
          <div>
            <span>Detecção</span>
            <strong>{Math.round((event.confidence ?? 0) * 100)}%</strong>
          </div>
          <div>
            <span>Revisão</span>
            <strong>
              {event.review_decision === 'FALSE_POSITIVE'
                ? 'Recusada'
                : event.review_decision
                  ? 'Concluída'
                  : 'Pendente'}
            </strong>
          </div>
        </div>
        <button className="secondary full" onClick={onClose}>
          Fechar registro
        </button>
      </section>
    </div>
  )
}

type Props = { events: Event[]; onChange: (event: Event) => void }

export default function EventList({ events, onChange }: Props) {
  const { zoneLabels, zoneIcon } = useHousehold()
  const [detailId, setDetailId] = useState<string | null>(null)
  const detail = events.find(event => event.id === detailId) ?? null
  const close = useCallback(() => setDetailId(null), [])
  useEscape(close, detail !== null)

  if (!events.length)
    return (
      <Empty title="Nenhuma visita registrada">
        Os eventos aparecerão quando o monitoramento detectar um pet em uma zona.
      </Empty>
    )
  return (
    <>
      <div className="event-list">
        {events.map(event => (
          <div className={`event-row ${event.highlighted_at ? 'highlighted' : ''}`} key={event.id}>
            <button className="event-open" onClick={() => setDetailId(event.id)}>
              <div className={`event-kind ${event.zone_type.toLowerCase()}`}>
                <Icon name={zoneIcon(event.zone_type)} />
              </div>
              <div>
                <strong>
                  {event.pet_name ? `${event.pet_name} · ` : 'Pet não identificado · '}
                  {zoneLabels[event.zone_type] ?? event.zone_name}
                </strong>
                <span>
                  {event.camera_name} · {formatDateTime(event.started_at)}
                </span>
              </div>
              <div className="event-meta">
                <strong>{Math.round(event.duration_seconds)}s</strong>
                <span className={!event.review_decision ? 'pending' : ''}>{reviewLabel(event.review_decision)}</span>
              </div>
            </button>
            <StarButton event={event} onChange={onChange} />
          </div>
        ))}
      </div>
      {detail && <EventDetail event={detail} onClose={close} onChange={onChange} />}
    </>
  )
}
