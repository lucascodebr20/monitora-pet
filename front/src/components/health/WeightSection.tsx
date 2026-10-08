import { FormEvent, PointerEvent, useCallback, useMemo, useState } from 'react'
import * as api from '../../api'
import type { WeightPayload, WeightRecord } from '../../api'
import { errorMessage } from '../../lib/errors'
import { useToast } from '../useToast'
import { SectionState, formatDay, formatWeight, todayIso, useLoader } from './shared'

type Props = { petId: string; petName: string; onChanged: () => void }

const WIDTH = 640
const HEIGHT = 220
const PAD = { top: 18, right: 64, bottom: 30, left: 48 }
const DAY_MS = 86_400_000

const dayValue = (day: string) => {
  const [year, month, date] = day.split('-').map(Number)
  return Date.UTC(year, month - 1, date)
}

function WeightChart({ records }: { records: WeightRecord[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const points = useMemo(() => {
    const sorted = [...records].sort((a, b) => a.measured_on.localeCompare(b.measured_on))
    const times = sorted.map(item => dayValue(item.measured_on))
    const weights = sorted.map(item => item.weight_kg)
    const first = times[0]
    const last = Math.max(times[times.length - 1], first + DAY_MS)
    const spread = Math.max(...weights) - Math.min(...weights)
    const margin = Math.max(spread * 0.25, 0.1)
    const low = Math.min(...weights) - margin
    const high = Math.max(...weights) + margin
    const x = (time: number) => PAD.left + ((time - first) / (last - first)) * (WIDTH - PAD.left - PAD.right)
    const y = (kg: number) => PAD.top + (1 - (kg - low) / (high - low)) * (HEIGHT - PAD.top - PAD.bottom)
    const ticks = [low + margin, (low + high) / 2, high - margin]
    return {
      sorted,
      coords: sorted.map((item, index) => ({ x: sorted.length === 1 ? (WIDTH - PAD.right + PAD.left) / 2 : x(times[index]), y: y(item.weight_kg) })),
      ticks: ticks.map(value => ({ value, y: y(value) })),
    }
  }, [records])

  function track(event: PointerEvent<SVGSVGElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const position = ((event.clientX - box.left) / box.width) * WIDTH
    let nearest = 0
    points.coords.forEach((coord, index) => {
      if (Math.abs(coord.x - position) < Math.abs(points.coords[nearest].x - position)) nearest = index
    })
    setHover(nearest)
  }

  const path = points.coords.map((coord, index) => `${index ? 'L' : 'M'}${coord.x.toFixed(1)},${coord.y.toFixed(1)}`).join(' ')
  const lastIndex = points.coords.length - 1
  const active = hover ?? null
  const first = points.sorted[0]
  const final = points.sorted[lastIndex]

  return (
    <figure className="weight-chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Evolução do peso de ${formatWeight(first.weight_kg)} em ${formatDay(first.measured_on)} para ${formatWeight(final.weight_kg)} em ${formatDay(final.measured_on)}`}
        onPointerMove={track}
        onPointerLeave={() => setHover(null)}
      >
        {points.ticks.map(tick => (
          <g key={tick.value} className="weight-grid">
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={tick.y} y2={tick.y} />
            <text x={PAD.left - 8} y={tick.y} dominantBaseline="middle" textAnchor="end">
              {tick.value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}
            </text>
          </g>
        ))}
        <text className="weight-axis" x={PAD.left} y={HEIGHT - 8}>
          {formatDay(first.measured_on)}
        </text>
        {lastIndex > 0 && (
          <text className="weight-axis" x={WIDTH - PAD.right} y={HEIGHT - 8} textAnchor="end">
            {formatDay(final.measured_on)}
          </text>
        )}
        {active !== null && (
          <line
            className="weight-crosshair"
            x1={points.coords[active].x}
            x2={points.coords[active].x}
            y1={PAD.top}
            y2={HEIGHT - PAD.bottom}
          />
        )}
        <path className="weight-line" d={path} />
        {points.coords.map((coord, index) => (
          <circle
            key={points.sorted[index].id}
            className={`weight-point ${index === active ? 'active' : ''}`}
            cx={coord.x}
            cy={coord.y}
            r={index === active ? 6 : 4.5}
          />
        ))}
        <text className="weight-label" x={points.coords[lastIndex].x + 10} y={points.coords[lastIndex].y} dominantBaseline="middle">
          {formatWeight(final.weight_kg)}
        </text>
      </svg>
      {active !== null && (
        <div
          className="weight-tooltip"
          style={{ left: `${(points.coords[active].x / WIDTH) * 100}%`, top: `${(points.coords[active].y / HEIGHT) * 100}%` }}
        >
          <strong>{formatWeight(points.sorted[active].weight_kg)}</strong>
          <span>{formatDay(points.sorted[active].measured_on)}</span>
        </div>
      )}
    </figure>
  )
}

export default function WeightSection({ petId, petName, onChanged }: Props) {
  const showToast = useToast()
  const load = useCallback(() => api.getWeights(petId), [petId])
  const { data: weights, loading, error, reload } = useLoader<WeightRecord[]>(load, [], 'Não foi possível carregar o peso.')
  const [form, setForm] = useState<WeightPayload>({ measured_on: todayIso(), weight_kg: 0, notes: '' })
  const [weightText, setWeightText] = useState('')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    const weight = Number(weightText.replace(',', '.'))
    if (!Number.isFinite(weight) || weight <= 0) {
      setFormError('Informe o peso em kg, por exemplo 4,2.')
      return
    }
    setSaving(true)
    setFormError('')
    try {
      await api.createWeight(petId, { ...form, weight_kg: weight })
      setWeightText('')
      setForm({ measured_on: todayIso(), weight_kg: 0, notes: '' })
      reload()
      onChanged()
      showToast('Pesagem registrada.')
    } catch (reason) {
      setFormError(errorMessage(reason, 'Não foi possível registrar o peso.'))
    } finally {
      setSaving(false)
    }
  }

  async function remove(record: WeightRecord) {
    if (!window.confirm(`Apagar a pesagem de ${formatDay(record.measured_on)}?`)) return
    try {
      await api.deleteHealthRecord(petId, 'weights', record.id)
      reload()
      onChanged()
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível apagar a pesagem.'), 'error')
    }
  }

  return (
    <section className="panel health-section" aria-labelledby="weight-title">
      <div className="panel-head">
        <div>
          <h2 id="weight-title">Peso</h2>
          <p>Pesagens de {petName} ao longo do tempo.</p>
        </div>
      </div>
      <form className="health-inline-form" onSubmit={submit}>
        <fieldset disabled={saving}>
          <label>
            Data
            <input
              type="date"
              required
              max={todayIso()}
              value={form.measured_on}
              onChange={e => setForm({ ...form, measured_on: e.target.value })}
            />
          </label>
          <label>
            Peso (kg)
            <input
              required
              inputMode="decimal"
              value={weightText}
              onChange={e => setWeightText(e.target.value)}
              placeholder="4,2"
            />
          </label>
          <label className="grow">
            Observação
            <input
              maxLength={500}
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
              placeholder="Ex.: pesado na clínica"
            />
          </label>
          <button className="primary">{saving ? 'Salvando…' : 'Registrar'}</button>
        </fieldset>
        {formError && <p className="form-error">{formError}</p>}
      </form>
      <SectionState
        loading={loading}
        error={error}
        empty={!weights.length}
        emptyTitle="Nenhuma pesagem ainda"
        emptyText="Registre o peso sempre que pesar em casa ou na clínica para acompanhar a evolução."
      />
      {weights.length > 0 && (
        <div className="weight-layout">
          <WeightChart records={weights} />
          <table className="health-table">
            <caption>Pesagens</caption>
            <thead>
              <tr>
                <th>Data</th>
                <th>Peso</th>
                <th>Variação</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {weights.map((record, index) => {
                const previous = weights[index + 1]
                const delta = previous ? record.weight_kg - previous.weight_kg : null
                return (
                  <tr key={record.id}>
                    <td>
                      {formatDay(record.measured_on)}
                      {record.notes && <small>{record.notes}</small>}
                    </td>
                    <td>{formatWeight(record.weight_kg)}</td>
                    <td>
                      {delta === null
                        ? '—'
                        : `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${formatWeight(Math.abs(delta))}`}
                    </td>
                    <td>
                      <button className="tertiary danger" onClick={() => void remove(record)}>
                        Apagar
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
