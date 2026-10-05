import { useEffect } from 'react'

export function useEscape(onEscape: () => void, enabled = true): void {
  useEffect(() => {
    if (!enabled) return
    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onEscape()
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [onEscape, enabled])
}
