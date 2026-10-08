import { useCallback } from 'react'
import Icon from '../Icon'
import * as api from '../../api'
import type { HealthSummary as Summary } from '../../api'
import { doseKindLabels, examTypeLabels, foodTypeLabels } from '../../lib/labels'
import { SectionState, dueLabel, formatDay, formatWeight, useLoader } from './shared'
import type { HealthTab } from './PetHealth'

type Props = { petId: string; petName: string; onOpen: (tab: HealthTab) => void }

const EMPTY: Summary = {
  current_food: [],
  latest_weight: null,
  previous_weight: null,
  active_treatments: [],
  recent_exams: [],
  reminders: [],
}

export default function HealthSummary({ petId, petName, onOpen }: Props) {
  const load = useCallback(() => api.getHealthSummary(petId), [petId])
  const { data, loading, error } = useLoader<Summary>(load, EMPTY, 'Não foi possível carregar o resumo de saúde.')
  const latest = data.latest_weight
  const previous = data.previous_weight
  const delta = latest && previous ? latest.weight_kg - previous.weight_kg : null

  if (loading || error) return <SectionState loading={loading} error={error} empty={false} emptyTitle="" emptyText="" />

  return (
    <div className="health-summary">
      {data.reminders.length > 0 && (
        <section className="panel health-summary-card reminders">
          <header>
            <h2>
              <Icon name="calendar" /> Próximas doses e pendências
            </h2>
            <button className="text-button" onClick={() => onOpen('doses')}>
              Ver vacinas e remédios
            </button>
          </header>
          <ul className="health-due-list compact">
            {data.reminders.map(reminder => (
              <li key={reminder.id} className={reminder.overdue ? 'overdue' : 'soon'}>
                <div>
                  <strong>{reminder.name}</strong>
                  <span>
                    {doseKindLabels[reminder.kind]} · {formatDay(reminder.next_due_on)} ·{' '}
                    {dueLabel(reminder.days_until_due)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="panel health-summary-card">
        <header>
          <h2>
            <Icon name="food" /> Alimentação atual
          </h2>
          <button className="text-button" onClick={() => onOpen('food')}>
            {data.current_food.length ? 'Ver histórico' : 'Registrar'}
          </button>
        </header>
        {data.current_food.length ? (
          <ul className="health-plain-list">
            {data.current_food.map(food => (
              <li key={food.id}>
                <strong>{food.name}</strong>
                <span>
                  {[food.brand, foodTypeLabels[food.food_type], food.offered_amount].filter(Boolean).join(' · ')} ·
                  desde {formatDay(food.started_on)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Ainda não sabemos o que {petName} come.</p>
        )}
      </section>
      <section className="panel health-summary-card">
        <header>
          <h2>
            <Icon name="activity" /> Peso
          </h2>
          <button className="text-button" onClick={() => onOpen('weight')}>
            {latest ? 'Ver evolução' : 'Registrar'}
          </button>
        </header>
        {latest ? (
          <p className="health-big-number">
            <strong>{formatWeight(latest.weight_kg)}</strong>
            <span>
              em {formatDay(latest.measured_on)}
              {delta !== null &&
                ` · ${delta === 0 ? 'igual à' : `${delta > 0 ? '+' : '−'}${formatWeight(Math.abs(delta))} desde a`} pesagem anterior`}
            </span>
          </p>
        ) : (
          <p className="muted">Nenhuma pesagem registrada.</p>
        )}
      </section>
      <section className="panel health-summary-card">
        <header>
          <h2>
            <Icon name="shield" /> Tratamentos em andamento
          </h2>
          <button className="text-button" onClick={() => onOpen('treatments')}>
            Ver tratamentos
          </button>
        </header>
        {data.active_treatments.length ? (
          <ul className="health-plain-list">
            {data.active_treatments.map(treatment => (
              <li key={treatment.id}>
                <strong>{treatment.title}</strong>
                <span>
                  {[treatment.body_region, `desde ${formatDay(treatment.started_on)}`].filter(Boolean).join(' · ')}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhum tratamento em andamento.</p>
        )}
      </section>
      <section className="panel health-summary-card">
        <header>
          <h2>
            <Icon name="reviews" /> Exames recentes
          </h2>
          <button className="text-button" onClick={() => onOpen('exams')}>
            {data.recent_exams.length ? 'Ver todos' : 'Adicionar'}
          </button>
        </header>
        {data.recent_exams.length ? (
          <ul className="health-plain-list">
            {data.recent_exams.map(exam => (
              <li key={exam.id}>
                <strong>{exam.title}</strong>
                <span>
                  {examTypeLabels[exam.exam_type]} · {formatDay(exam.performed_on, 'sem data')} ·{' '}
                  {exam.attachments.length} arquivo(s)
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhum exame guardado.</p>
        )}
      </section>
    </div>
  )
}
