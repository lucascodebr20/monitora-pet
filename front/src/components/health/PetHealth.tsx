import { useState } from 'react'
import DosesSection from './DosesSection'
import ExamsSection from './ExamsSection'
import FoodSection from './FoodSection'
import HealthSummary from './HealthSummary'
import HealthTimeline from './HealthTimeline'
import TreatmentsSection from './TreatmentsSection'
import WeightSection from './WeightSection'

export type HealthTab = 'summary' | 'timeline' | 'food' | 'exams' | 'weight' | 'doses' | 'treatments'

const TABS: [HealthTab, string][] = [
  ['summary', 'Resumo'],
  ['timeline', 'Linha do tempo'],
  ['exams', 'Exames'],
  ['food', 'Alimentação'],
  ['weight', 'Peso'],
  ['doses', 'Vacinas e remédios'],
  ['treatments', 'Tratamentos'],
]

type Props = { petId: string; petName: string }

export default function PetHealth({ petId, petName }: Props) {
  const [tab, setTab] = useState<HealthTab>('summary')
  const [version, setVersion] = useState(0)
  const changed = () => setVersion(current => current + 1)
  const props = { petId, petName, onChanged: changed }

  return (
    <div className="pet-health">
      <div className="health-tabs" role="group" aria-label={`Saúde de ${petName}`}>
        {TABS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-current={tab === value ? 'page' : undefined}
            className={tab === value ? 'selected' : ''}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'summary' && <HealthSummary key={`${petId}-${version}`} petId={petId} petName={petName} onOpen={setTab} />}
      {tab === 'timeline' && <HealthTimeline key={`${petId}-${version}`} petId={petId} petName={petName} />}
      {tab === 'exams' && <ExamsSection key={petId} {...props} />}
      {tab === 'food' && <FoodSection key={petId} {...props} />}
      {tab === 'weight' && <WeightSection key={petId} {...props} />}
      {tab === 'doses' && <DosesSection key={petId} {...props} />}
      {tab === 'treatments' && <TreatmentsSection key={petId} {...props} />}
    </div>
  )
}
