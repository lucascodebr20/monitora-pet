import type { CSSProperties } from 'react'
import type { Household } from '../lib/household'
import { Paw } from './HouseholdArt'

type Props = {
  household: Household
  className?: string
  /** Quantas pegadas a trilha tem. */
  steps?: number
}

/** Pata de cachorro: dedos mais compridos, almofada maior e as unhas à mostra. */
function DogPaw() {
  return (
    <>
      <ellipse cx="4.6" cy="10.2" rx="1.9" ry="2.7" />
      <ellipse cx="9.3" cy="6.6" rx="2" ry="3" />
      <ellipse cx="14.7" cy="6.6" rx="2" ry="3" />
      <ellipse cx="19.4" cy="10.2" rx="1.9" ry="2.7" />
      <ellipse cx="4" cy="6.9" rx="0.7" ry="1" />
      <ellipse cx="9" cy="2.9" rx="0.7" ry="1" />
      <ellipse cx="15" cy="2.9" rx="0.7" ry="1" />
      <ellipse cx="20" cy="6.9" rx="0.7" ry="1" />
      <path d="M12 11.6c-3.6 0-6.2 2.6-6.2 5.4 0 2.4 1.9 3.6 3.8 3 1.6-.5 3.2-.5 4.8 0 1.9.6 3.8-.6 3.8-3 0-2.8-2.6-5.4-6.2-5.4Z" />
    </>
  )
}

// A trilha sobe na diagonal, do canto inferior direito ao superior esquerdo.
const START = { x: 98, y: 150 }
const END = { x: 22, y: 14 }

/**
 * Pegadas decorativas andando na diagonal. A pata segue a casa: gato, cachorro
 * ou as duas alternadas. Cada pegada aparece em sequência (CSS `--step`), então
 * remontar o componente com outra `key` faz a trilha "andar" de novo.
 */
export default function PawTrail({ household, className = '', steps = 6 }: Props) {
  const dx = END.x - START.x
  const dy = END.y - START.y
  const length = Math.hypot(dx, dy)
  const heading = (Math.atan2(dx, -dy) * 180) / Math.PI
  const side = { x: -dy / length, y: dx / length }

  return (
    <svg className={`paw-trail ${className}`} viewBox="0 0 120 164" aria-hidden="true">
      {Array.from({ length: steps }, (_, step) => {
        const t = steps === 1 ? 0 : step / (steps - 1)
        const offset = step % 2 === 0 ? 10 : -10
        const x = START.x + dx * t + side.x * offset
        const y = START.y + dy * t + side.y * offset
        const dog = household === 'DOG' || (household === 'BOTH' && step % 2 === 1)
        return (
          <g key={step} transform={`translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${heading.toFixed(1)})`}>
            {/* A animação usa transform no CSS, então a escala fica num <g> próprio. */}
            <g className="paw-step" style={{ '--step': step } as CSSProperties}>
              <g transform="scale(0.95) translate(-12 -12)">{dog ? <DogPaw /> : <Paw />}</g>
            </g>
          </g>
        )
      })}
    </svg>
  )
}
