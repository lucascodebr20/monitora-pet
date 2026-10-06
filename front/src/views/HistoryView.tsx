import { useEffect, useState } from 'react'
import * as api from '../api'
import type { EventPage, Pet, Zone } from '../api'
import EventList from '../components/EventList'
import Icon from '../components/Icon'
import { errorMessage } from '../lib/errors'
import { zoneIcon, zoneLabels } from '../lib/labels'
import { pageWindow } from '../lib/pagination'

type Props = { pets: Pet[]; reloadToken: number }

const PAGE_SIZE = 10

export default function HistoryView({ pets, reloadToken }: Props) {
  const [page, setPage] = useState(1)
  const [petId, setPetId] = useState('')
  const [zoneType, setZoneType] = useState<Zone['type'] | ''>('')
  const [date, setDate] = useState('')
  const [result, setResult] = useState<EventPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    void api
      .getEventPage(page, petId, zoneType, PAGE_SIZE, date)
      .then(data => {
        if (active) {
          setResult(data)
          setError('')
        }
      })
      .catch(reason => {
        if (active) setError(errorMessage(reason, 'Não foi possível carregar o histórico.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [page, petId, zoneType, date, reloadToken])

  const total = result?.total ?? 0
  const pageSize = result?.page_size ?? PAGE_SIZE
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const start = total ? (page - 1) * pageSize + 1 : 0
  const end = Math.min(page * pageSize, total)
  const pages = pageWindow(page, pageCount)

  function choosePet(id: string) {
    setPetId(id)
    setPage(1)
  }

  function chooseZone(type: Zone['type'] | '') {
    setZoneType(type)
    setPage(1)
  }

  function chooseDate(value: string) {
    setDate(value)
    setPage(1)
  }

  function shiftDate(days: number) {
    const base = date ? new Date(`${date}T12:00:00`) : new Date()
    base.setDate(base.getDate() + days)
    chooseDate(base.toISOString().slice(0, 10))
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">REGISTROS</p>
          <h1>Histórico</h1>
          <p>Consulte as visitas detectadas pelo sistema.</p>
        </div>
      </div>
      <section className="history-filter-panel" aria-label="Filtros do histórico">
        <div className="filter-chip-row">
          <span className="filter-chip-label">Pet</span>
          <div className="filter-chip-options" role="group" aria-label="Filtrar por pet">
            {[{ id: '', name: 'Todos os pets' }, ...pets].map(pet => (
              <button
                key={pet.id || 'all'}
                className={petId === pet.id ? 'selected' : ''}
                aria-pressed={petId === pet.id}
                onClick={() => choosePet(pet.id)}
              >
                {pet.name}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-chip-row">
          <span className="filter-chip-label">Dia</span>
          <div className="filter-chip-options history-date" role="group" aria-label="Filtrar por dia">
            <button className={date ? '' : 'selected'} aria-pressed={!date} onClick={() => chooseDate('')}>
              Todos os dias
            </button>
            <button type="button" aria-label="Dia anterior" onClick={() => shiftDate(-1)}>
              ‹
            </button>
            <input
              type="date"
              value={date}
              max={new Date().toISOString().slice(0, 10)}
              onChange={event => chooseDate(event.target.value)}
              aria-label="Escolher dia"
            />
            <button type="button" aria-label="Dia seguinte" disabled={!date} onClick={() => shiftDate(1)}>
              ›
            </button>
          </div>
        </div>
        <div className="filter-chip-row">
          <span className="filter-chip-label">Área</span>
          <div className="filter-chip-options" role="group" aria-label="Filtrar por área">
            {([['', 'Todas as áreas'], ...Object.entries(zoneLabels)] as [Zone['type'] | '', string][]).map(
              ([value, label]) => (
                <button
                  key={value || 'all'}
                  className={zoneType === value ? 'selected' : ''}
                  aria-pressed={zoneType === value}
                  onClick={() => chooseZone(value)}
                >
                  {value && <Icon name={zoneIcon(value)} />} {label}
                </button>
              ),
            )}
          </div>
        </div>
      </section>
      <section className="panel">
        <div className="panel-head">
          <h2>{total} registros</h2>
          <span className="muted">
            {date ? new Date(`${date}T12:00:00`).toLocaleDateString('pt-BR') : 'Todos os períodos'}
          </span>
        </div>
        {error && <p className="form-error">{error}</p>}
        {loading && !result ? (
          <p className="loading">Carregando histórico…</p>
        ) : (
          <EventList events={result?.events ?? []} />
        )}
        {total > 0 && (
          <div className="history-pagination">
            <p className="pagination-summary" aria-live="polite">
              Mostrando{' '}
              <strong>
                {start}–{end}
              </strong>{' '}
              de <strong>{total}</strong> registros
            </p>
            <nav className="pagination-controls" aria-label="Páginas do histórico">
              <button className="secondary" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>
                Anterior
              </button>
              {pages.map((value, index) => (
                <span className="pagination-item" key={value}>
                  {index > 0 && value - pages[index - 1] > 1 && (
                    <span className="pagination-ellipsis" aria-hidden="true">
                      …
                    </span>
                  )}
                  <button
                    className="pagination-number"
                    aria-label={`Página ${value}`}
                    aria-current={value === page ? 'page' : undefined}
                    disabled={loading}
                    onClick={() => setPage(value)}
                  >
                    {value}
                  </button>
                </span>
              ))}
              <button className="secondary" disabled={page >= pageCount || loading} onClick={() => setPage(page + 1)}>
                Próxima
              </button>
            </nav>
          </div>
        )}
      </section>
    </>
  )
}
