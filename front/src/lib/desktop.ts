declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown
  }
}

export const isDesktopApp = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export async function pickFolder(): Promise<string | null | undefined> {
  try {
    const { open } = await import('@tauri-apps/plugin-dialog')
    const selected = await open({ directory: true, multiple: false, title: 'Escolha a pasta com as gravações' })
    return typeof selected === 'string' ? selected : null
  } catch {
    return undefined
  }
}
