import type { PetSpecies, Zone } from '../api'
import type { IconName } from '../components/Icon'

export const zoneLabels: Record<Zone['type'], string> = {
  FOOD: 'Comida',
  WATER: 'Água',
  LITTER: 'Caixa de areia',
  CUSTOM: 'Personalizada',
}

export const correctableZoneTypes = ['WATER', 'FOOD', 'LITTER'] as const

export function zoneIcon(type: string): IconName {
  switch (type) {
    case 'WATER':
      return 'water'
    case 'FOOD':
      return 'food'
    case 'LITTER':
      return 'litter'
    default:
      return 'zones'
  }
}

export const speciesLabels: Record<PetSpecies, string> = { CAT: 'Gato', DOG: 'Cão' }

export const identificationDecisionLabels: Record<string, string> = {
  MATCHED: 'Gato identificado',
  LOW_SIMILARITY: 'Similaridade insuficiente',
  AMBIGUOUS: 'Resultado ambíguo',
  NO_REFERENCES: 'Sem referências disponíveis',
  CAPTURE_UNAVAILABLE: 'Captura indisponível',
  UNSUPPORTED: 'Espécie não analisada',
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('pt-BR')
}
