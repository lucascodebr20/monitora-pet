import { useState } from 'react'
import Icon, { type IconName } from '../Icon'
import DosesSection from './DosesSection'
import ExamsSection from './ExamsSection'
import FoodSection from './FoodSection'
import HealthSummary from './HealthSummary'
import HealthTimeline from './HealthTimeline'
import PetActivity from './PetActivity'
import TreatmentsSection from './TreatmentsSection'
import WeightSection from './WeightSection'

export type HealthTab = 'summary' | 'timeline' | 'food' | 'exams' | 'weight' | 'doses' | 'treatments'

const TABS: [HealthTab, string, IconName][] = [
  ['summary', 'Resumo', 'dashboard'],
  ['timeline', 'Linha do tempo', 'clock'],
  ['exams', 'Exames', 'reviews'],
  ['food', 'Alimentação', 'food'],
  ['weight', 'Peso', 'activity'],
  ['doses', 'Vacinas e remédios', 'calendar'],
  ['treatments', 'Tratamentos', 'shield'],
]

type Props = { petId: string; petName: string }

export default function PetHealth({ petId, petName }: Props) {
  const [tab, setTab] = useState<HealthTab>('summary')
  const [version, setVersion] = useState(0)
  const changed = () => setVersion(current => current + 1)
  const props = { petId, petName, onChanged: changed }

  return (
    <div className="pet-health">
      <header className="health-heading">
        <span className="health-heading-icon">
          <Icon name="activity" />
        </span>
        <div>
          <p className="eyebrow">CUIDADOS E BEM-ESTAR</p>
          <h2>Saúde de {petName}</h2>
          <p>Um lugar para acompanhar cada etapa do cuidado.</p>
        </div>
      </header>
      <div className="health-tabs" role="group" aria-label={`Saúde de ${petName}`}>
        {TABS.map(([value, label, icon]) => (
          <button
            key={value}
            type="button"
            aria-current={tab === value ? 'page' : undefined}
            className={tab === value ? 'selected' : ''}
            onClick={() => setTab(value)}
          >
            <Icon name={icon} />
            {label}
          </button>
        ))}
      </div>
      {tab === 'summary' && (
        <>
          <PetActivity
            key={`activity-${petId}-${version}`}
            petId={petId}
            petName={petName}
            onOpenTimeline={() => setTab('timeline')}
          />
          <HealthSummary key={`${petId}-${version}`} petId={petId} petName={petName} onOpen={setTab} />
        </>
      )}
      {tab === 'timeline' && <HealthTimeline key={`${petId}-${version}`} petId={petId} petName={petName} />}
      {tab === 'exams' && <ExamsSection key={petId} {...props} />}
      {tab === 'food' && <FoodSection key={petId} {...props} />}
      {tab === 'weight' && <WeightSection key={petId} {...props} />}
      {tab === 'doses' && <DosesSection key={petId} {...props} />}
      {tab === 'treatments' && <TreatmentsSection key={petId} {...props} />}
    </div>
  )
}
