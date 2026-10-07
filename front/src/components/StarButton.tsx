import { useState } from 'react'
import * as api from '../api'
import type { Event } from '../api'
import { errorMessage } from '../lib/errors'
import { useToast } from './useToast'
import Icon from './Icon'

type Props = { event: Event; onChange: (event: Event) => void; withLabel?: boolean }

export default function StarButton({ event, onChange, withLabel = false }: Props) {
  const showToast = useToast()
  const [saving, setSaving] = useState(false)
  const marked = event.highlighted_at !== null
  const label = marked ? 'Remover dos favoritos' : 'Adicionar aos favoritos'

  async function toggle() {
    if (saving) return
    setSaving(true)
    try {
      onChange(await api.setEventHighlighted(event.id, !marked))
      showToast(marked ? 'Removido dos favoritos.' : 'Adicionado aos favoritos.')
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível atualizar a marcação.'), 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <button
      type="button"
      className={`star-button ${marked ? 'marked' : ''} ${withLabel ? 'with-label' : ''}`}
      aria-pressed={marked}
      aria-label={withLabel ? undefined : label}
      title={label}
      disabled={saving}
      onClick={e => {
        e.stopPropagation()
        void toggle()
      }}
    >
      <Icon name="star" filled={marked} />
      {withLabel && <span>{marked ? 'Favorito' : 'Favoritar'}</span>}
    </button>
  )
}
