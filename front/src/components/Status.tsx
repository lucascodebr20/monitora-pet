export default function Status({ connected }: { connected: boolean }) {
  return (
    <span className={`status ${connected ? 'online' : ''}`}>
      <i />
      {connected ? 'Online' : 'Offline'}
    </span>
  )
}
