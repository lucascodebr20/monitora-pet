import { ReactNode } from 'react'

export default function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon">◇</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}
