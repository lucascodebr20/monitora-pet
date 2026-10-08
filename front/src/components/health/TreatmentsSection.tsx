import { FormEvent, useCallback, useState } from 'react'
import * as api from '../../api'
import type { HealthAttachment, Treatment, TreatmentEntry, TreatmentPayload } from '../../api'
import { errorMessage } from '../../lib/errors'
import { doseKindLabels } from '../../lib/labels'
import Lightbox from '../Lightbox'
import { useToast } from '../useToast'
import { SectionState, formatDay, formatInstant, nowLocalInput, todayIso, useLoader } from './shared'

type Props = { petId: string; petName: string; onChanged: () => void }
type EntryForm = { observed_at: string; notes: string; files: File[] }
type Photo = { attachment: HealthAttachment; entry: TreatmentEntry }

const PHOTO_ACCEPT = 'image/jpeg,image/png,image/webp'
const emptyTreatment = (): TreatmentPayload => ({
  title: '',
  body_region: '',
  description: '',
  instructions: '',
  started_on: todayIso(),
  ended_on: null,
})

export default function TreatmentsSection({ petId, petName, onChanged }: Props) {
  const showToast = useToast()
  const load = useCallback(() => api.getTreatments(petId), [petId])
  const { data: treatments, loading, error, reload } = useLoader<Treatment[]>(load, [], 'Não foi possível carregar os tratamentos.')
  const [form, setForm] = useState<TreatmentPayload | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [entryForm, setEntryForm] = useState<EntryForm | null>(null)
  const [entryInputKey, setEntryInputKey] = useState(0)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [compare, setCompare] = useState<string[]>([])
  const [openImage, setOpenImage] = useState<HealthAttachment | null>(null)

  const opened = treatments.find(item => item.id === openId) ?? null

  function startCreate() {
    setEditingId(null)
    setForm(emptyTreatment())
    setFormError('')
  }

  function startEdit(treatment: Treatment) {
    setEditingId(treatment.id)
    setForm({
      title: treatment.title,
      body_region: treatment.body_region,
      description: treatment.description,
      instructions: treatment.instructions,
      started_on: treatment.started_on,
      ended_on: treatment.ended_on,
    })
    setFormError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form || saving) return
    setSaving(true)
    setFormError('')
    try {
      const payload = { ...form, ended_on: form.ended_on || null }
      const saved = editingId
        ? await api.updateTreatment(petId, editingId, payload)
        : await api.createTreatment(petId, payload)
      setForm(null)
      setOpenId(saved.id)
      reload()
      onChanged()
      showToast(editingId ? 'Tratamento atualizado.' : 'Tratamento criado.')
    } catch (reason) {
      setFormError(errorMessage(reason, 'Não foi possível salvar o tratamento.'))
    } finally {
      setSaving(false)
    }
  }

  async function finish(treatment: Treatment) {
    try {
      await api.updateTreatment(petId, treatment.id, { ...treatment, ended_on: todayIso() })
      reload()
      onChanged()
      showToast('Tratamento encerrado hoje.')
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível encerrar o tratamento.'), 'error')
    }
  }

  async function remove(treatment: Treatment) {
    if (!window.confirm(`Apagar "${treatment.title}" com todos os registros e fotos? As aplicações ligadas a ele continuam guardadas.`))
      return
    try {
      await api.deleteHealthRecord(petId, 'treatments', treatment.id)
      setOpenId(null)
      reload()
      onChanged()
      showToast('Tratamento apagado.')
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível apagar o tratamento.'), 'error')
    }
  }

  async function submitEntry(event: FormEvent) {
    event.preventDefault()
    if (!opened || !entryForm || saving) return
    setSaving(true)
    setFormError('')
    try {
      const entry = await api.createTreatmentEntry(petId, opened.id, {
        observed_at: new Date(entryForm.observed_at).toISOString(),
        notes: entryForm.notes,
      })
      const failures: string[] = []
      for (const file of entryForm.files) {
        try {
          await api.uploadTreatmentPhoto(petId, opened.id, entry.id, file)
        } catch (reason) {
          failures.push(`${file.name}: ${errorMessage(reason, 'falhou')}`)
        }
      }
      setEntryForm(null)
      reload()
      onChanged()
      if (failures.length) showToast(`Registro salvo, mas algumas fotos falharam: ${failures.join('; ')}`, 'error')
      else showToast('Evolução registrada.')
    } catch (reason) {
      setFormError(errorMessage(reason, 'Não foi possível registrar a evolução.'))
    } finally {
      setSaving(false)
    }
  }

  async function removeEntry(entry: TreatmentEntry) {
    if (!opened || !window.confirm(`Apagar o registro de ${formatInstant(entry.observed_at)} e suas fotos?`)) return
    try {
      await api.deleteTreatmentEntry(petId, opened.id, entry.id)
      setCompare(current => current.filter(id => !entry.attachments.some(item => item.id === id)))
      reload()
      onChanged()
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível apagar o registro.'), 'error')
    }
  }

  function toggleCompare(id: string) {
    setCompare(current => (current.includes(id) ? current.filter(item => item !== id) : [...current.slice(-1), id]))
  }

  const photos: Photo[] = opened
    ? opened.entries.flatMap(entry =>
        entry.attachments.filter(item => item.thumbnail_url).map(attachment => ({ attachment, entry })),
      )
    : []
  const compared = compare
    .map(id => photos.find(photo => photo.attachment.id === id))
    .filter((photo): photo is Photo => Boolean(photo))
    .sort((a, b) => a.entry.observed_at.localeCompare(b.entry.observed_at))

  const treatmentForm = form && (
    <form className="stack-form health-form" onSubmit={submit}>
      <fieldset disabled={saving}>
        <div className="health-form-grid">
          <label>
            Nome do tratamento
            <input
              required
              autoFocus
              maxLength={160}
              value={form.title}
              onChange={e => setForm({ ...form, title: e.target.value })}
              placeholder="Ex.: Ferida na pata traseira"
            />
          </label>
          <label>
            Região do corpo
            <input
              maxLength={120}
              value={form.body_region}
              onChange={e => setForm({ ...form, body_region: e.target.value })}
              placeholder="Ex.: pata traseira esquerda"
            />
          </label>
          <label>
            Início
            <input
              type="date"
              required
              value={form.started_on}
              onChange={e => setForm({ ...form, started_on: e.target.value })}
            />
          </label>
          <label>
            Encerrado em <small>(opcional)</small>
            <input
              type="date"
              min={form.started_on}
              value={form.ended_on ?? ''}
              onChange={e => setForm({ ...form, ended_on: e.target.value || null })}
            />
          </label>
        </div>
        <label>
          Descrição
          <textarea
            maxLength={2000}
            value={form.description}
            onChange={e => setForm({ ...form, description: e.target.value })}
            placeholder="O que aconteceu e o que está sendo tratado"
          />
        </label>
        <label>
          Orientações recebidas
          <textarea
            maxLength={4000}
            value={form.instructions}
            onChange={e => setForm({ ...form, instructions: e.target.value })}
            placeholder="Ex.: limpar com soro 2x ao dia, colar elizabetano até o retorno"
          />
        </label>
        {formError && <p className="form-error">{formError}</p>}
        <div className="pet-form-actions">
          <button type="button" className="tertiary" onClick={() => setForm(null)}>
            Cancelar
          </button>
          <button className="primary">{saving ? 'Salvando…' : 'Salvar'}</button>
        </div>
      </fieldset>
    </form>
  )

  if (opened)
    return (
      <section className="panel health-section" aria-labelledby="treatment-title">
        <button className="text-button pet-back" onClick={() => setOpenId(null)}>
          ← Todos os tratamentos
        </button>
        <div className="panel-head">
          <div>
            <h2 id="treatment-title">{opened.title}</h2>
            <p>
              {[opened.body_region, `${formatDay(opened.started_on)} → ${opened.ended_on ? formatDay(opened.ended_on) : 'em andamento'}`]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          {!form && (
            <div className="health-head-actions">
              {!opened.ended_on && (
                <button className="tertiary" onClick={() => void finish(opened)}>
                  Encerrar hoje
                </button>
              )}
              <button className="tertiary" onClick={() => startEdit(opened)}>
                Editar
              </button>
              <button className="tertiary danger" onClick={() => void remove(opened)}>
                Apagar
              </button>
            </div>
          )}
        </div>
        {treatmentForm}
        {opened.description && <p className="health-notes">{opened.description}</p>}
        {opened.instructions && (
          <div className="health-instructions">
            <strong>Orientações</strong>
            <p>{opened.instructions}</p>
          </div>
        )}
        {opened.doses.length > 0 && (
          <>
            <h3 className="health-subtitle">Remédios deste tratamento</h3>
            <ul className="health-plain-list">
              {opened.doses.map(dose => (
                <li key={dose.id}>
                  <strong>{dose.name}</strong>
                  <span>
                    {[
                      dose.dose,
                      `${doseKindLabels[dose.kind]} em ${formatDay(dose.given_on)}`,
                      dose.next_due_on && `próxima ${formatDay(dose.next_due_on)}`,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="health-subtitle-row">
          <h3 className="health-subtitle">Evolução</h3>
          {!entryForm && (
            <button
              className="primary"
              onClick={() => {
                setEntryForm({ observed_at: nowLocalInput(), notes: '', files: [] })
                setEntryInputKey(key => key + 1)
                setFormError('')
              }}
            >
              + Registro de hoje
            </button>
          )}
        </div>
        {entryForm && (
          <form className="stack-form health-form" onSubmit={submitEntry}>
            <fieldset disabled={saving}>
              <p className="health-hint">
                Para comparar melhor, fotografe a mesma região, da mesma distância e com luz parecida em todos os dias.
              </p>
              <div className="health-form-grid">
                <label>
                  Quando
                  <input
                    type="datetime-local"
                    required
                    value={entryForm.observed_at}
                    onChange={e => setEntryForm({ ...entryForm, observed_at: e.target.value })}
                  />
                </label>
                <label>
                  Fotos
                  <input
                    key={entryInputKey}
                    type="file"
                    multiple
                    accept={PHOTO_ACCEPT}
                    onChange={e => setEntryForm({ ...entryForm, files: Array.from(e.target.files ?? []) })}
                  />
                </label>
              </div>
              <label>
                Como está
                <textarea
                  maxLength={2000}
                  value={entryForm.notes}
                  onChange={e => setEntryForm({ ...entryForm, notes: e.target.value })}
                  placeholder="Ex.: menos vermelho, sem secreção, lambeu pouco"
                />
              </label>
              {formError && <p className="form-error">{formError}</p>}
              <div className="pet-form-actions">
                <button type="button" className="tertiary" onClick={() => setEntryForm(null)}>
                  Cancelar
                </button>
                <button className="primary">
                  {saving ? (entryForm.files.length ? 'Enviando fotos…' : 'Salvando…') : 'Salvar registro'}
                </button>
              </div>
            </fieldset>
          </form>
        )}
        {photos.length > 1 && (
          <p className="health-hint">Marque duas fotos para compará-las lado a lado.</p>
        )}
        {compared.length === 2 && (
          <div className="health-compare" aria-label="Comparação de fotos">
            {compared.map(photo => (
              <figure key={photo.attachment.id}>
                <img src={photo.attachment.url} alt={`Foto de ${formatInstant(photo.entry.observed_at)}`} />
                <figcaption>{formatInstant(photo.entry.observed_at)}</figcaption>
              </figure>
            ))}
          </div>
        )}
        {!opened.entries.length && !entryForm && (
          <div className="empty">
            <h3>Nenhum registro de evolução</h3>
            <p>Registre como {petName} está, de preferência com foto, para acompanhar a melhora dia a dia.</p>
          </div>
        )}
        <ol className="health-entries">
          {opened.entries.map(entry => (
            <li key={entry.id}>
              <header>
                <strong>{formatInstant(entry.observed_at)}</strong>
                <button className="tertiary danger" onClick={() => void removeEntry(entry)}>
                  Apagar
                </button>
              </header>
              {entry.notes && <p>{entry.notes}</p>}
              {entry.attachments.length > 0 && (
                <div className="health-entry-photos">
                  {entry.attachments.map(attachment => (
                    <figure key={attachment.id} className={compare.includes(attachment.id) ? 'selected' : ''}>
                      <button type="button" className="image-button" onClick={() => setOpenImage(attachment)}>
                        <img src={attachment.thumbnail_url ?? attachment.url} alt={`Foto de ${formatInstant(entry.observed_at)}`} />
                      </button>
                      {photos.length > 1 && (
                        <label>
                          <input
                            type="checkbox"
                            checked={compare.includes(attachment.id)}
                            onChange={() => toggleCompare(attachment.id)}
                          />
                          Comparar
                        </label>
                      )}
                    </figure>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
        {openImage && <Lightbox src={openImage.url} alt={openImage.original_name} onClose={() => setOpenImage(null)} />}
      </section>
    )

  const active = treatments.filter(item => !item.ended_on)
  const finished = treatments.filter(item => item.ended_on)

  function card(treatment: Treatment) {
    const lastEntry = treatment.entries[0]
    const photoCount = treatment.entries.reduce((total, entry) => total + entry.attachments.length, 0)
    return (
      <article className={`health-card ${treatment.ended_on ? '' : 'current'}`} key={treatment.id}>
        <header>
          <div>
            <h3>{treatment.title}</h3>
            <p>{treatment.body_region || 'Sem região informada'}</p>
          </div>
          {!treatment.ended_on && <span className="health-tag">Em andamento</span>}
        </header>
        <p className="health-period">
          {formatDay(treatment.started_on)} → {treatment.ended_on ? formatDay(treatment.ended_on) : 'hoje'}
        </p>
        <p className="health-notes">
          {treatment.entries.length} registro(s) · {photoCount} foto(s) · {treatment.doses.length} aplicação(ões)
          {lastEntry && ` · último em ${formatInstant(lastEntry.observed_at)}`}
        </p>
        <footer>
          <button className="secondary" onClick={() => setOpenId(treatment.id)}>
            Abrir
          </button>
        </footer>
      </article>
    )
  }

  return (
    <section className="panel health-section" aria-labelledby="treatments-title">
      <div className="panel-head">
        <div>
          <h2 id="treatments-title">Tratamentos</h2>
          <p>Feridas, doenças e recuperações de {petName}, com fotos da evolução e os remédios usados.</p>
        </div>
        {!form && (
          <button className="primary" onClick={startCreate}>
            + Tratamento
          </button>
        )}
      </div>
      {treatmentForm}
      <SectionState
        loading={loading}
        error={error}
        empty={!treatments.length && !form}
        emptyTitle="Nenhum tratamento registrado"
        emptyText="Crie um tratamento para guardar orientações, remédios e fotos diárias da evolução."
      />
      {active.length > 0 && (
        <>
          <h3 className="health-subtitle">Em andamento</h3>
          <div className="health-cards">{active.map(card)}</div>
        </>
      )}
      {finished.length > 0 && (
        <>
          <h3 className="health-subtitle">Encerrados</h3>
          <div className="health-cards">{finished.map(card)}</div>
        </>
      )}
    </section>
  )
}
