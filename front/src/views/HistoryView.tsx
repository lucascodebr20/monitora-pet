import { useEffect, useState } from 'react'
import * as api from '../api'
import type { EventPage, Pet, Zone } from '../api'
import DateRangePicker from '../components/DateRangePicker'
import EventList from '../components/EventList'
import Icon from '../components/Icon'
import PetAvatar from '../components/PetAvatar'
import { errorMessage } from '../lib/errors'
import { zoneIcon, zoneLabels } from '../lib/labels'
import { pageWindow } from '../lib/pagination'

type Props = { pets: Pet[]; reloadToken: number }

const PAGE_SIZE = 10

export default function HistoryView({ pets, reloadToken }: Props) {
  const [page, setPage] = useState(1)
  const [petId, setPetId] = useState('')
  const [zoneType, setZoneType] = useState<Zone['type'] | ''>('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [result, setResult] = useState<EventPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    void api
      .getEventPage(page, petId, zoneType, PAGE_SIZE, startDate, endDate)
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
  }, [page, petId, zoneType, startDate, endDate, reloadToken])

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

  function choosePeriod(start: string, end: string) {
    setStartDate(start)
    setEndDate(end)
    setPage(1)
  }

  function periodLabel(): string {
    const format = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR')
    if (startDate && endDate) return `${format(startDate)} – ${format(endDate)}`
    if (startDate) return `A partir de ${format(startDate)}`
    if (endDate) return `Até ${format(endDate)}`
    return 'Todos os períodos'
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
        <div className="history-primary-filters">
          <div className="filter-chip-row">
            <span className="filter-chip-label">Pet</span>
            <div className="filter-chip-options pet-chip-options" role="group" aria-label="Filtrar por pet">
              <button
                className={petId === '' ? 'selected' : ''}
                aria-pressed={petId === ''}
                onClick={() => choosePet('')}
              >
                <span className="all-pets pet-avatar">
                  <Icon name="pets" />
                </span>
                Todos os pets
              </button>
              {pets.map(pet => (
                <button
                  key={pet.id}
                  className={petId === pet.id ? 'selected' : ''}
                  aria-pressed={petId === pet.id}
                  onClick={() => choosePet(pet.id)}
                >
                  <PetAvatar pet={pet} />
                  {pet.name}
                </button>
              ))}
            </div>
          </div>
          <div className="history-period-filter">
            <span className="filter-chip-label">Período</span>
            <DateRangePicker startDate={startDate} endDate={endDate} onChange={choosePeriod} />
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
          <span className="muted">{periodLabel()}</span>
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
