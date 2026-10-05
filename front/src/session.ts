/**
 * Abertura de sessão com o backend local.
 *
 * Quem inicia o app (Tauri, lançador desktop ou start.bat) gera um token e o entrega de uma destas formas:
 *   - `window.__VIGIAPET_TOKEN__` (script de inicialização da WebView), ou
 *   - query `?token=` na URL inicial.
 *
 * O token vira um cookie HttpOnly via `POST /api/session`, o que permite que `<img>` e
 * `<video>` carreguem vídeo e mídia sem cabeçalhos extras. A query só é removida da barra de
 * endereço depois que a sessão está confirmada, para que um F5 após falha transitória recupere.
 */

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

/** Tenta reabrir a sessão com o token recebido do iniciador. Retorna false se não houver token ou ele for recusado. */
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
