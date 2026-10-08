import { reauthenticate } from './session'

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
  source_kind: 'NETWORK' | 'MANUAL'
  recording_support: 'UNKNOWN' | 'NONE' | 'ONVIF_REPLAY'
  credentials_saved: boolean
  clock_offset_seconds: number
  last_synced_at: string | null
}

export type Recording = {
  id: string
  camera_id: string
  origin: 'FOLDER' | 'CAMERA'
  path: string
  size_bytes: number
  started_at: string
  ended_at: string
  status: 'PENDING' | 'PROCESSING' | 'DONE' | 'FAILED' | 'SKIPPED'
  processed_seconds: number
  error: string | null
  created_at: string
  processed_at: string | null
  time_source: 'PROTOCOL' | 'FILENAME' | 'MODIFIED' | 'MANUAL'
}

export type JobState = {
  status: 'idle' | 'running'
  stage: 'scanning' | 'downloading' | 'analyzing' | null
  camera_id: string | null
  camera_name: string | null
  recording_id: string | null
  progress_seconds: number
  total_seconds: number
  queue: number
  pending_recordings: number
  started_at: string | null
  finished_at: string | null
  last_result:
    | { kind: 'import'; processed: number; skipped: number; failed: number }
    | { kind: 'sync'; downloaded: number; errors: string[] }
    | null
  error: string | null
}

export type HouseholdSpecies = 'CAT' | 'DOG' | 'BOTH'

export type AppSettings = {
  retention_enabled: boolean
  retention_days: number
  household_species: HouseholdSpecies | null
  tutorial: { step: number; status: 'active' | 'completed' | 'skipped'; finished_at: string | null }
}

export type WatchedFolder = {
  id: string
  camera_id: string
  path: string
  created_at: string
  last_scanned_at: string | null
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
  friendly_name?: string
  hostname?: string
  web_title?: string
  upnp_type?: string
  device_type?: 'host' | 'router' | 'camera' | 'media_device' | 'network_device'
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
  pet_names: string | null
  automatically_identified_pet_id: string | null
  pet_identification_confidence: number | null
  pet_identification_method: string | null
  detected_species: PetSpecies
  review_decision: string | null
  highlighted_at: string | null
  highlight_note: string | null
}

export type EventPage = {
  events: Event[]
  total: number
  page: number
  page_size: number
}

export type IdentificationScore = {
  pet_id: string
  pet_name: string
  confidence: number
  reference_count: number
  rank: number
}

export type IdentificationAnalysis = {
  id: string
  event_id: string
  decision: 'MATCHED' | 'LOW_SIMILARITY' | 'AMBIGUOUS' | 'NO_REFERENCES' | 'CAPTURE_UNAVAILABLE' | 'UNSUPPORTED'
  selected_pet_id: string | null
  selected_pet_name: string | null
  selected_confidence: number | null
  minimum_similarity: number
  minimum_margin: number
  reviewed_pet_id: string | null
  reviewed_pet_name: string | null
  was_correct: number | null
  camera_name: string
  zone_name: string
  created_at: string
  scores: IdentificationScore[]
}

export type IdentificationLogs = {
  analyses: IdentificationAnalysis[]
  total: number
  page: number
  page_size: number
  calibrations: Record<PetSpecies, IdentificationCalibration>
}

export type IdentificationCalibration = {
  minimum_similarity: number
  minimum_margin: number
  interaction_count: number
  accuracy: number | null
  created_at: string | null
  interactions_until_calibration: number
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

type ErrorBody = { detail?: string }

async function request<T>(url: string, options?: RequestInit, retried = false): Promise<T> {
  const response = await fetch(url, options)
  if (response.status === 401 && !retried && (await reauthenticate())) return request<T>(url, options, true)
  const data: unknown = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error((data as ErrorBody).detail ?? 'Não foi possível concluir a operação.')
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
export const deleteCamera = (id: string) => request<void>(`/api/cameras/${id}`, { method: 'DELETE' })
export const createManualCamera = (name: string) => request<Camera>('/api/cameras/manual', json('POST', { name }))
export const convertCamera = (id: string, payload: Omit<CameraPayload, 'name'>) =>
  request<Camera>(`/api/cameras/${id}/convert`, json('POST', payload))

export const getRecordings = async (cameraId?: string) => {
  const query = cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : ''
  return (await request<{ recordings: Recording[] }>(`/api/recordings${query}`)).recordings
}
export const importRecordings = async (cameraId: string, path: string, startedAt?: string) =>
  (
    await request<{ recordings: Recording[] }>(
      '/api/recordings/import',
      json('POST', { camera_id: cameraId, path, ...(startedAt ? { started_at: startedAt } : {}) }),
    )
  ).recordings
export const reprocessRecording = (id: string) => request<Recording>(`/api/recordings/${id}/reprocess`, json('POST'))
export const adjustRecordingTime = (id: string, startedAt: string) =>
  request<Recording>(`/api/recordings/${id}`, json('PATCH', { started_at: startedAt }))
export const getWatchedFolders = async (cameraId?: string) => {
  const query = cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : ''
  return (await request<{ folders: WatchedFolder[] }>(`/api/recordings/folders${query}`)).folders
}
export const createWatchedFolder = (cameraId: string, path: string) =>
  request<WatchedFolder>('/api/recordings/folders', json('POST', { camera_id: cameraId, path }))
export const deleteWatchedFolder = (id: string) => request<void>(`/api/recordings/folders/${id}`, { method: 'DELETE' })
export const getSettings = () => request<AppSettings>('/api/settings')
export const updateTutorial = (step: number, status: AppSettings['tutorial']['status'] = 'active') =>
  request<AppSettings>('/api/settings/tutorial', json('PUT', { step, status }))
export const updateSettings = (payload: Partial<AppSettings>) =>
  request<AppSettings>('/api/settings', json('PUT', payload))
export const getJobState = () => request<JobState>('/api/jobs')
export const startImportJob = (cameraId?: string) =>
  request<JobState>(`/api/jobs/import${cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : ''}`, json('POST'))
export const startSyncJob = (cameraId: string) => request<JobState>(`/api/jobs/sync/${cameraId}`, json('POST'))
export const cancelJobs = () => request<JobState>('/api/jobs/cancel', json('POST'))
export const scanWatchedFolder = async (id: string) =>
  (await request<{ recordings: Recording[] }>(`/api/recordings/folders/${id}/scan`, json('POST'))).recordings

export const getZones = async () => (await request<{ zones: Zone[] }>('/api/zones')).zones
export const createZone = (payload: Omit<Zone, 'id' | 'enabled'>) => request<Zone>('/api/zones', json('POST', payload))
export const updateZone = (id: string, payload: Omit<Zone, 'id' | 'enabled'>) =>
  request<Zone>(`/api/zones/${id}`, json('PUT', payload))
export const deleteZone = (id: string) => request<void>(`/api/zones/${id}`, { method: 'DELETE' })
export const getMonitoringFeedback = (cameraId: string) => request<MonitoringFeedback>(`/api/monitoring/${cameraId}`)
export const getIdentificationLogs = (page = 1, pageSize = 10) =>
  request<IdentificationLogs>(`/api/identification/logs?page=${page}&page_size=${pageSize}`)

export const getPets = async () => (await request<{ pets: Pet[] }>('/api/pets')).pets
export type PetPayload = { name: string; species: PetSpecies; description: string; photo_data: string | null }

export const createPet = (payload: PetPayload) => request<Pet>('/api/pets', json('POST', payload))
export const updatePet = (id: string, payload: PetPayload) => request<Pet>(`/api/pets/${id}`, json('PUT', payload))
export const deletePet = (id: string) => request<void>(`/api/pets/${id}`, { method: 'DELETE' })
export const getPetReferences = async (id: string) =>
  (await request<{ images: PetReferenceImage[] }>(`/api/pets/${id}/references`)).images
export const deletePetReference = (petId: string, imageId: string) =>
  request<void>(`/api/pets/${petId}/references/${imageId}`, { method: 'DELETE' })

export const getEvents = async (pendingReview = false, limit = 100, date?: string) => {
  const query = new URLSearchParams({ limit: String(limit) })
  if (pendingReview) query.set('pending_review', 'true')
  if (date) query.set('date', date)
  return (await request<EventPage>(`/api/events?${query.toString()}`)).events
}
export const getEventPage = (
  page: number,
  petId: string,
  zoneType: Zone['type'] | '',
  pageSize = 10,
  startDate = '',
  endDate = '',
  highlightedOnly = false,
) => {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (petId) query.set('pet_id', petId)
  if (zoneType) query.set('zone_type', zoneType)
  if (startDate) query.set('start_date', startDate)
  if (endDate) query.set('end_date', endDate)
  if (highlightedOnly) query.set('highlighted', 'true')
  return request<EventPage>(`/api/events?${query.toString()}`)
}
export const setEventHighlighted = (id: string, highlighted: boolean) =>
  request<Event>(`/api/events/${id}/highlight`, json('PUT', { highlighted }))
export const reviewEvent = (
  id: string,
  decision: string,
  pet_id: string | null,
  zone_type?: Zone['type'],
  pet_ids?: string[],
) =>
  request<unknown>(
    `/api/events/${id}/reviews`,
    json('POST', {
      decision,
      pet_id,
      ...(zone_type ? { zone_type } : {}),
      ...(pet_ids?.length ? { pet_ids } : {}),
    }),
  )
