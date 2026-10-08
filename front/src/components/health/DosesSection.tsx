import { FormEvent, useCallback, useState } from 'react'
import * as api from '../../api'
import type { Dose, DoseKind, DosePayload, Treatment } from '../../api'
import { errorMessage } from '../../lib/errors'
import { doseKindLabels } from '../../lib/labels'
import { useToast } from '../useToast'
import { SectionState, dueLabel, formatDay, shiftDays, todayIso, useLoader } from './shared'

type Props = { petId: string; petName: string; onChanged: () => void }
type Loaded = { doses: Dose[]; treatments: Treatment[] }

const NEXT_DOSE_SHORTCUTS: [string, number][] = [
  ['+1 dia', 1],
  ['+7 dias', 7],
  ['+30 dias', 30],
  ['+1 ano', 365],
]

const emptyDose = (kind: DoseKind = 'VACCINE'): DosePayload => ({
  kind,
  name: '',
  dose: '',
  given_on: todayIso(),
  next_due_on: null,
  notes: '',
  treatment_id: null,
})

function daysUntil(day: string): number {
  const [year, month, date] = day.split('-').map(Number)
  const [ty, tm, td] = todayIso().split('-').map(Number)
  return Math.round((Date.UTC(year, month - 1, date) - Date.UTC(ty, tm - 1, td)) / 86_400_000)
}

export default function DosesSection({ petId, petName, onChanged }: Props) {
  const showToast = useToast()
  const load = useCallback(async (): Promise<Loaded> => {
    const [doses, treatments] = await Promise.all([api.getDoses(petId), api.getTreatments(petId)])
    return { doses, treatments }
  }, [petId])
  const { data, loading, error, reload } = useLoader<Loaded>(load, { doses: [], treatments: [] }, 'Não foi possível carregar vacinas e remédios.')
  const [form, setForm] = useState<DosePayload | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const latest = new Map<string, Dose>()
  for (const dose of data.doses) {
    const key = `${dose.kind}:${dose.name.trim().toLowerCase()}`
    const current = latest.get(key)
    if (!current || dose.given_on > current.given_on) latest.set(key, dose)
  }
  const upcoming = [...latest.values()]
    .filter(dose => dose.next_due_on)
    .sort((a, b) => (a.next_due_on ?? '').localeCompare(b.next_due_on ?? ''))

  function startCreate(base?: Partial<DosePayload>) {
    setEditingId(null)
    setForm({ ...emptyDose(), ...base })
    setFormError('')
  }

  function startEdit(dose: Dose) {
    setEditingId(dose.id)
    setForm({
      kind: dose.kind,
      name: dose.name,
      dose: dose.dose,
      given_on: dose.given_on,
      next_due_on: dose.next_due_on,
      notes: dose.notes,
      treatment_id: dose.treatment_id,
    })
    setFormError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form || saving) return
    setSaving(true)
    setFormError('')
    try {
      const payload = { ...form, next_due_on: form.next_due_on || null, treatment_id: form.treatment_id || null }
      if (editingId) await api.updateDose(petId, editingId, payload)
      else await api.createDose(petId, payload)
      setForm(null)
      reload()
      onChanged()
      showToast(editingId ? 'Aplicação atualizada.' : 'Aplicação registrada.')
    } catch (reason) {
      setFormError(errorMessage(reason, 'Não foi possível salvar a aplicação.'))
    } finally {
      setSaving(false)
    }
  }

  async function remove(dose: Dose) {
    if (!window.confirm(`Apagar a aplicação de ${dose.name} em ${formatDay(dose.given_on)}?`)) return
    try {
      await api.deleteHealthRecord(petId, 'doses', dose.id)
      reload()
      onChanged()
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível apagar a aplicação.'), 'error')
    }
  }

  const treatmentName = (id: string | null) => data.treatments.find(item => item.id === id)?.title

  return (
    <section className="panel health-section" aria-labelledby="doses-title">
      <div className="panel-head">
        <div>
          <h2 id="doses-title">Vacinas e remédios</h2>
          <p>Aplicações de {petName} e quando é a próxima dose.</p>
        </div>
        {!form && (
          <button className="primary" onClick={() => startCreate()}>
            + Aplicação
          </button>
        )}
      </div>
      {form && (
        <form className="stack-form health-form" onSubmit={submit}>
          <fieldset disabled={saving}>
            <div className="health-form-grid">
              <label>
                Tipo
                <select value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value as DoseKind })}>
                  {Object.entries(doseKindLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Nome
                <input
                  required
                  autoFocus
                  maxLength={160}
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder={form.kind === 'VACCINE' ? 'Ex.: V4 (quádrupla felina)' : 'Ex.: Meloxicam'}
                />
              </label>
              <label>
                Dose
                <input
                  maxLength={120}
                  value={form.dose}
                  onChange={e => setForm({ ...form, dose: e.target.value })}
                  placeholder="Ex.: 0,5 ml ou 1/2 comprimido"
                />
              </label>
              <label>
                Aplicado em
                <input
                  type="date"
                  required
                  value={form.given_on}
                  onChange={e => setForm({ ...form, given_on: e.target.value })}
                />
              </label>
              <label>
                Próxima dose <small>(opcional)</small>
                <input
                  type="date"
                  min={form.given_on}
                  value={form.next_due_on ?? ''}
                  onChange={e => setForm({ ...form, next_due_on: e.target.value || null })}
                />
                <span className="health-shortcuts">
                  {NEXT_DOSE_SHORTCUTS.map(([label, days]) => (
                    <button
                      type="button"
                      key={label}
                      onClick={() => setForm({ ...form, next_due_on: shiftDays(form.given_on, days) })}
                    >
                      {label}
                    </button>
                  ))}
                </span>
              </label>
              <label>
                Faz parte do tratamento
                <select
                  value={form.treatment_id ?? ''}
                  onChange={e => setForm({ ...form, treatment_id: e.target.value || null })}
                >
                  <option value="">Nenhum</option>
                  {data.treatments.map(treatment => (
                    <option key={treatment.id} value={treatment.id}>
                      {treatment.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Observações
              <textarea
                maxLength={1000}
                value={form.notes}
                onChange={e => setForm({ ...form, notes: e.target.value })}
                placeholder="Ex.: lote, clínica, reação depois da aplicação"
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
      )}
      <SectionState
        loading={loading}
        error={error}
        empty={!data.doses.length && !form}
        emptyTitle="Nenhuma aplicação registrada"
        emptyText="Registre vacinas, vermífugos e remédios. Com a data da próxima dose, o app avisa quando estiver chegando."
      />
      {upcoming.length > 0 && (
        <>
          <h3 className="health-subtitle">Próximas doses</h3>
          <ul className="health-due-list">
            {upcoming.map(dose => {
              const days = daysUntil(dose.next_due_on ?? '')
              return (
                <li key={dose.id} className={days < 0 ? 'overdue' : days <= 14 ? 'soon' : ''}>
                  <div>
                    <strong>{dose.name}</strong>
                    <span>
                      {doseKindLabels[dose.kind]} · {formatDay(dose.next_due_on)} · {dueLabel(days)}
                    </span>
                  </div>
                  <button
                    className="secondary"
                    onClick={() =>
                      startCreate({ kind: dose.kind, name: dose.name, dose: dose.dose, treatment_id: dose.treatment_id })
                    }
                  >
                    Registrar aplicação
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}
      {data.doses.length > 0 && (
        <>
          <h3 className="health-subtitle">Histórico</h3>
          <table className="health-table">
            <caption>Aplicações</caption>
            <thead>
              <tr>
                <th>Data</th>
                <th>Aplicação</th>
                <th>Próxima</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {data.doses.map(dose => (
                <tr key={dose.id}>
                  <td>{formatDay(dose.given_on)}</td>
                  <td>
                    <strong>{dose.name}</strong>
                    <small>
                      {[doseKindLabels[dose.kind], dose.dose, treatmentName(dose.treatment_id), dose.notes]
                        .filter(Boolean)
                        .join(' · ')}
                    </small>
                  </td>
                  <td>{dose.next_due_on ? formatDay(dose.next_due_on) : '—'}</td>
                  <td className="health-row-actions">
                    <button className="tertiary" onClick={() => startEdit(dose)}>
                      Editar
                    </button>
                    <button className="tertiary danger" onClick={() => void remove(dose)}>
                      Apagar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
