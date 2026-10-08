import { FormEvent, useCallback, useEffect, useState } from 'react'
import * as api from '../api'
import type { AppSettings, HouseholdSpecies, IdentificationLogs, PetSpecies } from '../api'
import BrandMark from '../components/BrandMark'
import HouseholdArt from '../components/HouseholdArt'
import Icon from '../components/Icon'
import { errorMessage } from '../lib/errors'
import { formatDateTime, identificationDecisionLabels } from '../lib/labels'
import { householdOptions } from '../lib/household'
import { pageWindow } from '../lib/pagination'
import { useHousehold } from '../lib/useHousehold'

type Section = 'general' | 'identification'

const CALIBRATION_INTERVAL = 10
const DEFAULT_SIMILARITY = 0.72
const DEFAULT_MARGIN = 0.08

type Props = { version: string; settings: AppSettings | null; onSettings: (settings: AppSettings) => void }

export default function SettingsView({ version, settings: appSettings, onSettings }: Props) {
  const { hasCats, hasDogs } = useHousehold()
  const [section, setSection] = useState<Section>('general')
  const [logs, setLogs] = useState<IdentificationLogs | null>(null)
  const [logPage, setLogPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [retention, setRetention] = useState('7')
  const [savingRetention, setSavingRetention] = useState(false)
  const [retentionMessage, setRetentionMessage] = useState('')
  const [savingRetentionToggle, setSavingRetentionToggle] = useState(false)
  const [savingHousehold, setSavingHousehold] = useState(false)
  const [householdMessage, setHouseholdMessage] = useState('')

  const retentionDays = appSettings?.retention_days

  useEffect(() => {
    if (retentionDays !== undefined) setRetention(String(retentionDays))
  }, [retentionDays])

  async function saveRetention(event: FormEvent) {
    event.preventDefault()
    const days = Number(retention)
    if (!Number.isInteger(days) || days < 1 || days > 365) {
      setRetentionMessage('Informe um número de dias entre 1 e 365.')
      return
    }
    setSavingRetention(true)
    setRetentionMessage('')
    try {
      const saved = await api.updateSettings({ retention_days: days })
      onSettings(saved)
      setRetentionMessage('Retenção salva.')
    } catch (reason) {
      setRetentionMessage(errorMessage(reason, 'Não foi possível salvar.'))
    } finally {
      setSavingRetention(false)
    }
  }

  async function toggleRetention(enabled: boolean) {
    if (savingRetentionToggle || !appSettings) return
    setSavingRetentionToggle(true)
    setRetentionMessage('')
    try {
      onSettings(await api.updateSettings({ retention_enabled: enabled }))
      setRetentionMessage(enabled ? 'Limpeza automática ativada.' : 'Limpeza automática desativada. Nada será apagado.')
    } catch (reason) {
      setRetentionMessage(errorMessage(reason, 'Não foi possível salvar.'))
    } finally {
      setSavingRetentionToggle(false)
    }
  }

  async function saveHousehold(value: HouseholdSpecies) {
    if (savingHousehold || value === appSettings?.household_species) return
    setSavingHousehold(true)
    setHouseholdMessage('')
    try {
      const saved = await api.updateSettings({ household_species: value })
      onSettings(saved)
      setHouseholdMessage('Preferência salva. A interface já foi adaptada.')
    } catch (reason) {
      setHouseholdMessage(errorMessage(reason, 'Não foi possível salvar.'))
    } finally {
      setSavingHousehold(false)
    }
  }

  const loadLogs = useCallback(async (page: number) => {
    setLoading(true)
    setLoadError('')
    try {
      setLogs(await api.getIdentificationLogs(page))
      setLogPage(page)
    } catch (reason) {
      setLoadError(errorMessage(reason, 'Não foi possível carregar os logs.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (section === 'identification' && logs === null) void loadLogs(1)
  }, [section, logs, loadLogs])

  const speciesInHousehold = (['CAT', 'DOG'] as PetSpecies[]).filter(species => (species === 'CAT' ? hasCats : hasDogs))
  const logTotal = logs?.total ?? 0
  const logPageSize = logs?.page_size ?? 10
  const logPageCount = Math.max(1, Math.ceil(logTotal / logPageSize))
  const logStart = logTotal ? (logPage - 1) * logPageSize + 1 : 0
  const logEnd = Math.min(logPage * logPageSize, logTotal)
  const logPages = pageWindow(logPage, logPageCount)

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">SISTEMA</p>
          <h1>Configurações</h1>
          <p>Preferências e transparência do monitoramento local.</p>
        </div>
      </div>
      <nav className="settings-navigation" aria-label="Opções de configurações">
        <button className={section === 'general' ? 'selected' : ''} onClick={() => setSection('general')}>
          <Icon name="settings" />
          Geral
        </button>
        <button className={section === 'identification' ? 'selected' : ''} onClick={() => setSection('identification')}>
          <Icon name="activity" />
          Logs de identificação
        </button>
      </nav>
      {section === 'general' ? (
        <div className="settings-panels">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Quem mora com você</h2>
                <p>Define as áreas, os nomes e o cadastro de pets que a interface mostra.</p>
              </div>
            </div>
            <fieldset className="household-options compact" disabled={savingHousehold || appSettings === null}>
              <legend className="sr-only">Espécies da casa</legend>
              {householdOptions.map(option => (
                <label
                  className={`household-option ${appSettings?.household_species === option.value ? 'chosen' : ''}`}
                  key={option.value}
                >
                  <input
                    type="radio"
                    name="settings-household"
                    value={option.value}
                    checked={appSettings?.household_species === option.value}
                    onChange={() => void saveHousehold(option.value)}
                  />
                  <span className="household-art">
                    <HouseholdArt household={option.value} size={30} />
                  </span>
                  <span>
                    <strong>{option.title}</strong>
                    <small>{option.description}</small>
                  </span>
                </label>
              ))}
            </fieldset>
            {householdMessage && (
              <small className="muted" aria-live="polite">
                {householdMessage}
              </small>
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Privacidade</h2>
                <p>Onde ficam as imagens, os vídeos e o histórico das visitas.</p>
              </div>
            </div>
            <div className="settings-highlight">
              <Icon name="shield" />
              <div>
                <strong>Todos os dados são armazenados localmente</strong>
                <p>Nada é enviado para servidores externos: tudo permanece neste computador.</p>
              </div>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Limpeza automática de vídeos e imagens</h2>
                <p>
                  Por padrão nada é apagado. Se ativar, gravações baixadas, fotos e vídeos dos eventos mais antigos que
                  o prazo são removidos automaticamente. O histórico das visitas é mantido, e registros favoritados com
                  a estrela preservam a mídia.
                </p>
              </div>
            </div>
            <label className="retention-toggle">
              <input
                type="checkbox"
                checked={appSettings?.retention_enabled ?? false}
                disabled={savingRetentionToggle || appSettings === null}
                onChange={event => void toggleRetention(event.target.checked)}
              />
              <span>Apagar mídia antiga automaticamente</span>
            </label>
            <form className="retention-form" onSubmit={saveRetention}>
              <label htmlFor="retention-days">Guardar por</label>
              <div className="retention-input">
                <input
                  id="retention-days"
                  type="number"
                  min="1"
                  max="365"
                  value={retention}
                  onChange={event => setRetention(event.target.value)}
                  disabled={!appSettings?.retention_enabled}
                />
                <span>dias</span>
                <button
                  className="secondary"
                  type="submit"
                  disabled={savingRetention || !appSettings?.retention_enabled}
                >
                  {savingRetention ? 'Salvando…' : 'Salvar'}
                </button>
              </div>
              {retentionMessage && (
                <small className="muted" aria-live="polite">
                  {retentionMessage}
                </small>
              )}
            </form>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Sobre</h2>
                <p>Versão instalada do aplicativo.</p>
              </div>
            </div>
            <div className="settings-about">
              <BrandMark size={44} />
              <div>
                <strong>Monitora Pet</strong>
                <span>{version ? `Versão ${version}` : 'Versão indisponível'}</span>
              </div>
            </div>
          </section>
        </div>
      ) : (
        <>
          {speciesInHousehold.map(species => {
            const calibration = logs?.calibrations[species]
            const remaining = calibration?.interactions_until_calibration ?? CALIBRATION_INTERVAL
            return (
              <div className="identification-species" key={species}>
                <h2>{species === 'CAT' ? 'Gatos' : 'Cães'}</h2>
                <section className="identification-summary">
                  <article className="panel">
                    <span>Similaridade mínima</span>
                    <strong>{Math.round((calibration?.minimum_similarity ?? DEFAULT_SIMILARITY) * 100)}%</strong>
                    <small>Confiança mínima para sugerir um pet.</small>
                  </article>
                  <article className="panel">
                    <span>Separação mínima</span>
                    <strong>{Math.round((calibration?.minimum_margin ?? DEFAULT_MARGIN) * 100)}%</strong>
                    <small>Diferença exigida para o segundo candidato.</small>
                  </article>
                  <article className="panel">
                    <span>Próxima calibração</span>
                    <strong>
                      {CALIBRATION_INTERVAL - remaining}/{CALIBRATION_INTERVAL}
                    </strong>
                    <small>{remaining} revisões confirmadas restantes.</small>
                  </article>
                  <article className="panel">
                    <span>Acerto após revisão</span>
                    <strong>
                      {calibration?.accuracy !== null && calibration?.accuracy !== undefined
                        ? `${Math.round(calibration.accuracy * 100)}%`
                        : '—'}
                    </strong>
                    <small>
                      {calibration?.created_at
                        ? `Calibrado em ${formatDateTime(calibration.created_at)}`
                        : 'Aguardando a primeira calibração.'}
                    </small>
                  </article>
                </section>
              </div>
            )
          })}
          <section className="panel identification-log-panel">
            <div className="panel-head">
              <div>
                <h2>Decisões da identificação</h2>
                <p>Percentuais de todos os pets avaliados em cada visita.</p>
              </div>
              <button className="tertiary" disabled={loading} onClick={() => void loadLogs(logPage)}>
                {loading ? 'Atualizando…' : 'Atualizar'}
              </button>
            </div>
            {loadError && <p className="form-error">{loadError}</p>}
            {loading && !logs ? (
              <p className="loading">Carregando análises…</p>
            ) : !logs?.analyses.length ? (
              <div className="empty">
                <h3>Nenhuma análise registrada</h3>
                <p>Os resultados aparecerão quando uma nova visita for analisada.</p>
              </div>
            ) : (
              <div className="identification-log-list">
                {logs.analyses.map(analysis => (
                  <article className="identification-log" key={analysis.id}>
                    <header>
                      <div>
                        <span className={`identification-decision ${analysis.decision.toLowerCase()}`}>
                          {identificationDecisionLabels[analysis.decision]}
                        </span>
                        <h3>{analysis.selected_pet_name ?? 'Nenhum pet atribuído'}</h3>
                        <p>
                          {analysis.camera_name} · {analysis.zone_name} · {formatDateTime(analysis.created_at)}
                        </p>
                      </div>
                      {analysis.selected_confidence !== null && (
                        <strong>{Math.round(analysis.selected_confidence * 100)}%</strong>
                      )}
                    </header>
                    <div className="identification-candidates">
                      {analysis.scores.map(score => (
                        <div key={score.pet_id}>
                          <div>
                            <span>
                              {score.pet_name}
                              <small>
                                {score.reference_count} {score.reference_count === 1 ? 'referência' : 'referências'}
                              </small>
                            </span>
                            <strong>{Math.round(score.confidence * 100)}%</strong>
                          </div>
                          <i>
                            <b style={{ width: `${Math.round(score.confidence * 100)}%` }} />
                          </i>
                        </div>
                      ))}
                    </div>
                    <footer>
                      <span>
                        Critérios: {Math.round(analysis.minimum_similarity * 100)}% mínimo ·{' '}
                        {Math.round(analysis.minimum_margin * 100)}% de separação
                      </span>
                      {analysis.reviewed_pet_name && (
                        <span className={analysis.was_correct ? 'confirmed' : 'corrected'}>
                          {analysis.was_correct
                            ? 'Confirmado na revisão'
                            : analysis.selected_pet_id
                              ? `Corrigido para ${analysis.reviewed_pet_name}`
                              : `Identificado na revisão como ${analysis.reviewed_pet_name}`}
                        </span>
                      )}
                    </footer>
                  </article>
                ))}
              </div>
            )}
            {logTotal > 0 && (
              <div className="history-pagination">
                <p className="pagination-summary" aria-live="polite">
                  Mostrando{' '}
                  <strong>
                    {logStart}–{logEnd}
                  </strong>{' '}
                  de <strong>{logTotal}</strong> análises
                </p>
                <nav className="pagination-controls" aria-label="Páginas dos logs de identificação">
                  <button
                    className="secondary"
                    disabled={logPage <= 1 || loading}
                    onClick={() => void loadLogs(logPage - 1)}
                  >
                    Anterior
                  </button>
                  {logPages.map((value, index) => (
                    <span className="pagination-item" key={value}>
                      {index > 0 && value - logPages[index - 1] > 1 && (
                        <span className="pagination-ellipsis" aria-hidden="true">
                          …
                        </span>
                      )}
                      <button
                        className="pagination-number"
                        aria-label={`Página ${value}`}
                        aria-current={value === logPage ? 'page' : undefined}
                        disabled={loading}
                        onClick={() => void loadLogs(value)}
                      >
                        {value}
                      </button>
                    </span>
                  ))}
                  <button
                    className="secondary"
                    disabled={logPage >= logPageCount || loading}
                    onClick={() => void loadLogs(logPage + 1)}
                  >
                    Próxima
                  </button>
                </nav>
              </div>
            )}
          </section>
        </>
      )}
    </>
  )
}
