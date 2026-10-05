import { FormEvent, useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Pet, PetReferenceImage, PetSpecies } from '../api'
import { errorMessage } from '../lib/errors'
import { speciesLabels } from '../lib/labels'
import Lightbox from './Lightbox'
import { useToast } from './useToast'

type Props = { pets: Pet[]; refresh: () => Promise<void> }
type PetTab = 'edit' | 'references'
type PetForm = { name: string; species: PetSpecies; description: string; photo_data: string | null }
type CropPosition = { x: number; y: number }

const CROP_SIZE = 640
const CROP_QUALITY = 0.88
const CENTER: CropPosition = { x: 50, y: 50 }
const SPECIES: PetSpecies[] = ['CAT', 'DOG']

const emptyForm = (): PetForm => ({ name: '', species: 'CAT', description: '', photo_data: null })
const formFor = (pet: Pet): PetForm => ({
  name: pet.name,
  species: pet.species,
  description: pet.description,
  photo_data: null,
})
const speciesEmoji = (species: PetSpecies) => (species === 'CAT' ? '🐈' : '🐕')

async function cropPhoto(sourceUrl: string, position: CropPosition): Promise<string> {
  const source = await new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.onerror = () => reject(new Error('O arquivo não parece ser uma imagem.'))
    image.onload = () => resolve(image)
    image.src = sourceUrl
  })
  const cropSize = Math.min(source.width, source.height)
  const sourceX = ((source.width - cropSize) * position.x) / 100
  const sourceY = ((source.height - cropSize) * position.y) / 100
  const canvas = document.createElement('canvas')
  canvas.width = CROP_SIZE
  canvas.height = CROP_SIZE
  canvas.getContext('2d')?.drawImage(source, sourceX, sourceY, cropSize, cropSize, 0, 0, CROP_SIZE, CROP_SIZE)
  return canvas.toDataURL('image/jpeg', CROP_QUALITY)
}

export default function PetManager({ pets, refresh }: Props) {
  const showToast = useToast()
  const [form, setForm] = useState<PetForm>(emptyForm)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [readingPhoto, setReadingPhoto] = useState(false)
  const [photoSource, setPhotoSource] = useState<string | null>(null)
  const [cropPosition, setCropPosition] = useState(CENTER)
  const [photoInputKey, setPhotoInputKey] = useState(0)
  const [photoVersion, setPhotoVersion] = useState(0)
  const photoReadId = useRef(0)
  const [detailsId, setDetailsId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<PetTab>('edit')
  const [references, setReferences] = useState<PetReferenceImage[]>([])
  const [loadingReferences, setLoadingReferences] = useState(false)
  const [referenceError, setReferenceError] = useState('')
  const [deletingReference, setDeletingReference] = useState<string | null>(null)
  const [openImage, setOpenImage] = useState<PetReferenceImage | null>(null)

  const detailedPet = pets.find(pet => pet.id === detailsId) ?? null

  useEffect(() => {
    if (!detailsId) return
    let active = true
    setReferences([])
    setLoadingReferences(true)
    setReferenceError('')
    void api
      .getPetReferences(detailsId)
      .then(images => {
        if (active) setReferences(images)
      })
      .catch(reason => {
        if (active) setReferenceError(errorMessage(reason, 'Não foi possível carregar as referências.'))
      })
      .finally(() => {
        if (active) setLoadingReferences(false)
      })
    return () => {
      active = false
    }
  }, [detailsId])

  function resetPhoto() {
    photoReadId.current++
    setReadingPhoto(false)
    setPhotoSource(null)
    setCropPosition(CENTER)
    setPhotoInputKey(current => current + 1)
  }

  function startCreate() {
    setDetailsId(null)
    setCreating(true)
    setForm(emptyForm())
    resetPhoto()
    setError('')
  }

  function openPet(pet: Pet, tab: PetTab) {
    setCreating(false)
    setDetailsId(pet.id)
    setActiveTab(tab)
    setForm(formFor(pet))
    resetPhoto()
    setError('')
  }

  function returnToList() {
    setCreating(false)
    setDetailsId(null)
    setActiveTab('edit')
    setForm(emptyForm())
    resetPhoto()
    setError('')
  }

  function discardProfileChanges() {
    if (!detailedPet) return
    setForm(formFor(detailedPet))
    resetPhoto()
    setError('')
  }

  function readPhoto(file: File | undefined) {
    if (!file) return
    const readId = ++photoReadId.current
    setReadingPhoto(true)
    setError('')
    const reader = new FileReader()
    reader.onerror = () => {
      if (readId === photoReadId.current) {
        setError('Não foi possível abrir a foto.')
        setReadingPhoto(false)
      }
    }
    reader.onload = () => {
      if (readId === photoReadId.current) {
        setPhotoSource(String(reader.result))
        setCropPosition(CENTER)
        setReadingPhoto(false)
      }
    }
    reader.readAsDataURL(file)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (saving || readingPhoto) return
    setSaving(true)
    setError('')
    try {
      const photo_data = photoSource ? await cropPhoto(photoSource, cropPosition) : form.photo_data
      const payload = { ...form, photo_data }
      if (detailedPet) {
        const updated = await api.updatePet(detailedPet.id, payload)
        setForm(formFor(updated))
        resetPhoto()
        setPhotoVersion(current => current + 1)
        await refresh()
        showToast('Perfil atualizado.')
      } else {
        await api.createPet(payload)
        returnToList()
        await refresh()
        showToast('Pet cadastrado.')
      }
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível salvar o pet.'))
    } finally {
      setSaving(false)
    }
  }

  async function removePet(pet: Pet) {
    if (!window.confirm(`Remover o perfil de ${pet.name}?`)) return
    try {
      await api.deletePet(pet.id)
      await refresh()
      showToast(`Perfil de ${pet.name} removido.`)
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível remover o pet.'), 'error')
    }
  }

  async function removeReference(image: PetReferenceImage) {
    if (!detailedPet || !window.confirm('Excluir esta imagem da galeria de referência?')) return
    setDeletingReference(image.id)
    setReferenceError('')
    try {
      await api.deletePetReference(detailedPet.id, image.id)
      setReferences(current => current.filter(item => item.id !== image.id))
      await refresh()
      showToast('Referência removida.')
    } catch (reason) {
      setReferenceError(errorMessage(reason, 'Não foi possível remover a referência.'))
    } finally {
      setDeletingReference(null)
    }
  }

  function formFields(mode: 'create' | 'edit') {
    const editing = mode === 'edit'
    return (
      <fieldset className="pet-form-fields" disabled={saving}>
        <label>
          Nome
          <input
            autoFocus={!editing}
            required
            maxLength={80}
            value={form.name}
            onChange={event => setForm({ ...form, name: event.target.value })}
            placeholder="Ex.: Mingau"
          />
        </label>
        <fieldset className="species-options">
          <legend>Espécie</legend>
          {SPECIES.map(species => (
            <label className={form.species === species ? 'chosen' : ''} key={species}>
              <input
                type="radio"
                name={`pet-species-${mode}`}
                value={species}
                checked={form.species === species}
                onChange={() => setForm({ ...form, species })}
              />
              {speciesLabels[species]}
            </label>
          ))}
        </fieldset>
        <label>
          Características visuais
          <textarea
            maxLength={500}
            value={form.description}
            onChange={event => setForm({ ...form, description: event.target.value })}
            placeholder="Ex.: pelo preto, mancha branca no peito"
          />
        </label>
        <label>
          Foto de referência
          <input
            key={photoInputKey}
            type="file"
            accept="image/*"
            required={!editing && !photoSource}
            onChange={event => readPhoto(event.target.files?.[0])}
          />
        </label>
        {photoSource && (
          <section className="pet-photo-crop" aria-label="Recortar foto de perfil">
            <div>
              <p className="eyebrow">PRÉVIA DO PERFIL</p>
              <div className="pet-crop-frame">
                <img
                  src={photoSource}
                  alt="Prévia do recorte da foto"
                  style={{ objectPosition: `${cropPosition.x}% ${cropPosition.y}%` }}
                />
                <span aria-hidden="true" />
              </div>
              <small>A área dentro do círculo será a parte principal da foto de perfil.</small>
            </div>
            <div className="pet-crop-controls">
              <label>
                Posição horizontal
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={cropPosition.x}
                  onChange={event => setCropPosition(current => ({ ...current, x: Number(event.target.value) }))}
                />
              </label>
              <label>
                Posição vertical
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={cropPosition.y}
                  onChange={event => setCropPosition(current => ({ ...current, y: Number(event.target.value) }))}
                />
              </label>
            </div>
          </section>
        )}
        {editing && detailedPet?.photo_path && !photoSource && (
          <p className="muted">A foto atual será mantida se nenhuma nova for selecionada.</p>
        )}
        {error && <p className="form-error">{error}</p>}
        <div className="pet-form-actions">
          <button
            type="button"
            className="tertiary"
            disabled={saving}
            onClick={editing ? discardProfileChanges : returnToList}
          >
            {editing ? 'Descartar alterações' : 'Cancelar'}
          </button>
          <button className="primary" disabled={saving || readingPhoto}>
            {readingPhoto ? 'Preparando foto…' : saving ? 'Salvando…' : editing ? 'Salvar alterações' : 'Cadastrar pet'}
          </button>
        </div>
      </fieldset>
    )
  }

  if (creating)
    return (
      <>
        <div className="page-heading pet-details-heading">
          <div>
            <button className="text-button pet-back" disabled={saving} onClick={returnToList}>
              ← Voltar para pets
            </button>
            <p className="eyebrow">NOVO PERFIL</p>
            <h1>Cadastrar pet</h1>
            <p>Adicione os dados e escolha uma boa foto de referência.</p>
          </div>
        </div>
        <section className="panel pet-create-page">
          <div className="panel-head">
            <div>
              <h2>Informações do pet</h2>
              <p>Esses dados ajudam a organizar o histórico e iniciar a identificação.</p>
            </div>
          </div>
          <form className="stack-form pet-form" onSubmit={submit}>
            {formFields('create')}
          </form>
        </section>
      </>
    )

  if (detailedPet)
    return (
      <>
        <div className="page-heading pet-details-heading">
          <div>
            <button className="text-button pet-back" disabled={saving} onClick={returnToList}>
              ← Voltar para pets
            </button>
            <p className="eyebrow">PERFIL DO PET</p>
            <h1>{detailedPet.name}</h1>
            <p>Consulte os dados, edite o perfil e organize as referências.</p>
          </div>
        </div>
        <section className="pet-profile-page">
          <article className="panel pet-profile-summary">
            {detailedPet.photo_path ? (
              <img src={`/api/pets/${detailedPet.id}/photo?v=${photoVersion}`} alt={detailedPet.name} />
            ) : (
              <div className="pet-placeholder">{speciesEmoji(detailedPet.species)}</div>
            )}
            <div>
              <span className="eyebrow">{speciesLabels[detailedPet.species].toUpperCase()}</span>
              <h2>{detailedPet.name}</h2>
              <p>{detailedPet.description || 'Sem características cadastradas.'}</p>
              <small>
                {detailedPet.event_count} evento(s) · {references.length} referência(s) ativa(s)
              </small>
            </div>
          </article>
          <div className="pet-profile-workspace">
            <nav className="pet-details-tabs" role="tablist" aria-label={`Perfil de ${detailedPet.name}`}>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'edit'}
                aria-controls="pet-edit-panel"
                className={activeTab === 'edit' ? 'active' : ''}
                onClick={() => setActiveTab('edit')}
              >
                Editar
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'references'}
                aria-controls="pet-references-panel"
                className={activeTab === 'references' ? 'active' : ''}
                onClick={() => setActiveTab('references')}
              >
                Referências <span>{references.length}</span>
              </button>
            </nav>
            {activeTab === 'edit' && (
              <section id="pet-edit-panel" role="tabpanel" className="panel pet-profile-editor">
                <div className="panel-head">
                  <div>
                    <h2>Editar perfil</h2>
                    <p>Atualize os dados e a foto principal deste pet.</p>
                  </div>
                </div>
                <form className="stack-form pet-form" onSubmit={submit}>
                  {formFields('edit')}
                </form>
              </section>
            )}
            {activeTab === 'references' && (
              <section id="pet-references-panel" className="panel pet-reference-panel" role="tabpanel">
                <div className="panel-head">
                  <div>
                    <h2>Galeria de referências</h2>
                    <p>Capturas confirmadas nas revisões e usadas na identificação automática.</p>
                  </div>
                  <span className="reference-count">{references.length}</span>
                </div>
                {referenceError && <p className="form-error">{referenceError}</p>}
                {loadingReferences ? (
                  <p className="loading">Carregando referências…</p>
                ) : references.length ? (
                  <div className="pet-reference-gallery">
                    {references.map((image, index) => (
                      <figure key={image.id}>
                        <button
                          type="button"
                          className="image-button"
                          title="Ver em tamanho maior"
                          onClick={() => setOpenImage(image)}
                        >
                          <img src={image.url} alt={`Referência ${index + 1} de ${detailedPet.name}`} />
                        </button>
                        <figcaption>
                          <span>{new Date(image.created_at).toLocaleDateString('pt-BR')}</span>
                          <button
                            className="tertiary danger"
                            disabled={deletingReference === image.id}
                            onClick={() => void removeReference(image)}
                          >
                            {deletingReference === image.id ? 'Excluindo…' : 'Excluir'}
                          </button>
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                ) : (
                  <div className="empty">
                    <h3>Nenhuma referência confirmada</h3>
                    <p>Novas imagens aparecerão aqui quando você identificar este pet durante uma revisão.</p>
                  </div>
                )}
              </section>
            )}
          </div>
        </section>
        {openImage && (
          <Lightbox src={openImage.url} alt={`Referência de ${detailedPet.name}`} onClose={() => setOpenImage(null)} />
        )}
      </>
    )

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">PERFIS LOCAIS</p>
          <h1>Pets</h1>
        </div>
        <button className="primary" onClick={startCreate}>
          + Cadastrar pet
        </button>
      </div>
      <section className="pet-layout pet-list-layout">
        <section className="pet-grid">
          {pets.map(pet => (
            <article className="panel pet-card" key={pet.id}>
              {pet.photo_path ? (
                <img src={`/api/pets/${pet.id}/photo`} alt={pet.name} />
              ) : (
                <div className="pet-placeholder">{speciesEmoji(pet.species)}</div>
              )}
              <div className="pet-card-info">
                <span className="eyebrow">{speciesLabels[pet.species].toUpperCase()}</span>
                <h2>{pet.name}</h2>
                <p>{pet.description || 'Sem características cadastradas.'}</p>
                <small>
                  {pet.event_count} evento(s) · {pet.reference_count} captura(s) confirmada(s)
                </small>
              </div>
              <div className="pet-card-actions">
                <button className="tertiary" onClick={() => openPet(pet, 'edit')}>
                  Editar
                </button>
                <button className="tertiary danger" onClick={() => void removePet(pet)}>
                  Excluir
                </button>
              </div>
            </article>
          ))}
          {!pets.length && (
            <section className="panel pet-empty">
              <h2>Comece cadastrando um pet</h2>
              <p>
                Adicione uma foto inicial. Depois, confirme o animal nas revisões para acumular capturas reais dele.
              </p>
            </section>
          )}
        </section>
      </section>
    </>
  )
}
