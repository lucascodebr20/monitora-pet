import { FormEvent, useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Pet, PetSpecies } from '../api'

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
  const [open, setOpen] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState<Pet | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [readingPhoto,setReadingPhoto] = useState(false)
  const photoReadId = useRef(0)

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    dialogRef.current?.showModal()
    return () => { dialogRef.current?.close();previous?.focus() }
  }, [open])

  function startCreate() {
    setEditing(null)
    setForm({name:'',species:'CAT',description:'',photo_data:null})
    photoReadId.current++;setReadingPhoto(false)
    setError('');setNotice('');setOpen(true)
  }

  function edit(pet: Pet) {
    photoReadId.current++;setReadingPhoto(false)
    setOpen(true);setNotice('')
    setEditing(pet)
    setForm({ name: pet.name, species: pet.species, description: pet.description, photo_data: null })
    setError('')
  }

  function cancel() {
    photoReadId.current++;setReadingPhoto(false)
    setOpen(false)
    setEditing(null)
    setForm({ name: '', species: 'CAT', description: '', photo_data: null })
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if(saving || readingPhoto) return
    setSaving(true)
    setError('')
    try {
      if (editing) await api.updatePet(editing.id, form)
      else await api.createPet(form)
      cancel()
      await refresh()
      setNotice(editing ? 'Perfil atualizado.' : 'Pet cadastrado.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível salvar o pet.')
    } finally {
      setSaving(false)
    }
  }


  return <>
    <div className="page-heading"><div><p className="eyebrow">PERFIS LOCAIS</p><h1>Pets</h1></div><button className="primary" onClick={startCreate}>+ Cadastrar pet</button></div>
    {notice && <p className="review-notice" role="status">{notice}</p>}
    <section className="pet-layout pet-list-layout">

      <section className="pet-grid">{pets.map(pet => <article className="panel pet-card" key={pet.id}>
        {pet.photo_path ? <img src={`/api/pets/${pet.id}/photo`} alt={pet.name} /> : <div className="pet-placeholder">{pet.species === 'CAT' ? '🐈' : '🐕'}</div>}
        <div className="pet-card-info"><span className="eyebrow">{pet.species === 'CAT' ? 'GATO' : 'CÃO'}</span><h2>{pet.name}</h2><p>{pet.description || 'Sem características cadastradas.'}</p><small>{pet.event_count} evento(s) · {pet.reference_count} captura(s) confirmada(s)</small><div><button className="tertiary" onClick={() => edit(pet)}>Editar</button><button className="tertiary danger" onClick={async () => { if (window.confirm(`Remover o perfil de ${pet.name}?`)) { await api.deletePet(pet.id); await refresh() } }}>Remover</button></div></div>
      </article>)}{!pets.length && <section className="panel pet-empty"><h2>Comece cadastrando um pet</h2><p>Adicione uma foto inicial. Depois, confirme o animal nas revisões para acumular capturas reais dele.</p></section>}</section>
    </section>
    {open && <dialog ref={dialogRef} className="modal pet-modal" aria-labelledby="pet-form-title" onCancel={event=>{event.preventDefault();if(!saving)cancel()}}>
      <form className="stack-form pet-form" onSubmit={submit}>
        <div className="panel-head"><div><p className="eyebrow">{editing ? 'EDITAR PERFIL' : 'NOVO PET'}</p><h2 id="pet-form-title">{editing ? `Editar ${editing.name}` : 'Cadastrar pet'}</h2></div><button type="button" className="close" aria-label="Fechar cadastro" disabled={saving} onClick={cancel}>×</button></div>
        <fieldset className="pet-form-fields" disabled={saving}><label>Nome<input autoFocus required maxLength={80} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Mingau" /></label>
        <fieldset className="species-options"><legend>Espécie</legend>{(['CAT','DOG'] as PetSpecies[]).map(species=><label className={form.species===species?'chosen':''} key={species}><input type="radio" name="pet-species" value={species} checked={form.species===species} onChange={()=>setForm({...form,species})}/>{species==='CAT'?'Gato':'Cão'}</label>)}</fieldset>
        <label>Características visuais<textarea maxLength={500} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} placeholder="Ex.: pelo preto, mancha branca no peito" /></label>
        <label>Foto de referência<input type="file" accept="image/*" required={!editing?.photo_path && !form.photo_data} onChange={async event => { const file = event.target.files?.[0]; if (!file) return; const readId=++photoReadId.current;setReadingPhoto(true);try { setForm(current => ({ ...current, photo_data: null })); const photo_data = await preparePhoto(file);if(readId!==photoReadId.current)return; setForm(current => ({ ...current, photo_data })) } catch (reason) { if(readId===photoReadId.current)setError(reason instanceof Error ? reason.message : 'Falha ao carregar a foto.') } finally {if(readId===photoReadId.current)setReadingPhoto(false)} }} /></label>
        {form.photo_data && <img className="pet-photo-preview" src={form.photo_data} alt="Prévia da foto do pet" />}
        {editing?.photo_path && !form.photo_data && <p className="muted">A foto atual será mantida se nenhuma nova for selecionada.</p>}
        {error && <p className="form-error">{error}</p>}
        <div className="pet-form-actions"><button type="button" className="tertiary" disabled={saving} onClick={cancel}>Cancelar</button><button className="primary" disabled={saving || readingPhoto}>{readingPhoto ? 'Preparando foto…' : saving ? 'Salvando…' : editing ? 'Salvar perfil' : 'Cadastrar pet'}</button></div>
</fieldset>
      </form>
    </dialog>}
  </>
}
