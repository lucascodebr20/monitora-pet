import type { Pet } from '../api'

/** Foto do pet nos seletores; cai para a inicial do nome quando nao ha foto. */
export default function PetAvatar({ pet }: { pet: Pet }) {
  if (pet.photo_path) return <img className="pet-avatar" src={`/api/pets/${pet.id}/photo`} alt="" />
  return <span className="pet-avatar pet-initial">{pet.name.trim()[0]?.toUpperCase() ?? '?'}</span>
}
