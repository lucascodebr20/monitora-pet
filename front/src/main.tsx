import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ToastProvider } from './components/Toast'
import { bootstrapSession } from './session'
import './styles.css'

const root = createRoot(document.getElementById('root')!)

bootstrapSession()
  .then(() => root.render(<StrictMode><ToastProvider><App /></ToastProvider></StrictMode>))
  .catch((error: Error) =>
    root.render(
      <div className="empty" role="alert">
        <span className="empty-icon">◇</span>
        <h3>VigiaPet não conseguiu iniciar a sessão</h3>
        <p>{error.message}</p>
      </div>,
    ),
  )
