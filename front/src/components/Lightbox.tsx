import { useEscape } from '../lib/hooks'

type Props = { src: string; alt: string; onClose: () => void }

export default function Lightbox({ src, alt, onClose }: Props) {
  useEscape(onClose)
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={alt} onClick={onClose}>
      <section className="modal lightbox" onClick={event => event.stopPropagation()}>
        <div className="panel-head">
          <h2>{alt}</h2>
          <button type="button" className="close" aria-label="Fechar imagem" onClick={onClose}>
            ×
          </button>
        </div>
        <img src={src} alt={alt} />
      </section>
    </div>
  )
}
