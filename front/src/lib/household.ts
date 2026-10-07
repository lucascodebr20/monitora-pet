import { createContext } from 'react'
import type { HouseholdSpecies, PetSpecies, Zone } from '../api'
import type { IconName } from '../components/Icon'

export type Household = HouseholdSpecies

export const householdOptions: { value: Household; title: string; description: string; emoji: string }[] = [
  { value: 'CAT', title: 'Gatos', description: 'Áreas de água, comida e caixa de areia.', emoji: '🐈' },
  { value: 'DOG', title: 'Cachorros', description: 'Áreas de água, comida e banheiro.', emoji: '🐕' },
  { value: 'BOTH', title: 'Gatos e cachorros', description: 'Todas as áreas e espécies disponíveis.', emoji: '🐾' },
]

export const householdLabels: Record<Household, string> = {
  CAT: 'Gatos',
  DOG: 'Cachorros',
  BOTH: 'Gatos e cachorros',
}

const hygieneLabels: Record<Household, string> = {
  CAT: 'Caixa de areia',
  DOG: 'Banheiro',
  BOTH: 'Banheiro',
}

const hygieneShortLabels: Record<Household, string> = {
  CAT: 'visitas à caixa',
  DOG: 'visitas ao banheiro',
  BOTH: 'visitas ao banheiro',
}

export type HouseholdView = {
  household: Household
  hasCats: boolean
  hasDogs: boolean
  defaultSpecies: PetSpecies
  zoneLabels: Record<Zone['type'], string>
  hygieneSummary: string
  zoneIcon: (type: string) => IconName
}

export function describeHousehold(household: Household): HouseholdView {
  const hasCats = household !== 'DOG'
  const hasDogs = household !== 'CAT'
  return {
    household,
    hasCats,
    hasDogs,
    defaultSpecies: hasCats ? 'CAT' : 'DOG',
    zoneLabels: {
      FOOD: 'Comida',
      WATER: 'Água',
      LITTER: hygieneLabels[household],
      CUSTOM: 'Personalizada',
    },
    hygieneSummary: hygieneShortLabels[household],
    zoneIcon: type => {
      switch (type) {
        case 'WATER':
          return 'water'
        case 'FOOD':
          return 'food'
        case 'LITTER':
          return household === 'DOG' ? 'pad' : 'litter'
        default:
          return 'zones'
      }
    },
  }
}

export const HouseholdContext = createContext<HouseholdView>(describeHousehold('BOTH'))
