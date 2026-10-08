import { FormEvent, useCallback, useState } from 'react'
import * as api from '../../api'
import type { FoodPayload, FoodPeriod, FoodType } from '../../api'
import { errorMessage } from '../../lib/errors'
import { foodTypeLabels } from '../../lib/labels'
import { useToast } from '../useToast'
import { SectionState, formatDay, todayIso, useLoader } from './shared'

type Props = { petId: string; petName: string; onChanged: () => void }

const emptyFood = (): FoodPayload => ({
  name: '',
  brand: '',
  food_type: 'DRY',
  offered_amount: '',
  started_on: todayIso(),
  ended_on: null,
  notes: '',
  replace_current: true,
})

export default function FoodSection({ petId, petName, onChanged }: Props) {
  const showToast = useToast()
  const load = useCallback(() => api.getFoodPeriods(petId), [petId])
  const { data: periods, loading, error, reload } = useLoader<FoodPeriod[]>(load, [], 'Não foi possível carregar a alimentação.')
  const [form, setForm] = useState<FoodPayload | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const today = todayIso()
  const current = periods.filter(item => item.started_on <= today && (!item.ended_on || item.ended_on >= today))
  const past = periods.filter(item => !current.includes(item))

  function startCreate() {
    setEditingId(null)
    setForm(emptyFood())
    setFormError('')
  }

  function startEdit(period: FoodPeriod) {
    setEditingId(period.id)
    setForm({ ...period, replace_current: false })
    setFormError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form || saving) return
    setSaving(true)
    setFormError('')
    try {
      const payload = { ...form, ended_on: form.ended_on || null }
      if (editingId) await api.updateFoodPeriod(petId, editingId, payload)
      else await api.createFoodPeriod(petId, payload)
      setForm(null)
      reload()
      onChanged()
      showToast(editingId ? 'Alimento atualizado.' : 'Alimento registrado.')
    } catch (reason) {
      setFormError(errorMessage(reason, 'Não foi possível salvar o alimento.'))
    } finally {
      setSaving(false)
    }
  }

  async function finish(period: FoodPeriod) {
    try {
      await api.updateFoodPeriod(petId, period.id, { ...period, ended_on: today })
      reload()
      onChanged()
      showToast(`${period.name} encerrado hoje.`)
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível encerrar o alimento.'), 'error')
    }
  }

  async function remove(period: FoodPeriod) {
    if (!window.confirm(`Apagar o registro de ${period.name}? O histórico desse período será perdido.`)) return
    try {
      await api.deleteHealthRecord(petId, 'food', period.id)
      reload()
      onChanged()
      showToast('Registro apagado.')
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível apagar o registro.'), 'error')
    }
  }

  function card(period: FoodPeriod, active: boolean) {
    const details = [period.brand, foodTypeLabels[period.food_type], period.offered_amount && `${period.offered_amount} oferecido`]
    return (
      <article className={`health-card ${active ? 'current' : ''}`} key={period.id}>
        <header>
          <div>
            <h3>{period.name}</h3>
            <p>{details.filter(Boolean).join(' · ')}</p>
          </div>
          {active && <span className="health-tag">Atual</span>}
        </header>
        <p className="health-period">
          {formatDay(period.started_on)} → {period.ended_on ? formatDay(period.ended_on) : 'hoje'}
        </p>
        {period.notes && <p className="health-notes">{period.notes}</p>}
        <footer>
          {active && !period.ended_on && (
            <button className="tertiary" onClick={() => void finish(period)}>
              Encerrar hoje
            </button>
          )}
          <button className="tertiary" onClick={() => startEdit(period)}>
            Editar
          </button>
          <button className="tertiary danger" onClick={() => void remove(period)}>
            Apagar
          </button>
        </footer>
      </article>
    )
  }

  return (
    <section className="panel health-section" aria-labelledby="food-title">
      <div className="panel-head">
        <div>
          <h2 id="food-title">Alimentação</h2>
          <p>O que {petName} come e quando cada alimento começou e parou.</p>
        </div>
        {!form && (
          <button className="primary" onClick={startCreate}>
            + Alimento
          </button>
        )}
      </div>
      {form && (
        <form className="stack-form health-form" onSubmit={submit}>
          <fieldset disabled={saving}>
            <div className="health-form-grid">
              <label>
                Alimento
                <input
                  required
                  autoFocus
                  maxLength={120}
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="Ex.: Urinary S/O"
                />
              </label>
              <label>
                Marca
                <input
                  maxLength={120}
                  value={form.brand}
                  onChange={e => setForm({ ...form, brand: e.target.value })}
                  placeholder="Ex.: Royal Canin"
                />
              </label>
              <label>
                Tipo
                <select
                  value={form.food_type}
                  onChange={e => setForm({ ...form, food_type: e.target.value as FoodType })}
                >
                  {Object.entries(foodTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Quantidade oferecida
                <input
                  maxLength={80}
                  value={form.offered_amount}
                  onChange={e => setForm({ ...form, offered_amount: e.target.value })}
                  placeholder="Ex.: 60 g por dia"
                />
              </label>
              <label>
                Começou em
                <input
                  type="date"
                  required
                  value={form.started_on}
                  onChange={e => setForm({ ...form, started_on: e.target.value })}
                />
              </label>
              <label>
                Parou em <small>(opcional)</small>
                <input
                  type="date"
                  value={form.ended_on ?? ''}
                  min={form.started_on}
                  onChange={e => setForm({ ...form, ended_on: e.target.value || null })}
                />
              </label>
            </div>
            <label>
              Observações
              <textarea
                maxLength={1000}
                value={form.notes}
                onChange={e => setForm({ ...form, notes: e.target.value })}
                placeholder="Ex.: troca indicada pela veterinária por causa do cálculo urinário"
              />
            </label>
            {!editingId && current.some(item => !item.ended_on) && (
              <label className="health-check">
                <input
                  type="checkbox"
                  checked={Boolean(form.replace_current)}
                  onChange={e => setForm({ ...form, replace_current: e.target.checked })}
                />
                Substitui o que {petName} come hoje (encerra os alimentos atuais na data de início)
              </label>
            )}
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
        empty={!periods.length && !form}
        emptyTitle="Nenhum alimento registrado"
        emptyText="Registre a ração atual. Ao trocar, o período anterior fica guardado no histórico."
      />
      {current.length > 0 && (
        <>
          <h3 className="health-subtitle">Hoje</h3>
          <div className="health-cards">{current.map(item => card(item, true))}</div>
        </>
      )}
      {past.length > 0 && (
        <>
          <h3 className="health-subtitle">Histórico</h3>
          <div className="health-cards">{past.map(item => card(item, false))}</div>
        </>
      )}
    </section>
  )
}
