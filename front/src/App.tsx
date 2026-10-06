import { useState } from 'react'
import Icon from './components/Icon'
import PetManager from './components/PetManager'
import ZoneEditor from './components/ZoneEditor'
import { useAppData } from './data/useAppData'
import { monitoringViews, primaryViews, View, viewLabels } from './lib/views'
import CamerasView from './views/CamerasView'
import DashboardView from './views/DashboardView'
import HistoryView from './views/HistoryView'
import ReviewsView from './views/ReviewsView'
import SettingsView from './views/SettingsView'

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const { dashboard, cameras, zones, pets, error, reloadToken, refresh } = useAppData()
  const pendingReviews = dashboard?.pending_reviews ?? 0

  function navItems(items: View[]) {
    return items.map(item => (
      <button key={item} className={view === item ? 'active' : ''} onClick={() => setView(item)}>
        <Icon name={item} />
        {viewLabels[item]}
        {item === 'reviews' && pendingReviews > 0 && <b>{pendingReviews}</b>}
      </button>
    ))
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={e => {
            e.preventDefault()
            setView('dashboard')
          }}
        >
          <span className="brand-mark">
            <Icon name="pets" />
          </span>
          <strong>
            vigia<span>pet</span>
          </strong>
        </a>
        <p className="nav-caption">ACOMPANHAMENTO</p>
        <nav>{navItems(primaryViews)}</nav>
        <p className="nav-caption second">MONITORAMENTO</p>
        <nav>{navItems(monitoringViews)}</nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <Icon name="shield" />
            <div>
              <strong>Todos os dados são armazenados localmente</strong>
            </div>
          </div>
          <div className="workspace-avatar">
            <span>VP</span>
            <div>
              <strong>Minha casa</strong>
              <small>Monitoramento local</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span>Minha casa</span>
            <span className="breadcrumb">/</span>
            <strong>{viewLabels[view]}</strong>
          </div>
        </header>
        <main className="content">
          {error && (
            <div className="global-error">
              {error}
              <button onClick={() => void refresh()}>Tentar novamente</button>
            </div>
          )}
          {view === 'dashboard' && (
            <DashboardView
              data={dashboard}
              pets={pets}
              cameras={cameras}
              reloadToken={reloadToken}
              onNavigate={setView}
            />
          )}
          {view === 'cameras' && <CamerasView cameras={cameras} zones={zones} refresh={refresh} />}
          {view === 'zones' && <ZoneEditor cameras={cameras} zones={zones} refresh={refresh} />}
          {view === 'pets' && <PetManager pets={pets} refresh={refresh} />}
          {view === 'history' && <HistoryView pets={pets} reloadToken={reloadToken} />}
          {view === 'reviews' && <ReviewsView pets={pets} reloadToken={reloadToken} refresh={refresh} />}
          {view === 'settings' && <SettingsView version={dashboard?.health.version ?? ''} />}
        </main>
        <footer className="app-footer">
          Monitora Pet <span>Um pouco mais perto da rotina deles.</span>
        </footer>
      </div>
    </div>
  )
}
