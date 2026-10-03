import { FormEvent, useState } from 'react'
import * as api from '../api'
import type { Pet, PetReferenceImage, PetSpecies } from '../api'

type Props = { pets: Pet[]; refresh: () => Promise<void> }

async function preparePhoto(file: File): Promise<string> {
  const source = await new Promise<HTMLImageElement>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Não foi possível abrir a foto.'))
    reader.onload = () => {
      const image = new Image()
      image.onerror = () => reject(new Error('O arquivo não parece ser uma imagem.'))
      image.onload = () => resolve(image)
      image.src = String(reader.result)
    }
    reader.readAsDataURL(file)
  })
  const scale = Math.min(1, 900 / Math.max(source.width, source.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(source.width * scale)
  canvas.height = Math.round(source.height * scale)
  canvas.getContext('2d')?.drawImage(source, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', 0.84)
}

export default function PetManager({ pets, refresh }: Props) {
  const [form, setForm] = useState({ name: '', species: 'CAT' as PetSpecies, description: '', photo_data: null as string | null })
  const [editing, setEditing] = useState<Pet | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [expandedPet, setExpandedPet] = useState<string | null>(null)
  const [references, setReferences] = useState<Record<string, PetReferenceImage[]>>({})

  function edit(pet: Pet) {
    setEditing(pet)
    setForm({ name: pet.name, species: pet.species, description: pet.description, photo_data: null })
    setError('')
  }

  function cancel() {
    setEditing(null)
    setForm({ name: '', species: 'CAT', description: '', photo_data: null })
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (editing) await api.updatePet(editing.id, form)
      else await api.createPet(form)
      cancel()
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível salvar o pet.')
    } finally {
      setSaving(false)
    }
  }

  async function toggleReferences(pet: Pet) {
    if (expandedPet === pet.id) {
      setExpandedPet(null)
      return
    }
    setExpandedPet(pet.id)
    if (!references[pet.id]) {
      const images = await api.getPetReferences(pet.id)
      setReferences(current => ({ ...current, [pet.id]: images }))
    }
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">PERFIS LOCAIS</p><h1>Pets</h1><p>Cadastre cães e gatos. As capturas confirmadas nas revisões formarão referências visuais.</p></div></div>
    <section className="pet-layout">
      <form className="panel stack-form pet-form" onSubmit={submit}>
        <div><p className="eyebrow">{editing ? 'EDITAR PERFIL' : 'NOVO PET'}</p><h2>{editing ? editing.name : 'Cadastrar animal'}</h2></div>
        <label>Nome<input required maxLength={80} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Mingau" /></label>
        <label>Espécie<select value={form.species} onChange={event => setForm({ ...form, species: event.target.value as PetSpecies })}><option value="CAT">Gato</option><option value="DOG">Cão</option></select></label>
        <label>Características visuais<textarea maxLength={500} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} placeholder="Ex.: pelo preto, mancha branca no peito" /></label>
        <label>Foto de referência<input type="file" accept="image/*" required={!editing?.photo_path && !form.photo_data} onChange={async event => { const file = event.target.files?.[0]; if (!file) return; try { setForm(current => ({ ...current, photo_data: null })); const photo_data = await preparePhoto(file); setForm(current => ({ ...current, photo_data })) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Falha ao carregar a foto.') } }} /></label>
        {form.photo_data && <img className="pet-photo-preview" src={form.photo_data} alt="Prévia da foto do pet" />}
        {editing?.photo_path && !form.photo_data && <p className="muted">A foto atual será mantida se nenhuma nova for selecionada.</p>}
        {error && <p className="form-error">{error}</p>}
        <button className="primary full" disabled={saving}>{saving ? 'Salvando…' : editing ? 'Salvar perfil' : 'Cadastrar pet'}</button>
        {editing && <button type="button" className="ghost full" onClick={cancel}>Cancelar edição</button>}
      </form>
      <section className="pet-grid">{pets.map(pet => <article className="panel pet-card" key={pet.id}>
        {pet.photo_path ? <img src={`/api/pets/${pet.id}/photo`} alt={pet.name} /> : <div className="pet-placeholder">{pet.species === 'CAT' ? '🐈' : '🐕'}</div>}
        <div className="pet-card-info"><span className="eyebrow">{pet.species === 'CAT' ? 'GATO' : 'CÃO'}</span><h2>{pet.name}</h2><p>{pet.description || 'Sem características cadastradas.'}</p><small>{pet.event_count} evento(s) · {pet.reference_count} captura(s) confirmada(s)</small><div><button className="ghost" onClick={() => edit(pet)}>Editar</button><button className="ghost" onClick={() => void toggleReferences(pet)}>{expandedPet === pet.id ? 'Ocultar capturas' : 'Ver capturas'}</button><button className="ghost danger" onClick={async () => { if (window.confirm(`Remover o perfil de ${pet.name}?`)) { await api.deletePet(pet.id); await refresh() } }}>Remover</button></div>{expandedPet === pet.id && <div className="pet-reference-grid">{references[pet.id]?.length ? references[pet.id].map(image => <figure key={image.id}><img src={image.url} alt={`Captura confirmada de ${pet.name}`} /><figcaption>{new Date(image.created_at).toLocaleDateString('pt-BR')}</figcaption></figure>) : <small>As capturas confirmadas aparecerão aqui.</small>}</div>}</div>
      </article>)}{!pets.length && <section className="panel pet-empty"><h2>Comece cadastrando um pet</h2><p>Adicione uma foto inicial. Depois, confirme o animal nas revisões para acumular capturas reais dele.</p></section>}</section>
    </section>
  </>
}
