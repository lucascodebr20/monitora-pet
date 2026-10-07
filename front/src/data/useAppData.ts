import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { AppSettings, Camera, Dashboard, Pet, Zone } from '../api'
import { errorMessage } from '../lib/errors'

export type AppData = {
  dashboard: Dashboard | null
  cameras: Camera[]
  zones: Zone[]
  pets: Pet[]
  settings: AppSettings | null
  error: string
  reloadToken: number
  refresh: () => Promise<void>
  applySettings: (settings: AppSettings) => void
}

const POLL_MS = 10000
const LOAD_ERROR = 'Não foi possível carregar o Monitora Pet.'

export function useAppData(): AppData {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [pets, setPets] = useState<Pet[]>([])
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [error, setError] = useState('')
  const [reloadToken, setReloadToken] = useState(0)
  const summarySequence = useRef(0)
  const catalogSequence = useRef(0)

  const refresh = useCallback(async () => {
    const summaryId = ++summarySequence.current
    const catalogId = ++catalogSequence.current
    try {
      const [summary, cameraList, zoneList, petList, appSettings] = await Promise.all([
        api.getDashboard(),
        api.getCameras(),
        api.getZones(),
        api.getPets(),
        api.getSettings(),
      ])
      if (summaryId === summarySequence.current) {
        setDashboard(summary)
        setCameras(cameraList)
      }
      if (catalogId === catalogSequence.current) {
        setZones(zoneList)
        setPets(petList)
        setSettings(appSettings)
        setReloadToken(value => value + 1)
      }
      setError('')
    } catch (reason) {
      if (summaryId === summarySequence.current) setError(errorMessage(reason, LOAD_ERROR))
    }
  }, [])

  const poll = useCallback(async () => {
    if (document.hidden) return
    const summaryId = ++summarySequence.current
    try {
      const [summary, cameraList] = await Promise.all([api.getDashboard(), api.getCameras()])
      if (summaryId !== summarySequence.current) return
      setDashboard(summary)
      setCameras(cameraList)
      setError('')
    } catch (reason) {
      if (summaryId === summarySequence.current) setError(errorMessage(reason, LOAD_ERROR))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    const timer = window.setInterval(() => void poll(), POLL_MS)
    return () => window.clearInterval(timer)
  }, [poll])

  return { dashboard, cameras, zones, pets, settings, error, reloadToken, refresh, applySettings: setSettings }
}
