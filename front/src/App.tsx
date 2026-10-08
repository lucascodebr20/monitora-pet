import { useCallback, useMemo, useState } from 'react'
import BrandMark from './components/BrandMark'
import Icon from './components/Icon'
import JobBanner from './components/JobBanner'
import PawTrail from './components/PawTrail'
import PetManager from './components/PetManager'
import PetAvatar from './components/PetAvatar'
import ZoneEditor from './components/ZoneEditor'
import Tutorial from './components/Tutorial'
import { updateTutorial } from './api'
import { errorMessage } from './lib/errors'
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
  const [petsExpanded, setPetsExpanded] = useState(false)
  const [showAllPets, setShowAllPets] = useState(false)
  const [selectedPetId, setSelectedPetId] = useState<string | null>(null)
  const [petNavigationVersion, setPetNavigationVersion] = useState(0)
  const [openingTutorial, setOpeningTutorial] = useState(false)
  const [tutorialError, setTutorialError] = useState('')
  const [tutorialDismissed, setTutorialDismissed] = useState(false)
  const closeMenu = useCallback(() => setMenuOpen(false), [])
  useEscape(closeMenu, menuOpen)
  const { dashboard, cameras, zones, pets, settings, error, reloadToken, refresh, applySettings } = useAppData()
  const pendingReviews = dashboard?.pending_reviews ?? 0
  const household = settings?.household_species ?? null
  const tutorialOpen = Boolean(settings && household && settings.tutorial.status === 'active' && !tutorialDismissed)
  const householdView = useMemo(() => describeHousehold(household ?? 'BOTH'), [household])

  // O item "Pets" do menu mostra o pet da casa: gato, cachorro ou a pata para os dois.
  const petsIcon = household === 'CAT' ? 'cat' : household === 'DOG' ? 'dog' : 'pets'

  function navigate(next: View) {
    setView(next)
    setMenuOpen(false)
  }

  async function reopenTutorial() {
    if (openingTutorial) return
    setOpeningTutorial(true)
    setTutorialError('')
    try {
      if (settings?.tutorial.status !== 'active') applySettings(await updateTutorial(0))
      setTutorialDismissed(false)
    } catch (reason) {
      setTutorialError(errorMessage(reason, 'Não foi possível abrir o tutorial.'))
    } finally {
      setOpeningTutorial(false)
    }
  }

  function navItems(items: View[]) {
    return items.map(item =>
      item === 'pets' ? (
        <div className="sidebar-pets" key={item}>
          <button
            type="button"
            data-tutorial-view="pets"
            className={view === 'pets' ? 'active' : ''}
            aria-expanded={petsExpanded}
            aria-controls="sidebar-pet-list"
            onClick={() => setPetsExpanded(expanded => !expanded)}
          >
            <Icon name={petsIcon} />
            Pets
            <svg
              className={`pets-chevron ${petsExpanded ? 'expanded' : ''}`}
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden="true"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
          {petsExpanded && (
            <div id="sidebar-pet-list" className="sidebar-pet-list">
              {(showAllPets ? pets : pets.slice(0, 5)).map(pet => (
                <button
                  type="button"
                  key={pet.id}
                  className={view === 'pets' && selectedPetId === pet.id ? 'active' : ''}
                  aria-current={view === 'pets' && selectedPetId === pet.id ? 'page' : undefined}
                  onClick={() => {
                    setSelectedPetId(pet.id)
                    setPetNavigationVersion(version => version + 1)
                    navigate('pets')
                  }}
                >
                  <PetAvatar pet={pet} />
                  <span className="sidebar-pet-name">{pet.name}</span>
                </button>
              ))}
              {pets.length > 5 && (
                <button type="button" className="sidebar-pets-action" onClick={() => setShowAllPets(all => !all)}>
                  {showAllPets ? 'Ver menos' : `Ver mais (${pets.length - 5})`}
                </button>
              )}
              <button
                type="button"
                className="sidebar-pets-action"
                onClick={() => {
                  setSelectedPetId(null)
                  setPetNavigationVersion(version => version + 1)
                  navigate('pets')
                }}
              >
                {pets.length ? 'Gerenciar pets' : '+ Cadastrar pet'}
              </button>
            </div>
          )}
        </div>
      ) : (
        <button
          key={item}
          data-tutorial-view={item}
          className={view === item ? 'active' : ''}
          onClick={() => navigate(item)}
        >
          <Icon name={item} />
          {viewLabels[item]}
          {item === 'reviews' && pendingReviews > 0 && <b>{pendingReviews}</b>}
        </button>
      ),
    )
  }

  return (
    <HouseholdContext.Provider value={householdView}>
      <div className="app-shell" inert={tutorialOpen || Boolean(settings && !household)}>
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
            {settings && household && !tutorialOpen && (
              <button className="secondary" disabled={openingTutorial} onClick={() => void reopenTutorial()}>
                {settings.tutorial.status === 'active' ? 'Continuar tutorial' : 'Tutorial'}
              </button>
            )}
            <JobBanner refresh={refresh} />
          </header>
          <main className="content">
            {tutorialError && (
              <p className="form-error" role="alert">
                {tutorialError}
              </p>
            )}
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
            {view === 'pets' && (
              <PetManager
                key={petNavigationVersion}
                pets={pets}
                refresh={refresh}
                selectedPetId={selectedPetId}
                onSelectPet={setSelectedPetId}
              />
            )}
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
      {settings && tutorialOpen && (
        <Tutorial
          settings={settings}
          onSettings={applySettings}
          onClose={() => setTutorialDismissed(true)}
          onNavigate={next => {
            navigate(next)
            setTutorialDismissed(true)
          }}
        />
      )}
      {settings && !household && (
        <OnboardingView onDone={chosen => applySettings({ ...settings, household_species: chosen })} />
      )}
    </HouseholdContext.Provider>
  )
}
