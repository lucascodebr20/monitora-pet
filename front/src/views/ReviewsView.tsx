import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Event, Pet, Zone } from '../api'
import Empty from '../components/Empty'
import Icon, { IconName } from '../components/Icon'
import { useToast } from '../components/useToast'
import { errorMessage } from '../lib/errors'
import { correctableZoneTypes, formatDateTime, zoneIcon, zoneLabels } from '../lib/labels'

type Props = { pets: Pet[]; reloadToken: number; refresh: () => Promise<void> }
type Decision = 'accept' | 'reject' | 'correct' | 'noaction' | 'multiple'
type Stage = 'validate' | 'type' | 'pet' | 'pets'

const PENDING_LIMIT = 500
const UNKNOWN_PET = 'unknown'

const decisionOptions: { value: Decision; icon: IconName; title: string; description: (zone: string) => string }[] = [
  { value: 'accept', icon: 'accept', title: 'Aceitar', description: zone => `É uma visita à área de ${zone}.` },
  {
    value: 'noaction',
    icon: 'noaction',
    title: 'Não usou a área',
    description: zone => `O gato esteve ali, mas não usou a área de ${zone}.`,
  },
  {
    value: 'multiple',
    icon: 'pets',
    title: 'Vários gatos',
    description: () => 'Mais de um animal aparece na imagem.',
  },
  {
    value: 'correct',
    icon: 'correct',
    title: 'Corrigir tipo',
    description: () => 'A visita é válida, mas o tipo está errado.',
  },
  { value: 'reject', icon: 'reject', title: 'Recusar', description: () => 'A imagem não comprova uma visita à área.' },
]

function ReviewWizard({ event, pets, onSaved }: { event: Event; pets: Pet[]; onSaved: () => Promise<void> }) {
  const showToast = useToast()
  const [decision, setDecision] = useState<Decision | ''>('')
  const [stage, setStage] = useState<Stage>('validate')
  const [correctedType, setCorrectedType] = useState<Zone['type'] | ''>('')
  const [petId, setPetId] = useState(event.pet_id ?? '')
  const [petIds, setPetIds] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const stageHeading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    stageHeading.current?.focus()
  }, [stage])

  const validPet = petId === UNKNOWN_PET || pets.some(p => p.id === petId)
  const typeChanged = !!correctedType && correctedType !== event.zone_type
  // "Não usou a área" exige dizer qual gato era: é essa afirmação que ensina o
  // identificador, mesmo sem ter havido a ação.
  const namedPet = pets.some(p => p.id === petId)
  const canSave =
    decision === 'reject' ||
    (decision === 'multiple' && petIds.length >= 2) ||
    (decision === 'noaction' && stage === 'pet' && namedPet) ||
    (stage === 'pet' && decision !== 'noaction' && validPet && (decision !== 'correct' || typeChanged))
  const effectiveType = decision === 'correct' && correctedType ? correctedType : event.zone_type
  const chosenPet = pets.find(p => p.id === petId)

  function chooseDecision(value: Decision) {
    setDecision(value)
    setError('')
    if (value === 'accept' || value === 'noaction') setStage('pet')
    else if (value === 'correct') setStage('type')
    else if (value === 'multiple') setStage('pets')
    else setStage('validate')
  }

  function togglePet(id: string) {
    setPetIds(current => (current.includes(id) ? current.filter(value => value !== id) : [...current, id]))
  }

  async function saveReview() {
    if (!canSave || saving) return
    setSaving(true)
    setError('')
    try {
      const apiDecision =
        decision === 'reject'
          ? 'FALSE_POSITIVE'
          : decision === 'correct'
            ? 'CORRECTED'
            : decision === 'noaction'
              ? 'NO_ACTION'
              : decision === 'multiple'
                ? 'MULTIPLE_PETS'
                : 'CONFIRMED'
      const singlePet = decision === 'reject' || decision === 'multiple' || petId === UNKNOWN_PET ? null : petId || null
      await api.reviewEvent(
        event.id,
        apiDecision,
        singlePet,
        decision === 'correct' && correctedType ? correctedType : undefined,
        decision === 'multiple' ? petIds : undefined,
      )
      await onSaved()
      showToast(
        decision === 'reject'
          ? 'Evidência recusada.'
          : decision === 'noaction'
            ? 'Registrado: esteve na área, mas não usou.'
            : decision === 'multiple'
              ? `Registrado com ${petIds.length} gatos.`
              : decision === 'correct' && correctedType
                ? `Tipo corrigido para ${zoneLabels[correctedType].toLowerCase()}.`
                : 'Evidência aceita.',
      )
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível salvar. Tente novamente.'))
    } finally {
      setSaving(false)
    }
  }

  const stepNumber = stage === 'validate' ? 2 : stage === 'type' || decision === 'accept' || stage === 'pets' ? 3 : 4

  return (
    <section className="review-card review-flow">
      <div className="review-evidence">
        <div className="review-step-heading">
          <span>1</span>
          <h2>Confira a evidência</h2>
        </div>
        <div className="review-media">
          {event.clip_path ? (
            <video
              controls
              preload="metadata"
              poster={event.snapshot_path ? `/api/events/${event.id}/snapshot` : undefined}
            >
              <source src={`/api/events/${event.id}/clip`} type="video/webm" />
              Seu navegador não conseguiu reproduzir este vídeo.
            </video>
          ) : event.snapshot_path ? (
            <div className="review-snapshot">
              <img src={`/api/events/${event.id}/snapshot`} alt={`Evidência de uma visita à área ${event.zone_name}`} />
            </div>
          ) : (
            <p>Mídia indisponível para este registro.</p>
          )}
        </div>
        <div className="review-record-details">
          <div>
            <strong>{zoneLabels[event.zone_type]}</strong>
            <p>
              {event.camera_name} · {formatDateTime(event.started_at)}
            </p>
          </div>
          <span>{event.duration_seconds ? `${Math.round(event.duration_seconds)}s na área` : 'Em andamento'}</span>
        </div>
      </div>
      <div className="review-detail review-wizard">
        <div className="review-step-heading">
          <span>{stepNumber}</span>
          <h2 ref={stageHeading} tabIndex={-1}>
            {stage === 'validate'
              ? 'A evidência está correta?'
              : stage === 'type'
                ? 'Qual é o tipo correto?'
                : stage === 'pets'
                  ? 'Quais gatos aparecem?'
                  : 'Qual animal aparece?'}
          </h2>
        </div>
        {stage === 'validate' && (
          <>
            <div className="evidence-actions">
              {decisionOptions.map(option => (
                <button
                  type="button"
                  className={`evidence-action evidence-action-${option.value} ${decision === option.value ? 'chosen' : ''}`}
                  key={option.value}
                  disabled={saving}
                  onClick={() => chooseDecision(option.value)}
                >
                  <span className="evidence-action-icon">
                    <Icon name={option.icon} />
                  </span>
                  <span className="evidence-action-copy">
                    <strong>{option.title}</strong>
                    <span>{option.description(zoneLabels[event.zone_type].toLowerCase())}</span>
                  </span>
                </button>
              ))}
            </div>
            {decision === 'reject' && (
              <div className="review-save">
                <p className="review-save-hint">
                  A evidência ficará no histórico como recusada e não entrará no resumo de visitas.
                </p>
                {error && (
                  <p className="form-error" role="alert">
                    {error}
                  </p>
                )}
                <button className="primary full" disabled={saving} onClick={() => void saveReview()}>
                  {saving ? 'Salvando…' : 'Confirmar recusa'}
                </button>
              </div>
            )}
          </>
        )}
        {stage === 'type' && (
          <>
            <p className="wizard-context">
              Tipo detectado: <strong>{zoneLabels[event.zone_type]}</strong>
            </p>
            <fieldset className="review-type-options" disabled={saving}>
              <legend className="sr-only">Novo tipo da evidência</legend>
              <div>
                {correctableZoneTypes.map(type => (
                  <label
                    key={type}
                    className={`${correctedType === type ? 'chosen' : ''} ${event.zone_type === type ? 'current-type' : ''}`}
                  >
                    <input
                      type="radio"
                      name="corrected-evidence-type"
                      value={type}
                      disabled={event.zone_type === type}
                      checked={correctedType === type}
                      onChange={() => setCorrectedType(type)}
                    />
                    <Icon name={zoneIcon(type)} />
                    <span>
                      {zoneLabels[type]}
                      {event.zone_type === type && <small>Tipo atual</small>}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="review-save">
              <button className="primary full" disabled={!typeChanged} onClick={() => setStage('pet')}>
                Continuar
              </button>
              <button
                className="tertiary full"
                onClick={() => {
                  setStage('validate')
                  setDecision('')
                }}
              >
                Voltar
              </button>
            </div>
          </>
        )}
        {stage === 'pets' && (
          <>
            <p className="wizard-context">
              Visita à área de <strong>{zoneLabels[event.zone_type].toLowerCase()}</strong>
            </p>
            <p className="auto-identification-note">
              <Icon name="pets" />
              <span>
                Com mais de um gato, a visita entra no histórico de todos eles, mas nenhum é usado para treinar a
                identificação — a imagem tem mais de um animal.
              </span>
            </p>
            <fieldset className="review-pet-options" disabled={saving}>
              <legend className="sr-only">Selecionar os animais presentes</legend>
              {pets.map(pet => (
                <label key={pet.id} className={`review-choice ${petIds.includes(pet.id) ? 'chosen' : ''}`}>
                  <input type="checkbox" checked={petIds.includes(pet.id)} onChange={() => togglePet(pet.id)} />
                  {pet.photo_path ? (
                    <img src={`/api/pets/${pet.id}/photo`} alt="" />
                  ) : (
                    <span className="review-pet-letter">{pet.name[0]}</span>
                  )}
                  <span className="review-choice-copy">
                    <strong>{pet.name}</strong>
                    <small>{pet.description}</small>
                  </span>
                </label>
              ))}
            </fieldset>
            <div className="review-save">
              <p className="review-save-hint">
                {petIds.length >= 2
                  ? `A visita será registrada com ${petIds.length} gatos.`
                  : 'Selecione pelo menos dois gatos.'}
              </p>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <button className="primary full" disabled={!canSave || saving} onClick={() => void saveReview()}>
                {saving ? 'Salvando…' : 'Concluir revisão'}
              </button>
              <button
                className="tertiary full"
                disabled={saving}
                onClick={() => {
                  setStage('validate')
                  setDecision('')
                  setPetIds([])
                }}
              >
                Voltar
              </button>
            </div>
          </>
        )}
        {stage === 'pet' && (
          <>
            <p className="wizard-context">
              {decision === 'noaction' ? 'Esteve na área de ' : 'Visita à área de '}
              <strong>{zoneLabels[effectiveType].toLowerCase()}</strong>
              {decision === 'correct' && ' · tipo corrigido'}
              {decision === 'noaction' && ' · sem uso'}
            </p>
            {event.automatically_identified_pet_id && (
              <p className="auto-identification-note">
                <Icon name="pets" />
                <span>
                  Sugestão automática: <strong>{event.pet_name}</strong>
                  {event.pet_identification_confidence !== null &&
                    ` · ${Math.round(event.pet_identification_confidence * 100)}% de similaridade`}
                  . Se necessário, selecione outro pet.
                </span>
              </p>
            )}
            <fieldset className="review-pet-options" disabled={saving}>
              <legend className="sr-only">Selecionar animal</legend>
              {pets.map(pet => (
                <label key={pet.id} className={`review-choice ${petId === pet.id ? 'chosen' : ''}`}>
                  <input
                    type="radio"
                    name="evidence-pet"
                    checked={petId === pet.id}
                    onChange={() => setPetId(pet.id)}
                  />
                  {pet.photo_path ? (
                    <img src={`/api/pets/${pet.id}/photo`} alt="" />
                  ) : (
                    <span className="review-pet-letter">{pet.name[0]}</span>
                  )}
                  <span className="review-choice-copy">
                    <strong>{pet.name}</strong>
                    <small>{pet.description}</small>
                  </span>
                </label>
              ))}
              {decision !== 'noaction' && (
                <label className={`review-choice ${petId === UNKNOWN_PET ? 'chosen' : ''}`}>
                  <input
                    type="radio"
                    name="evidence-pet"
                    checked={petId === UNKNOWN_PET}
                    onChange={() => setPetId(UNKNOWN_PET)}
                  />
                  <span className="review-choice-copy">
                    <strong>Não consigo identificar</strong>
                    <small>Salvar a visita sem atribuir a um animal.</small>
                  </span>
                </label>
              )}
            </fieldset>
            <div className="review-save">
              <p className="review-save-hint">
                {decision === 'noaction'
                  ? chosenPet
                    ? `${chosenPet.name} esteve na área sem usá-la. Não entra no resumo de visitas, mas confirma a identificação.`
                    : 'Selecione qual gato esteve na área.'
                  : petId === UNKNOWN_PET
                    ? 'A visita será salva sem identificar o animal.'
                    : chosenPet
                      ? `A visita será atribuída a ${chosenPet.name}.`
                      : 'Selecione o animal para concluir a revisão.'}
              </p>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <button className="primary full" disabled={!canSave || saving} onClick={() => void saveReview()}>
                {saving ? 'Salvando…' : 'Concluir revisão'}
              </button>
              <button
                className="tertiary full"
                disabled={saving}
                onClick={() => {
                  setStage(decision === 'correct' ? 'type' : 'validate')
                  if (decision !== 'correct') setDecision('')
                }}
              >
                Voltar
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  )
}

export default function ReviewsView({ pets, reloadToken, refresh }: Props) {
  const [events, setEvents] = useState<Event[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void api
      .getEvents(true, PENDING_LIMIT)
      .then(list => {
        if (active) {
          setEvents(list)
          setError('')
        }
      })
      .catch(reason => {
        if (active) setError(errorMessage(reason, 'Não foi possível carregar as revisões.'))
      })
    return () => {
      active = false
    }
  }, [reloadToken])

  const current = events.find(event => event.id === currentId) ?? events[0]

  useEffect(() => {
    if (current && current.id !== currentId) setCurrentId(current.id)
  }, [current, currentId])

  async function onSaved() {
    const index = events.findIndex(event => event.id === current?.id)
    const next = events[index + 1] ?? events[index - 1]
    setCurrentId(next?.id ?? null)
    await refresh()
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">REGISTROS PARA CONFERIR</p>
          <h1>Revisões</h1>
          <p>
            {events.length
              ? `${events.length} ${events.length === 1 ? 'registro aguardando' : 'registros aguardando'} revisão, do mais antigo ao mais recente.`
              : 'Nenhum registro pendente.'}
          </p>
        </div>
      </div>
      {error && <p className="form-error">{error}</p>}
      {!current ? (
        <section className="panel">
          <Empty title="Tudo revisado">Novos registros aparecerão aqui quando uma visita for detectada.</Empty>
        </section>
      ) : (
        <div className="review-layout">
          <aside className="review-queue panel" aria-label="Fila de revisão">
            <h2>Fila</h2>
            <ol>
              {events.map((event, index) => (
                <li key={event.id}>
                  <button
                    type="button"
                    className={event.id === current.id ? 'selected' : ''}
                    aria-current={event.id === current.id ? 'true' : undefined}
                    onClick={() => setCurrentId(event.id)}
                  >
                    <span className="review-queue-index">{index + 1}</span>
                    <span>
                      <strong>
                        <Icon name={zoneIcon(event.zone_type)} /> {zoneLabels[event.zone_type]}
                      </strong>
                      <small>
                        {event.camera_name} · {formatDateTime(event.started_at)}
                      </small>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </aside>
          <ReviewWizard key={current.id} event={current} pets={pets} onSaved={onSaved} />
        </div>
      )}
    </>
  )
}
