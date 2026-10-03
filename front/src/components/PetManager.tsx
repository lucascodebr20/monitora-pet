import { FormEvent, useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Pet, PetSpecies } from '../api'
import { useToast } from './Toast'

type Props = { pets: Pet[]; refresh: () => Promise<void> }

async function cropPhoto(sourceUrl: string, position: { x: number; y: number }): Promise<string> {
  const source = await new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.onerror = () => reject(new Error('O arquivo não parece ser uma imagem.'))
    image.onload = () => resolve(image)
    image.src = sourceUrl
  })
  const cropSize = Math.min(source.width, source.height)
  const sourceX = (source.width - cropSize) * position.x / 100
  const sourceY = (source.height - cropSize) * position.y / 100
  const canvas = document.createElement('canvas')
  canvas.width = 640
  canvas.height = 640
  canvas.getContext('2d')?.drawImage(source, sourceX, sourceY, cropSize, cropSize, 0, 0, 640, 640)
  return canvas.toDataURL('image/jpeg', 0.88)
}

export default function PetManager({ pets, refresh }: Props) {
  const showToast = useToast()
  const [form, setForm] = useState({ name: '', species: 'CAT' as PetSpecies, description: '', photo_data: null as string | null })
  const [open, setOpen] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [editing, setEditing] = useState<Pet | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [readingPhoto,setReadingPhoto] = useState(false)
  const [photoSource,setPhotoSource] = useState<string | null>(null)
  const [cropPosition,setCropPosition] = useState({x:50,y:50})
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
    setPhotoSource(null);setCropPosition({x:50,y:50})
    photoReadId.current++;setReadingPhoto(false)
    setError('');setOpen(true)
  }

  function edit(pet: Pet) {
    photoReadId.current++;setReadingPhoto(false)
    setOpen(true)
    setEditing(pet)
    setForm({ name: pet.name, species: pet.species, description: pet.description, photo_data: null })
    setPhotoSource(null);setCropPosition({x:50,y:50})
    setError('')
  }

  function cancel() {
    photoReadId.current++;setReadingPhoto(false)
    setOpen(false)
    setEditing(null)
    setForm({ name: '', species: 'CAT', description: '', photo_data: null })
    setPhotoSource(null);setCropPosition({x:50,y:50})
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if(saving || readingPhoto) return
    setSaving(true)
    setError('')
    try {
      const photo_data = photoSource ? await cropPhoto(photoSource, cropPosition) : form.photo_data
      const payload = { ...form, photo_data }
      if (editing) await api.updatePet(editing.id, payload)
      else await api.createPet(payload)
      cancel()
      await refresh()
      showToast(editing ? 'Perfil atualizado.' : 'Pet cadastrado.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível salvar o pet.')
    } finally {
      setSaving(false)
    }
  }


  return <>
    <div className="page-heading"><div><p className="eyebrow">PERFIS LOCAIS</p><h1>Pets</h1></div><button className="primary" onClick={startCreate}>+ Cadastrar pet</button></div>
    <section className="pet-layout pet-list-layout">

      <section className="pet-grid">{pets.map(pet => <article className="panel pet-card" key={pet.id}>
        {pet.photo_path ? <img src={`/api/pets/${pet.id}/photo`} alt={pet.name} /> : <div className="pet-placeholder">{pet.species === 'CAT' ? '🐈' : '🐕'}</div>}
        <div className="pet-card-info"><span className="eyebrow">{pet.species === 'CAT' ? 'GATO' : 'CÃO'}</span><h2>{pet.name}</h2><p>{pet.description || 'Sem características cadastradas.'}</p><small>{pet.event_count} evento(s) · {pet.reference_count} captura(s) confirmada(s)</small><div><button className="tertiary" onClick={() => edit(pet)}>Editar</button><button className="tertiary danger" onClick={async () => { if (window.confirm(`Remover o perfil de ${pet.name}?`)) { await api.deletePet(pet.id); await refresh(); showToast(`Perfil de ${pet.name} removido.`) } }}>Remover</button></div></div>
      </article>)}{!pets.length && <section className="panel pet-empty"><h2>Comece cadastrando um pet</h2><p>Adicione uma foto inicial. Depois, confirme o animal nas revisões para acumular capturas reais dele.</p></section>}</section>
    </section>
    {open && <dialog ref={dialogRef} className="modal pet-modal" aria-labelledby="pet-form-title" onCancel={event=>{event.preventDefault();if(!saving)cancel()}}>
      <form className="stack-form pet-form" onSubmit={submit}>
        <div className="panel-head"><div><p className="eyebrow">{editing ? 'EDITAR PERFIL' : 'NOVO PET'}</p><h2 id="pet-form-title">{editing ? `Editar ${editing.name}` : 'Cadastrar pet'}</h2></div><button type="button" className="close" aria-label="Fechar cadastro" disabled={saving} onClick={cancel}>×</button></div>
        <fieldset className="pet-form-fields" disabled={saving}><label>Nome<input autoFocus required maxLength={80} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Mingau" /></label>
        <fieldset className="species-options"><legend>Espécie</legend>{(['CAT','DOG'] as PetSpecies[]).map(species=><label className={form.species===species?'chosen':''} key={species}><input type="radio" name="pet-species" value={species} checked={form.species===species} onChange={()=>setForm({...form,species})}/>{species==='CAT'?'Gato':'Cão'}</label>)}</fieldset>
        <label>Características visuais<textarea maxLength={500} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} placeholder="Ex.: pelo preto, mancha branca no peito" /></label>
        <label>Foto de referência<input type="file" accept="image/*" required={!editing?.photo_path && !photoSource} onChange={event => { const file = event.target.files?.[0]; if (!file) return; const readId=++photoReadId.current;setReadingPhoto(true);setError('');const reader=new FileReader();reader.onerror=()=>{if(readId===photoReadId.current){setError('Não foi possível abrir a foto.');setReadingPhoto(false)}};reader.onload=()=>{if(readId===photoReadId.current){setPhotoSource(String(reader.result));setCropPosition({x:50,y:50});setReadingPhoto(false)}};reader.readAsDataURL(file) }} /></label>
        {photoSource && <section className="pet-photo-crop" aria-label="Recortar foto de perfil"><div><p className="eyebrow">PRÉVIA DO PERFIL</p><div className="pet-crop-frame"><img src={photoSource} alt="Prévia do recorte da foto" style={{objectPosition:`${cropPosition.x}% ${cropPosition.y}%`}}/><span aria-hidden="true" /></div><small>A área dentro do círculo será a parte principal da foto de perfil.</small></div><div className="pet-crop-controls"><label>Posição horizontal<input type="range" min="0" max="100" value={cropPosition.x} onChange={event=>setCropPosition(current=>({...current,x:Number(event.target.value)}))}/></label><label>Posição vertical<input type="range" min="0" max="100" value={cropPosition.y} onChange={event=>setCropPosition(current=>({...current,y:Number(event.target.value)}))}/></label></div></section>}
        {editing?.photo_path && !photoSource && <p className="muted">A foto atual será mantida se nenhuma nova for selecionada.</p>}
        {error && <p className="form-error">{error}</p>}
        <div className="pet-form-actions"><button type="button" className="tertiary" disabled={saving} onClick={cancel}>Cancelar</button><button className="primary" disabled={saving || readingPhoto}>{readingPhoto ? 'Preparando foto…' : saving ? 'Salvando…' : editing ? 'Salvar perfil' : 'Cadastrar pet'}</button></div>
</fieldset>
      </form>
    </dialog>}
  </>
}
