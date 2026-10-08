import { useCallback, useEffect, useState } from 'react'
import * as api from '../api'
import type { AppSettings, HouseholdSpecies, IdentificationLogs, PetSpecies } from '../api'
import BrandMark from '../components/BrandMark'
import HouseholdArt from '../components/HouseholdArt'
import Icon from '../components/Icon'
import { useToast } from '../components/useToast'
import { errorMessage } from '../lib/errors'
import { formatDateTime, identificationDecisionLabels } from '../lib/labels'
import { householdOptions } from '../lib/household'
import { pageWindow } from '../lib/pagination'
import { useHousehold } from '../lib/useHousehold'

type Section = 'general' | 'identification'

const CALIBRATION_INTERVAL = 10
const DEFAULT_SIMILARITY = 0.115
const DEFAULT_MARGIN = 0.016
const RETENTION_PRESETS = [7, 15, 30, 60, 90, 180, 365]

type Props = { version: string; settings: AppSettings | null; onSettings: (settings: AppSettings) => void }

export default function SettingsView({ version, settings: appSettings, onSettings }: Props) {
  const { hasCats, hasDogs } = useHousehold()
  const [section, setSection] = useState<Section>('general')
  const [logs, setLogs] = useState<IdentificationLogs | null>(null)
  const [logPage, setLogPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const showToast = useToast()
  const [savingRetention, setSavingRetention] = useState(false)
  const [savingHousehold, setSavingHousehold] = useState(false)

  const retentionEnabled = appSettings?.retention_enabled ?? false
  const retentionDays = appSettings?.retention_days ?? 7
  // Um prazo salvo fora das opções (versões antigas aceitavam qualquer número) continua na lista.
  const retentionChoices = [...new Set([...RETENTION_PRESETS, retentionDays])].sort((a, b) => a - b)

  async function saveSettings(payload: Partial<AppSettings>, success: string) {
    try {
      onSettings(await api.updateSettings(payload))
      showToast(success, 'success')
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível salvar.'), 'error')
    }
  }

  async function toggleRetention(enabled: boolean) {
    if (savingRetention || !appSettings) return
    setSavingRetention(true)
    await saveSettings(
      { retention_enabled: enabled },
      enabled
        ? `Mídia com mais de ${retentionDays} dias será apagada.`
        : 'Limpeza automática desligada. Nada será apagado.',
    )
    setSavingRetention(false)
  }

  async function saveRetention(days: number) {
    if (savingRetention) return
    setSavingRetention(true)
    await saveSettings({ retention_days: days }, `A mídia agora fica guardada por ${days} dias.`)
    setSavingRetention(false)
  }

  async function saveHousehold(value: HouseholdSpecies) {
    if (savingHousehold || value === appSettings?.household_species) return
    setSavingHousehold(true)
    await saveSettings({ household_species: value }, 'Preferência salva. A interface já foi adaptada.')
    setSavingHousehold(false)
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
          Identificação
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
            <fieldset
              className="household-options settings-household"
              disabled={savingHousehold || appSettings === null}
            >
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
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Armazenamento</h2>
                <p>Gravações, fotos e vídeos dos eventos ficam guardados neste computador.</p>
              </div>
            </div>
            <div className="settings-rows">
              <button
                type="button"
                className="settings-row settings-switch"
                role="switch"
                aria-checked={retentionEnabled}
                disabled={savingRetention || appSettings === null}
                onClick={() => void toggleRetention(!retentionEnabled)}
              >
                <span>
                  <strong>Apagar mídia antiga automaticamente</strong>
                  <small>
                    {retentionEnabled
                      ? 'Mídia mais antiga que o prazo abaixo é removida. O histórico das visitas é mantido.'
                      : 'Desligado, nada é apagado. O histórico das visitas é sempre mantido.'}
                  </small>
                </span>
                <span className="switch-control" aria-hidden="true">
                  <i />
                </span>
              </button>
              {retentionEnabled && (
                <div className="settings-row">
                  <label htmlFor="retention-days">
                    <strong>Guardar mídia por</strong>
                    <small>Registros favoritados com a estrela nunca perdem a mídia.</small>
                  </label>
                  <select
                    id="retention-days"
                    value={retentionDays}
                    disabled={savingRetention}
                    onChange={event => void saveRetention(Number(event.target.value))}
                  >
                    {retentionChoices.map(days => (
                      <option key={days} value={days}>
                        {days === 1 ? '1 dia' : `${days} dias`}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Sobre</h2>
              </div>
            </div>
            <div className="settings-rows">
              <div className="settings-row settings-info">
                <span className="settings-info-icon">
                  <Icon name="shield" />
                </span>
                <span>
                  <strong>Seus dados ficam só neste computador</strong>
                  <small>Imagens, vídeos e histórico não são enviados para servidores externos.</small>
                </span>
              </div>
              <div className="settings-row settings-info">
                <BrandMark size={36} />
                <span>
                  <strong>Monitora Pet</strong>
                  <small>{version ? `Versão ${version}` : 'Versão indisponível'}</small>
                </span>
              </div>
            </div>
          </section>
        </div>
      ) : (
        <div className="settings-panels">
          {speciesInHousehold.map(species => {
            const calibration = logs?.calibrations[species]
            const remaining = calibration?.interactions_until_calibration ?? CALIBRATION_INTERVAL
            return (
              <section className="panel identification-species" key={species}>
                <div className="panel-head">
                  <div>
                    <h2>{species === 'CAT' ? 'Gatos' : 'Cães'}</h2>
                    <p>
                      Critérios que a identificação usa hoje. Eles se ajustam a cada {CALIBRATION_INTERVAL} revisões.
                    </p>
                  </div>
                </div>
                <div className="identification-summary">
                  <article>
                    <span>Similaridade mínima</span>
                    <strong>{Math.round((calibration?.minimum_similarity ?? DEFAULT_SIMILARITY) * 100)}%</strong>
                    <small>Confiança mínima para sugerir um pet.</small>
                  </article>
                  <article>
                    <span>Separação mínima</span>
                    <strong>{Math.round((calibration?.minimum_margin ?? DEFAULT_MARGIN) * 100)}%</strong>
                    <small>Diferença exigida para o segundo candidato.</small>
                  </article>
                  <article>
                    <span>Próxima calibração</span>
                    <strong>
                      {CALIBRATION_INTERVAL - remaining}/{CALIBRATION_INTERVAL}
                    </strong>
                    <small>{remaining} revisões confirmadas restantes.</small>
                  </article>
                  <article>
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
                </div>
              </section>
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
        </div>
      )}
    </>
  )
}
