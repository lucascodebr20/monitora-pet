const paths: Record<string, string> = {
  dashboard: 'M3 10 12 3 21 10 M5 9v11h14V9 M9 20v-7h6v7',
  history: 'M4 5h16 M4 12h16 M4 19h16',
  reviews: 'M9 3h6v4H9z M9 5H5v16h14V5h-4 M8 14l3 3 5-6',
  pets: 'M7 10a2 3 0 1 0 0-6 2 3 0 1 0 0 6 M17 10a2 3 0 1 0 0-6 2 3 0 1 0 0 6 M3 15a2 2 0 1 0 0-4 2 2 0 1 0 0 4 M21 15a2 2 0 1 0 0-4 2 2 0 1 0 0 4 M8 14c-7 6-2 9 4 6 6 3 11 0 4-6-3-3-5-3-8 0',
  camera: 'M3 7h12v13H3z M15 11l6-4v13l-6-4',
  cameras: 'M3 7h12v13H3z M15 11l6-4v13l-6-4',
  zones: 'M4 4h4 M4 4v4 M20 4h-4 M20 4v4 M4 20h4 M4 20v-4 M20 20h-4 M20 20v-4 M8 8h8v8H8z',
  settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 1 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
  water: 'M12 3C9 7 5 11 5 15a7 7 0 0 0 14 0c0-4-4-8-7-12Z M8 15c0 2 1 3 3 3',
  food: 'M3 11h18c0 6-3 9-9 9s-9-3-9-9Z M7 7V4 M12 7V3 M17 7V4',
  litter: 'M3 8h18l-2 12H5Z M7 8V4h10v4 M8 13h8',
  activity: 'M2 12h4l3-8 5 16 3-8h5',
  calendar: 'M4 5h16v16H4z M8 2v6 M16 2v6 M4 10h16',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 1 0 0-18 M12 7v5l3 2',
  shield: 'M12 3 3 7v6c0 5 9 9 9 9s9-4 9-9V7Z M8 12l3 3 5-6',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 1 0 0-18 M12 11v6 M12 7v1',
}

export default function Icon({ name }: { name: string }) {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.info} /></svg>
}
