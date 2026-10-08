import { useState } from 'react'
import * as api from '../api'
import HouseholdArt from '../components/HouseholdArt'
import PawTrail from '../components/PawTrail'
import { errorMessage } from '../lib/errors'
import { Household, householdOptions } from '../lib/household'

type Props = { onDone: (household: Household) => void }

export default function OnboardingView({ onDone }: Props) {
  const [choice, setChoice] = useState<Household | ''>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const chosen = householdOptions.find(option => option.value === choice)
  // Antes da escolha as trilhas alternam gato e cachorro.
  const trail = choice || 'BOTH'

  async function save() {
    if (!choice || saving) return
    setSaving(true)
    setError('')
    try {
      const saved = await api.updateSettings({ household_species: choice })
      onDone(saved.household_species ?? choice)
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível salvar sua escolha.'))
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop onboarding" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <section className="modal onboarding-card">
        {/* A key remonta as trilhas a cada escolha, e as pegadas andam de novo. */}
        <PawTrail key={`top-${trail}`} household={trail} className="onboarding-trail top" steps={5} />
        <PawTrail key={`bottom-${trail}`} household={trail} className="onboarding-trail bottom" steps={4} />
        <h1 id="onboarding-title">Quem mora com você?</h1>
        <p className="onboarding-intro">
          O VigiaPet adapta as áreas monitoradas, os nomes e o cadastro dos pets ao que faz sentido para a sua casa. Dá
          para mudar depois em Configurações.
        </p>
        <div className="household-options" role="radiogroup" aria-label="Espécies da casa">
          {householdOptions.map(option => (
            <label
              className={`household-option ${choice === option.value ? 'chosen' : ''}`}
              data-household={option.value}
              key={option.value}
            >
              <input
                type="radio"
                name="household"
                value={option.value}
                checked={choice === option.value}
                disabled={saving}
                onChange={() => setChoice(option.value)}
              />
              <span className="household-art">
                <HouseholdArt household={option.value} size={40} />
              </span>
              <span>
                <strong>{option.title}</strong>
                <small>{option.description}</small>
              </span>
            </label>
          ))}
        </div>
        <p className="onboarding-greeting" aria-live="polite">
          {chosen && <span key={chosen.value}>{chosen.greeting}</span>}
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="primary full" disabled={!choice || saving} onClick={() => void save()}>
          {saving ? 'Salvando…' : 'Começar'}
        </button>
      </section>
    </div>
  )
}
