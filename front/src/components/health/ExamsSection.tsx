import { FormEvent, useCallback, useState } from 'react'
import * as api from '../../api'
import type { Exam, ExamPayload, ExamType, HealthAttachment } from '../../api'
import { errorMessage } from '../../lib/errors'
import { examTypeLabels } from '../../lib/labels'
import Lightbox from '../Lightbox'
import { useToast } from '../useToast'
import { AttachmentList, SectionState, formatDay, useLoader } from './shared'

type Props = { petId: string; petName: string; onChanged: () => void }

const ACCEPT = 'application/pdf,image/jpeg,image/png,image/webp'
const emptyExam = (): ExamPayload => ({
  title: '',
  exam_type: 'BLOOD',
  performed_on: null,
  laboratory: '',
  professional: '',
  notes: '',
  transcription: '',
})

export default function ExamsSection({ petId, petName, onChanged }: Props) {
  const showToast = useToast()
  const load = useCallback(() => api.getExams(petId), [petId])
  const { data: exams, setData, loading, error, reload } = useLoader<Exam[]>(load, [], 'Não foi possível carregar os exames.')
  const [form, setForm] = useState<ExamPayload | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [fileInputKey, setFileInputKey] = useState(0)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [uploadingTo, setUploadingTo] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [openImage, setOpenImage] = useState<HealthAttachment | null>(null)

  function startCreate() {
    setEditingId(null)
    setForm(emptyExam())
    setFiles([])
    setFileInputKey(key => key + 1)
    setFormError('')
  }

  function startEdit(exam: Exam) {
    setEditingId(exam.id)
    setForm({
      title: exam.title,
      exam_type: exam.exam_type,
      performed_on: exam.performed_on,
      laboratory: exam.laboratory,
      professional: exam.professional,
      notes: exam.notes,
      transcription: exam.transcription,
    })
    setFiles([])
    setFormError('')
  }

  async function uploadAll(examId: string, selected: File[]): Promise<string[]> {
    const failures: string[] = []
    for (const file of selected) {
      try {
        await api.uploadExamFile(petId, examId, file)
      } catch (reason) {
        failures.push(`${file.name}: ${errorMessage(reason, 'falhou')}`)
      }
    }
    return failures
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form || saving) return
    setSaving(true)
    setFormError('')
    try {
      const payload = { ...form, performed_on: form.performed_on || null }
      const exam = editingId ? await api.updateExam(petId, editingId, payload) : await api.createExam(petId, payload)
      const failures = await uploadAll(exam.id, files)
      setForm(null)
      reload()
      onChanged()
      if (failures.length) showToast(`Exame salvo, mas alguns arquivos falharam: ${failures.join('; ')}`, 'error')
      else showToast(editingId ? 'Exame atualizado.' : 'Exame guardado.')
    } catch (reason) {
      setFormError(errorMessage(reason, 'Não foi possível salvar o exame.'))
    } finally {
      setSaving(false)
    }
  }

  async function addFiles(exam: Exam, selected: FileList | null) {
    if (!selected?.length) return
    setUploadingTo(exam.id)
    const failures = await uploadAll(exam.id, Array.from(selected))
    setUploadingTo(null)
    reload()
    if (failures.length) showToast(failures.join('; '), 'error')
    else showToast('Arquivos anexados.')
  }

  async function removeAttachment(attachment: HealthAttachment) {
    if (!window.confirm(`Remover ${attachment.original_name}? O arquivo original será apagado.`)) return
    setDeleting(attachment.id)
    try {
      await api.deleteHealthAttachment(petId, attachment.id)
      setData(current =>
        current.map(exam => ({ ...exam, attachments: exam.attachments.filter(item => item.id !== attachment.id) })),
      )
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível remover o arquivo.'), 'error')
    } finally {
      setDeleting(null)
    }
  }

  async function remove(exam: Exam) {
    if (!window.confirm(`Apagar o exame "${exam.title}" e todos os arquivos dele?`)) return
    try {
      await api.deleteHealthRecord(petId, 'exams', exam.id)
      reload()
      onChanged()
      showToast('Exame apagado.')
    } catch (reason) {
      showToast(errorMessage(reason, 'Não foi possível apagar o exame.'), 'error')
    }
  }

  return (
    <section className="panel health-section" aria-labelledby="exams-title">
      <div className="panel-head">
        <div>
          <h2 id="exams-title">Exames e documentos</h2>
          <p>Laudos, receitas e exames de {petName}, com os arquivos originais guardados neste computador.</p>
        </div>
        {!form && (
          <button className="primary" onClick={startCreate}>
            + Exame
          </button>
        )}
      </div>
      {form && (
        <form className="stack-form health-form" onSubmit={submit}>
          <fieldset disabled={saving}>
            <div className="health-form-grid">
              <label>
                Nome do exame
                <input
                  required
                  autoFocus
                  maxLength={160}
                  value={form.title}
                  onChange={e => setForm({ ...form, title: e.target.value })}
                  placeholder="Ex.: Hemograma completo"
                />
              </label>
              <label>
                Tipo
                <select
                  value={form.exam_type}
                  onChange={e => setForm({ ...form, exam_type: e.target.value as ExamType })}
                >
                  {Object.entries(examTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Data do exame <small>(se souber)</small>
                <input
                  type="date"
                  value={form.performed_on ?? ''}
                  onChange={e => setForm({ ...form, performed_on: e.target.value || null })}
                />
              </label>
              <label>
                Laboratório ou clínica
                <input
                  maxLength={160}
                  value={form.laboratory}
                  onChange={e => setForm({ ...form, laboratory: e.target.value })}
                />
              </label>
              <label>
                Veterinário(a)
                <input
                  maxLength={160}
                  value={form.professional}
                  onChange={e => setForm({ ...form, professional: e.target.value })}
                />
              </label>
              <label>
                Arquivos <small>(PDF ou fotos, várias páginas)</small>
                <input
                  key={fileInputKey}
                  type="file"
                  multiple
                  accept={ACCEPT}
                  onChange={e => setFiles(Array.from(e.target.files ?? []))}
                />
              </label>
            </div>
            <label>
              Observações
              <textarea
                maxLength={2000}
                value={form.notes}
                onChange={e => setForm({ ...form, notes: e.target.value })}
                placeholder="Ex.: pedido por causa da perda de apetite"
              />
            </label>
            <label>
              Transcrição dos resultados <small>(opcional, digitada por você)</small>
              <textarea
                className="health-transcription"
                maxLength={20000}
                value={form.transcription}
                onChange={e => setForm({ ...form, transcription: e.target.value })}
                placeholder={'Ex.:\nUreia: 58 mg/dL (ref. 42–64)\nCreatinina: 1,9 mg/dL (ref. 0,8–1,8)'}
              />
            </label>
            {formError && <p className="form-error">{formError}</p>}
            <div className="pet-form-actions">
              <button type="button" className="tertiary" onClick={() => setForm(null)}>
                Cancelar
              </button>
              <button className="primary">
                {saving ? (files.length ? 'Enviando arquivos…' : 'Salvando…') : 'Salvar'}
              </button>
            </div>
          </fieldset>
        </form>
      )}
      <SectionState
        loading={loading}
        error={error}
        empty={!exams.length && !form}
        emptyTitle="Nenhum exame guardado"
        emptyText="Adicione o PDF do laboratório ou fotos das páginas impressas. O original fica guardado para mostrar na consulta."
      />
      <div className="health-cards">
        {exams.map(exam => (
          <article className="health-card" key={exam.id}>
            <header>
              <div>
                <h3>{exam.title}</h3>
                <p>
                  {[examTypeLabels[exam.exam_type], exam.laboratory, exam.professional].filter(Boolean).join(' · ')}
                </p>
              </div>
              <span className="health-date">{formatDay(exam.performed_on, 'Sem data')}</span>
            </header>
            {exam.notes && <p className="health-notes">{exam.notes}</p>}
            <AttachmentList
              attachments={exam.attachments}
              onOpenImage={setOpenImage}
              onDelete={attachment => void removeAttachment(attachment)}
              deleting={deleting}
            />
            {exam.transcription && (
              <details className="health-transcription-view">
                <summary>Resultados transcritos</summary>
                <pre>{exam.transcription}</pre>
              </details>
            )}
            <footer>
              <label className={`tertiary health-upload ${uploadingTo === exam.id ? 'busy' : ''}`}>
                {uploadingTo === exam.id ? 'Enviando…' : 'Anexar arquivos'}
                <input
                  type="file"
                  multiple
                  accept={ACCEPT}
                  disabled={uploadingTo === exam.id}
                  onChange={e => {
                    void addFiles(exam, e.target.files)
                    e.target.value = ''
                  }}
                />
              </label>
              <button className="tertiary" onClick={() => startEdit(exam)}>
                Editar
              </button>
              <button className="tertiary danger" onClick={() => void remove(exam)}>
                Apagar
              </button>
            </footer>
          </article>
        ))}
      </div>
      {openImage && <Lightbox src={openImage.url} alt={openImage.original_name} onClose={() => setOpenImage(null)} />}
    </section>
  )
}
