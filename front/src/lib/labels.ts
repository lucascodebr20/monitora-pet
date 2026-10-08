import type { PetSpecies, Recording } from '../api'

export const correctableZoneTypes = ['WATER', 'FOOD', 'LITTER'] as const

export const speciesLabels: Record<PetSpecies, string> = { CAT: 'Gato', DOG: 'Cão' }

export const identificationDecisionLabels: Record<string, string> = {
  MATCHED: 'Pet identificado',
  LOW_SIMILARITY: 'Similaridade insuficiente',
  AMBIGUOUS: 'Resultado ambíguo',
  INCONSISTENT_OBSERVATIONS: 'Imagens discordam sobre o pet',
  MULTIPLE_PETS: 'Mais de um pet na área',
  UNSTABLE_TRACK: 'Continuidade do pet incerta',
  NO_REFERENCES: 'Sem referências disponíveis',
  CAPTURE_UNAVAILABLE: 'Captura indisponível',
  UNSUPPORTED: 'Espécie não reconhecida',
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

export const foodTypeLabels: Record<string, string> = {
  DRY: 'Seca',
  WET: 'Úmida',
  OTHER: 'Outro',
}

export const examTypeLabels: Record<string, string> = {
  BLOOD: 'Sangue',
  URINE: 'Urina',
  FECES: 'Fezes',
  IMAGING: 'Imagem (raio-X, ultrassom)',
  PRESCRIPTION: 'Receita',
  REPORT: 'Laudo ou relatório',
  OTHER: 'Outro',
}

export const doseKindLabels: Record<string, string> = {
  VACCINE: 'Vacina',
  MEDICATION: 'Remédio',
  ANTIPARASITIC: 'Antiparasitário',
}
