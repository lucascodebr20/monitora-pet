export type View = 'dashboard' | 'cameras' | 'zones' | 'pets' | 'history' | 'reviews' | 'settings'

export const viewLabels: Record<View, string> = {
  dashboard: 'Hoje',
  cameras: 'Câmeras',
  zones: 'Áreas monitoradas',
  pets: 'Pets',
  history: 'Histórico',
  reviews: 'Revisões',
  settings: 'Configurações',
}

export const primaryViews: View[] = ['dashboard', 'history', 'reviews', 'pets']
export const monitoringViews: View[] = ['cameras', 'zones', 'settings']
