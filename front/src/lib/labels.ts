import type { PetSpecies, Recording, Zone } from '../api'
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

export const recordingStatusLabels: Record<Recording['status'], string> = {
  PENDING: 'Na fila',
  PROCESSING: 'Analisando',
  DONE: 'Analisada',
  FAILED: 'Falhou',
  SKIPPED: 'Já coberta ao vivo',
}

export const recordingTimeSourceLabels: Record<Recording['time_source'], string> = {
  PROTOCOL: 'Horário da câmera',
  FILENAME: 'Horário do nome do arquivo',
  MODIFIED: 'Horário estimado pelo arquivo',
  MANUAL: 'Horário ajustado manualmente',
}

export const recordingSupportLabels: Record<string, string> = {
  UNKNOWN: 'Verificando suporte a gravações',
  NONE: 'Importação manual do cartão',
  ONVIF_REPLAY: 'Download automático do cartão',
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('pt-BR')
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('pt-BR')
}

export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  if (minutes < 60) return `${minutes}min ${total % 60}s`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}min`
}

export function toLocalInputValue(value: string): string {
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
