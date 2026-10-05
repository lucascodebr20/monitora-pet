import { ReactNode, useCallback, useEffect, useState } from 'react'
import Icon from './Icon'
import { ToastContext, ToastContextValue, ToastTone } from './toastContext'

type Toast = { id: number; message: string; tone: ToastTone }

const DISMISS_MS = 4000

function ToastItem({ toast, dismiss }: { toast: Toast; dismiss: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(dismiss, DISMISS_MS)
    return () => window.clearTimeout(timer)
  }, [dismiss])

  return (
    <div className={`toast toast-${toast.tone}`} role={toast.tone === 'error' ? 'alert' : 'status'}>
      <span className="toast-icon">
        <Icon name={toast.tone === 'success' ? 'accept' : toast.tone === 'error' ? 'reject' : 'info'} />
      </span>
      <p>{toast.message}</p>
      <button type="button" aria-label="Fechar notificação" onClick={dismiss}>
        ×
      </button>
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const showToast = useCallback<ToastContextValue>((message, tone = 'success') => {
    const id = Date.now() + Math.random()
    setToasts(current => [...current, { id, message, tone }])
  }, [])
  const dismiss = useCallback((id: number) => setToasts(current => current.filter(toast => toast.id !== id)), [])

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      <div className="toast-region" aria-live="polite" aria-atomic="true">
        {toasts.map(toast => (
          <ToastItem key={toast.id} toast={toast} dismiss={() => dismiss(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
