import { useCallback, useMemo, useState } from 'react'
import BrandMark from './components/BrandMark'
import Icon from './components/Icon'
import JobBanner from './components/JobBanner'
import PawTrail from './components/PawTrail'
import PetManager from './components/PetManager'
import ZoneEditor from './components/ZoneEditor'
import { useAppData } from './data/useAppData'
import { useEscape } from './lib/hooks'
import { HouseholdContext, describeHousehold } from './lib/household'
import { monitoringViews, primaryViews, View, viewLabels } from './lib/views'
import CamerasView from './views/CamerasView'
import DashboardView from './views/DashboardView'
import HistoryView from './views/HistoryView'
import OnboardingView from './views/OnboardingView'
import ReviewsView from './views/ReviewsView'
import SettingsView from './views/SettingsView'

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = useCallback(() => setMenuOpen(false), [])
  useEscape(closeMenu, menuOpen)
  const { dashboard, cameras, zones, pets, settings, error, reloadToken, refresh, applySettings } = useAppData()
  const pendingReviews = dashboard?.pending_reviews ?? 0
  const household = settings?.household_species ?? null
  const householdView = useMemo(() => describeHousehold(household ?? 'BOTH'), [household])

  // O item "Pets" do menu mostra o pet da casa: gato, cachorro ou a pata para os dois.
  const petsIcon = household === 'CAT' ? 'cat' : household === 'DOG' ? 'dog' : 'pets'

  function navigate(next: View) {
    setView(next)
    setMenuOpen(false)
  }

  function navItems(items: View[]) {
    return items.map(item => (
      <button key={item} className={view === item ? 'active' : ''} onClick={() => navigate(item)}>
        <Icon name={item === 'pets' ? petsIcon : item} />
        {viewLabels[item]}
        {item === 'reviews' && pendingReviews > 0 && <b>{pendingReviews}</b>}
      </button>
    ))
  }

  return (
    <HouseholdContext.Provider value={householdView}>
      <div className="app-shell">
        <aside className="sidebar">
          <a
            className="brand"
            href="#"
            onClick={e => {
              e.preventDefault()
              navigate('dashboard')
            }}
          >
            <span className="brand-mark">
              <BrandMark />
            </span>
            <strong>
              Monitora <span>Pet</span>
            </strong>
          </a>
          <button
            type="button"
            className="menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="app-menu"
            aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}
            onClick={() => setMenuOpen(open => !open)}
          >
            <Icon name={menuOpen ? 'close' : 'menu'} />
            {!menuOpen && pendingReviews > 0 && <b>{pendingReviews}</b>}
          </button>
          <div id="app-menu" className={`sidebar-menu ${menuOpen ? 'open' : ''}`}>
            <p className="nav-caption">ACOMPANHAMENTO</p>
            <nav>{navItems(primaryViews)}</nav>
            <p className="nav-caption second">MONITORAMENTO</p>
            <nav>{navItems(monitoringViews)}</nav>
            <PawTrail
              key={`side-${householdView.household}`}
              household={householdView.household}
              className="sidebar-trail"
              steps={4}
            />
          </div>
        </aside>
        <PawTrail key={`page-${householdView.household}`} household={householdView.household} className="page-trail" />
        {menuOpen && <div className="menu-backdrop" onClick={closeMenu} aria-hidden="true" />}
        <div className="main-shell">
          <header className="topbar">
            <strong>{viewLabels[view]}</strong>
            <JobBanner refresh={refresh} />
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
            {view === 'cameras' && (
              <CamerasView cameras={cameras} zones={zones} refresh={refresh} reloadToken={reloadToken} />
            )}
            {view === 'zones' && <ZoneEditor cameras={cameras} zones={zones} refresh={refresh} />}
            {view === 'pets' && <PetManager pets={pets} refresh={refresh} />}
            {view === 'history' && <HistoryView pets={pets} reloadToken={reloadToken} />}
            {view === 'reviews' && <ReviewsView pets={pets} reloadToken={reloadToken} refresh={refresh} />}
            {view === 'settings' && (
              <SettingsView version={dashboard?.health.version ?? ''} settings={settings} onSettings={applySettings} />
            )}
          </main>
          <footer className="app-footer">
            Monitora Pet <span>Um pouco mais perto da rotina deles.</span>
          </footer>
        </div>
      </div>
      {settings && !household && (
        <OnboardingView onDone={chosen => applySettings({ ...settings, household_species: chosen })} />
      )}
    </HouseholdContext.Provider>
  )
}
