declare global {
  interface Window {
    __VIGIAPET_TOKEN__?: string
  }
}

type SessionStatus = { required: boolean; authenticated: boolean }

let launcherToken: string | null = null

function readLauncherToken(): string | null {
  if (window.__VIGIAPET_TOKEN__) return window.__VIGIAPET_TOKEN__
  return new URLSearchParams(window.location.search).get('token')
}

function forgetTokenInUrl(): void {
  const params = new URLSearchParams(window.location.search)
  if (!params.has('token')) return
  params.delete('token')
  const query = params.toString()
  window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`)
}

async function openSession(token: string): Promise<boolean> {
  const response = await fetch('/api/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  return response.ok
}

export async function reauthenticate(): Promise<boolean> {
  if (!launcherToken) return false
  return openSession(launcherToken)
}

export async function bootstrapSession(): Promise<void> {
  launcherToken = readLauncherToken()
  const response = await fetch('/api/session')
  if (!response.ok) throw new Error('Não foi possível falar com o serviço do VigiaPet.')
  const status = (await response.json()) as SessionStatus
  if (!status.required || status.authenticated) {
    forgetTokenInUrl()
    return
  }
  if (!launcherToken) throw new Error('Esta janela não recebeu a chave de sessão. Abra o VigiaPet pelo aplicativo.')
  if (!(await openSession(launcherToken)))
    throw new Error('A chave de sessão foi recusada. Feche e abra o VigiaPet novamente.')
  forgetTokenInUrl()
}
