import type { Household } from '../lib/household'

type Props = { household: Household; size?: number }

/**
 * Ilustração de cada opção de "Quem mora com você": rosto de gato, rosto de
 * cachorro e, para a casa com os dois, as patinhas da marca. Desenha em
 * currentColor, então a cor vem do CSS do card; olhos e focinho usam as classes
 * art-detail, que o CSS inverte quando a opção está selecionada.
 */
export default function HouseholdArt({ household, size = 32 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      {household === 'CAT' && <CatFace />}
      {household === 'DOG' && <DogFace />}
      {household === 'BOTH' && <Paws />}
    </svg>
  )
}

function CatFace() {
  return (
    <>
      <path
        fill="currentColor"
        d="M5.6 4.5 11.4 10a14 14 0 0 1 9.2 0l5.8-5.5c.5 3 .6 6.3.3 9.4 1.2 1.8 1.8 3.9 1.6 6.1-.5 5.2-5.4 8.3-12.3 8.3S4.2 25.2 3.7 20c-.2-2.2.4-4.3 1.6-6.1-.3-3.1-.2-6.4.3-9.4Z"
      />
      <path className="art-detail" opacity="0.35" d="M7.6 8.2 10.4 11l-2.6 1.6c-.3-1.4-.3-3 .2-4.4ZM24.4 8.2 21.6 11l2.6 1.6c.3-1.4.3-3-.2-4.4Z" />
      <ellipse cx="11.3" cy="17.6" rx="1.5" ry="2.1" className="art-detail" />
      <ellipse cx="20.7" cy="17.6" rx="1.5" ry="2.1" className="art-detail" />
      <path className="art-detail" d="M14.4 21.3h3.2L16 23.1Z" />
      <path
        className="art-detail-stroke"
        fill="none"
        strokeWidth="1.1"
        strokeLinecap="round"
        d="M16 23.1v1.2m0 0c-.6.8-1.6 1-2.4.6m2.4-.6c.6.8 1.6 1 2.4.6"
      />
    </>
  )
}

function DogFace() {
  return (
    <>
      <path
        fill="currentColor"
        opacity="0.6"
        d="M9.4 7.6C5 7.4 2.6 10.6 2.8 15.4c.2 4.2 1.6 6.6 3.8 6.8 1.7.1 2.6-1.7 3.1-4.6ZM22.6 7.6c4.4-.2 6.8 3 6.6 7.8-.2 4.2-1.6 6.6-3.8 6.8-1.7.1-2.6-1.7-3.1-4.6Z"
      />
      <path
        fill="currentColor"
        d="M16 6.8c5.6 0 8.6 3.8 8.6 9.6 0 6.6-3.8 11.2-8.6 11.2S7.4 23 7.4 16.4c0-5.8 3-9.6 8.6-9.6Z"
      />
      <circle cx="12.4" cy="15.6" r="1.4" className="art-detail" />
      <circle cx="19.6" cy="15.6" r="1.4" className="art-detail" />
      <ellipse cx="16" cy="22.2" rx="4.3" ry="3.4" className="art-detail" opacity="0.9" />
      <ellipse cx="16" cy="20.9" rx="1.9" ry="1.3" fill="currentColor" />
      <path fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" d="M16 22.2v1.1" />
    </>
  )
}

/** Mesma pata da marca (BrandMark), repetida em dois tamanhos. */
export function Paw() {
  return (
    <>
      <ellipse cx="4.3" cy="10.6" rx="1.9" ry="2.5" />
      <ellipse cx="9.3" cy="7.3" rx="2.1" ry="2.9" />
      <ellipse cx="14.7" cy="7.3" rx="2.1" ry="2.9" />
      <ellipse cx="19.7" cy="10.6" rx="1.9" ry="2.5" />
      <path d="M12 12.4c-3.1 0-5.6 2.1-5.6 4.6 0 2.1 1.8 3.4 3.7 2.9 1.2-.33 2.6-.33 3.8 0 1.9.5 3.7-.8 3.7-2.9 0-2.5-2.5-4.6-5.6-4.6Z" />
    </>
  )
}

function Paws() {
  return (
    <>
      <g fill="currentColor" opacity="0.55" transform="translate(13.6 1.2) rotate(18 9 10) scale(0.72)">
        <Paw />
      </g>
      <g fill="currentColor" transform="translate(1.4 9.4) rotate(-14 10 11) scale(0.86)">
        <Paw />
      </g>
    </>
  )
}
