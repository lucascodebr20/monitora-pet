import { useState } from 'react'
import * as api from '../api'
import Icon from '../components/Icon'
import { errorMessage } from '../lib/errors'
import { Household, householdOptions } from '../lib/household'

type Props = { onDone: (household: Household) => void }

export default function OnboardingView({ onDone }: Props) {
  const [choice, setChoice] = useState<Household | ''>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

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
    <main className="onboarding">
      <section className="onboarding-card">
        <span className="brand-mark">
          <Icon name="pets" />
        </span>
        <p className="eyebrow">PRIMEIRO ACESSO</p>
        <h1>Quem mora com você?</h1>
        <p className="onboarding-intro">
          O VigiaPet adapta as áreas monitoradas, os nomes e o cadastro dos pets ao que faz sentido para a sua casa. Dá
          para mudar depois em Configurações.
        </p>
        <div className="household-options" role="radiogroup" aria-label="Espécies da casa">
          {householdOptions.map(option => (
            <label className={`household-option ${choice === option.value ? 'chosen' : ''}`} key={option.value}>
              <input
                type="radio"
                name="household"
                value={option.value}
                checked={choice === option.value}
                disabled={saving}
                onChange={() => setChoice(option.value)}
              />
              <span className="household-emoji" aria-hidden="true">
                {option.emoji}
              </span>
              <span>
                <strong>{option.title}</strong>
                <small>{option.description}</small>
              </span>
            </label>
          ))}
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="primary full" disabled={!choice || saving} onClick={() => void save()}>
          {saving ? 'Salvando…' : 'Começar'}
        </button>
      </section>
    </main>
  )
}
