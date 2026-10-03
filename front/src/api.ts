export type ConnectionStatus = {
  connected: boolean
  message: string
  resolution: { width: number; height: number }
}

export type Camera = {
  id: string
  name: string
  ip: string
  manufacturer: string
  model: string
  enabled: boolean
  status: ConnectionStatus
}

export type PetSpecies = 'CAT' | 'DOG'

export type Pet = {
  id: string
  name: string
  species: PetSpecies
  description: string
  photo_path: string | null
  event_count: number
  reference_count: number
}

export type PetReferenceImage = {
  id: string
  pet_id: string
  event_id: string | null
  url: string
  created_at: string
}

export type CameraCandidate = {
  ip: string
  name: string
  onvif: boolean
  confidence?: 'high' | 'medium' | 'low'
  reason?: string
  manufacturer?: string
  model?: string
}

export type Zone = {
  id: string
  camera_id: string
  name: string
  type: 'FOOD' | 'WATER' | 'LITTER' | 'CUSTOM'
  polygon: { x: number; y: number }[]
  minimum_presence_seconds: number
  absence_tolerance_seconds: number
  cooldown_seconds: number
  enabled: boolean
}

export type Detection = {
  x1: number
  y1: number
  x2: number
  y2: number
  confidence: number
  species: PetSpecies
}

export type ZoneFeedback = {
  zone_id: string
  state: 'OUTSIDE' | 'CANDIDATE' | 'ACTIVE' | 'COOLDOWN'
  inside: boolean
  elapsed_seconds: number
  progress: number
  confidence: number
  event_id: string | null
}

export type MonitoringFeedback = {
  camera_id: string
  status: 'running' | 'stopped' | 'model_missing' | 'error'
  updated_at: string | null
  detections: Detection[]
  zones: ZoneFeedback[]
  error: string | null
}

export type Event = {
  id: string
  camera_name: string
  zone_name: string
  zone_type: Zone['type']
  started_at: string
  duration_seconds: number
  activity: string
  confidence: number | null
  snapshot_path: string | null
  clip_path: string | null
  pet_id: string | null
  pet_name: string | null
  detected_species: PetSpecies
  review_decision: string | null
}

export type EventPage = {
  events: Event[]
  total: number
  page: number
  page_size: number
}

export type Dashboard = {
  date: string
  events_today: number
  pending_reviews: number
  by_zone_type: Record<string, number>
  recent_events: Event[]
  health: {
    status: string
    version: string
    cameras: { registered: number; connected: number }
    inference: { status: string; provider: string | null }
  }
}

type CameraPayload = {
  name: string
  ip: string
  username: string
  password: string
  rtsp_url: string | null
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail ?? 'Não foi possível concluir a operação.')
  return data as T
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const getDashboard = () => request<Dashboard>('/api/dashboard')
export const getCameras = async () => (await request<{ cameras: Camera[] }>('/api/cameras')).cameras
export const discoverCameras = async (fallback = false) =>
  (await request<{ cameras: CameraCandidate[] }>(`/api/cameras/discover${fallback ? '?fallback=true' : ''}`)).cameras
export const createCamera = (payload: CameraPayload) => request<Camera>('/api/cameras', json('POST', payload))
export const connectCamera = (id: string, payload: Pick<CameraPayload, 'username' | 'password' | 'rtsp_url'>) =>
  request<ConnectionStatus>(`/api/cameras/${id}/connect`, json('POST', payload))
export const disconnectCamera = (id: string) => request<ConnectionStatus>(`/api/cameras/${id}/disconnect`, json('POST'))
export const deleteCamera = (id: string) => request<void>(`/api/cameras/${id}`, { method: 'DELETE' })

export const getZones = async () => (await request<{ zones: Zone[] }>('/api/zones')).zones
export const createZone = (payload: Omit<Zone, 'id' | 'enabled'>) => request<Zone>('/api/zones', json('POST', payload))
export const updateZone = (id: string, payload: Omit<Zone, 'id' | 'enabled'>) => request<Zone>(`/api/zones/${id}`, json('PUT', payload))
export const deleteZone = (id: string) => request<void>(`/api/zones/${id}`, { method: 'DELETE' })
export const getMonitoringFeedback = (cameraId: string) => request<MonitoringFeedback>(`/api/monitoring/${cameraId}`)

export const getPets = async () => (await request<{ pets: Pet[] }>('/api/pets')).pets
export const createPet = (payload: { name: string; species: PetSpecies; description: string; photo_data: string | null }) =>
  request<Pet>('/api/pets', json('POST', payload))
export const updatePet = (id: string, payload: { name: string; species: PetSpecies; description: string; photo_data: string | null }) =>
  request<Pet>(`/api/pets/${id}`, json('PUT', payload))
export const deletePet = (id: string) => request<void>(`/api/pets/${id}`, { method: 'DELETE' })
export const getPetReferences = async (id: string) =>
  (await request<{ images: PetReferenceImage[] }>(`/api/pets/${id}/references`)).images

export const getEvents = async (pendingReview = false, limit = 100, date?: string) => {
  const query = new URLSearchParams({ limit: String(limit) })
  if (pendingReview) query.set('pending_review', 'true')
  if (date) query.set('date', date)
  return (await request<EventPage>(`/api/events?${query.toString()}`)).events
}
export const getEventPage = (page: number, petId: string, zoneType: Zone['type'] | '', pageSize = 10) => {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (petId) query.set('pet_id', petId)
  if (zoneType) query.set('zone_type', zoneType)
  return request<EventPage>(`/api/events?${query.toString()}`)
}
export const reviewEvent = (id: string, decision: string, pet_id: string | null, zone_type?: Zone['type']) =>
  request(`/api/events/${id}/reviews`, json('POST', { decision, pet_id, ...(zone_type ? { zone_type } : {}) }))
